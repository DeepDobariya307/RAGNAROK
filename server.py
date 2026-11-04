"""
RAGNAROK — web server (FastAPI). Serves the interface in web/ and the API it calls.

Run:  uvicorn server:app --port 7860      (or double-click start.bat on Windows)

State is in memory, per browser tab (session id in sessionStorage, sent as the
X-Session header — headers, not cookies, so it also works inside the Hugging Face
Spaces iframe where third-party cookies are often blocked). A restart drops all
sessions; idle sessions are cleaned up, including their Pinecone namespace.
"""

import calendar
import csv
import io
import json
import os
import re
import threading
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv
from fastapi import Body, FastAPI, File, Header, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from langchain_core.documents import Document
from langchain_core.messages import AIMessage, HumanMessage

from config import config
from core import DocumentProcessor, RAGChain, VectorStoreManager, highlight

load_dotenv()

WEB = Path(__file__).parent / "web"
MODELS = ["gpt-4o", "gpt-4o-mini"]
FILE_TYPES = {"pdf", "csv", "xlsx", "xls", "docx", "txt", "png", "jpg", "jpeg", "webp", "bmp"}
IMAGE_TYPES = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp", "bmp": "image/bmp"}
SID_RE = re.compile(r"^[0-9a-f]{32}$")
NAMESPACE_RE = re.compile(r"^s-(?:(\d{10})-)?[0-9a-f]{32}$")     # s-<YYYYMMDDHH>-<session>; old: s-<session>
CITE_GROUP_RE, CITE_NUM_RE = highlight.CITE_GROUP_RE, highlight.CITE_NUM_RE


@asynccontextmanager
async def lifespan(_app):
    if keys_ok():
        threading.Thread(target=cleanup_namespaces, daemon=True).start()
    yield


app = FastAPI(title="RAGNAROK", docs_url=None, redoc_url=None, lifespan=lifespan)


# ── Session state ─────────────────────────────────────────────────────────────

@dataclass
class Session:
    id: str
    docs: Dict[str, dict] = field(default_factory=dict)          # name -> {name, fmt, meta, ids}
    images: Dict[str, tuple] = field(default_factory=dict)       # name -> (bytes, mime)
    chats: Dict[str, dict] = field(default_factory=dict)         # id -> {id, title, messages, history}
    settings: dict = field(default_factory=lambda: {
        "model": config.OPENAI_CHAT_MODEL if config.OPENAI_CHAT_MODEL in MODELS else MODELS[0],
        "k": config.RETRIEVER_K,
        "fetch_k": max(config.RETRIEVER_FETCH_K, config.RETRIEVER_K),
        "lambda": config.MMR_LAMBDA,
    })
    eval: Optional[dict] = None
    created: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def namespace(self) -> str:
        """Pinecone namespace; the creation hour in the name lets old data be found and deleted."""
        return f"s-{time.strftime('%Y%m%d%H', time.gmtime(self.created))}-{self.id}"


SESSIONS: Dict[str, Session] = {}
SESSIONS_LOCK = threading.Lock()
_vs: Optional[VectorStoreManager] = None
_vs_lock = threading.Lock()


def keys_ok() -> bool:
    return bool(os.getenv("OPENAI_API_KEY")) and bool(os.getenv("PINECONE_API_KEY"))


def vs() -> VectorStoreManager:
    """One Pinecone client + embedder for the whole process (thread-safe HTTP clients)."""
    global _vs
    with _vs_lock:
        if _vs is None:
            _vs = VectorStoreManager()
        return _vs


def _reap_idle():
    now = time.time()
    with SESSIONS_LOCK:
        stale = [s for s in SESSIONS.values() if now - s.last_seen > config.SESSION_IDLE_HOURS * 3600]
        for s in stale:
            SESSIONS.pop(s.id, None)
    for s in stale:
        if s.docs and _vs is not None:
            _vs.delete_namespace(s.namespace)
    if now - _last_cleanup[0] > 3600:
        cleanup_namespaces()


_last_cleanup = [0.0]


def cleanup_namespaces():
    """
    Delete Pinecone data of sessions that no longer exist. Sessions live in memory,
    so after a restart their data would otherwise stay in Pinecone forever.
    Only namespaces this app created (s-...) and older than NAMESPACE_MAX_AGE_HOURS are touched.
    """
    _last_cleanup[0] = time.time()
    try:
        live = {s.namespace for s in list(SESSIONS.values())}
        for ns in vs().list_namespaces():
            m = NAMESPACE_RE.match(ns)
            if not m or ns in live:
                continue
            created = calendar.timegm(time.strptime(m.group(1), "%Y%m%d%H")) if m.group(1) else 0
            if time.time() - created > config.NAMESPACE_MAX_AGE_HOURS * 3600:
                vs().delete_namespace(ns)
    except Exception:
        pass   # housekeeping must never break the app


class RateLimiter:
    """At most `limit` events per `window` seconds per key (in-memory sliding window)."""

    def __init__(self, limit: int, window: float):
        self.limit, self.window = limit, window
        self.events: Dict[str, deque] = defaultdict(deque)
        self.lock = threading.Lock()

    def allow(self, key: str, n: int = 1) -> bool:
        now = time.time()
        with self.lock:
            q = self.events[key]
            while q and now - q[0] > self.window:
                q.popleft()
            if len(q) + n > self.limit:
                return False
            q.extend([now] * n)
            return True


LIMITS = {
    "question": RateLimiter(config.QUESTIONS_PER_10_MIN, 600),
    "file": RateLimiter(config.FILES_PER_HOUR, 3600),
    "eval": RateLimiter(config.EVALS_PER_HOUR, 3600),
}


def rate_limit(kind: str, request: Request, n: int = 1):
    ip = request.client.host if request.client else "unknown"
    if not LIMITS[kind].allow(ip, n):
        raise HTTPException(429, "Too many requests from this address. Please wait a few minutes and try again.")


def session(sid: Optional[str]) -> Session:
    if not sid or not SID_RE.match(sid):
        raise HTTPException(400, "Missing or malformed X-Session header")
    with SESSIONS_LOCK:
        s = SESSIONS.get(sid)
        if s is None:
            s = SESSIONS[sid] = Session(id=sid)
            new = True
        else:
            new = False
        s.last_seen = time.time()
    if new:
        threading.Thread(target=_reap_idle, daemon=True).start()
    return s


def need_keys():
    if not keys_ok():
        raise HTTPException(503, "OPENAI_API_KEY and PINECONE_API_KEY must be set")


def chain_for(s: Session) -> RAGChain:
    st = s.settings
    return RAGChain(vs(), s.namespace, model=st["model"], k=st["k"], fetch_k=st["fetch_k"], lambda_mult=st["lambda"])


# ── Presentation helpers ──────────────────────────────────────────────────────

def ext_of(name: str) -> str:
    return os.path.splitext(name)[1].lstrip(".").lower()


def fmt_of(name: str) -> str:
    e = ext_of(name)
    if e in IMAGE_TYPES:
        return "IMG"
    return {"docx": "DOCX", "txt": "TXT", "xls": "XLS", "xlsx": "XLSX", "csv": "CSV", "pdf": "PDF"}.get(e, e.upper()[:4] or "FILE")


def _int(v, default=0) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def doc_meta(name: str, chunks: List[Document]) -> str:
    """The sidebar's second line: '64 pages', '3 sheets', 'Image'…"""
    e = ext_of(name)
    if e in IMAGE_TYPES:
        return "Image"
    if e == "pdf":
        n = max((_int(c.metadata.get("page")) for c in chunks), default=0) + 1
        return f"{n} page{'s' if n != 1 else ''}"
    if e in ("xlsx", "xls"):
        n = len({c.metadata.get("sheet") for c in chunks}) or 1
        return f"{n} sheet{'s' if n != 1 else ''}"
    if e == "csv":
        n = max((_int(c.metadata.get("total_rows")) for c in chunks), default=0)
        return f"{n:,} rows"
    return f"{len(chunks)} passage{'s' if len(chunks) != 1 else ''}"


def location(meta: dict) -> str:
    """Where a passage came from, in words that match its file type."""
    name = str(meta.get("source_file", "")).lower()
    kind = meta.get("type")
    if kind == "image":
        return "Text read from image"
    if meta.get("row_start"):
        rows = f"rows {_int(meta['row_start']):,}–{_int(meta.get('row_end')):,}"
        if meta.get("sheet"):
            return f"Sheet “{meta['sheet']}” · {rows}"
        return f"{rows[0].upper()}{rows[1:]} of {_int(meta.get('total_rows')):,}"
    page = f"page {_int(meta.get('page')) + 1}" if name.endswith(".pdf") else ""
    if kind == "table":
        label = meta.get("caption") or "Table"
        return f"{label} · {page}" if page else label
    return page.capitalize() if page else "Text passage"


def source_view(d: Document) -> dict:
    name = d.metadata.get("source_file", "Unknown document")
    return {
        "doc": name, "fmt": fmt_of(name), "loc": location(d.metadata),
        "score": round(float(d.metadata.get("score", 0.0)), 2),
        "text": d.page_content.strip(), "isImg": d.metadata.get("type") == "image",
    }


def cited_numbers(text: str, n_docs: int) -> List[int]:
    seen = []
    for g in CITE_GROUP_RE.finditer(text):
        for m in CITE_NUM_RE.finditer(g.group(1)):
            n = int(m.group(1))
            if 1 <= n <= n_docs and n not in seen:
                seen.append(n)
    return seen


def count_tokens(text: str, model: str) -> int:
    try:
        import tiktoken
        try:
            enc = tiktoken.encoding_for_model(model)
        except KeyError:
            enc = tiktoken.get_encoding("o200k_base")
        return len(enc.encode(text))
    except Exception:
        return max(1, len(text) // 4)


def sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def state_view(s: Session) -> dict:
    return {
        "keysOk": keys_ok(),
        "docs": [{"name": d["name"], "fmt": d["fmt"], "meta": d["meta"]} for d in s.docs.values()],
        "chats": [{"id": c["id"], "title": c["title"]} for c in s.chats.values()],
        "settings": s.settings, "models": MODELS,
        "fixed": {"temperature": config.TEMPERATURE, "memory": config.MEMORY_WINDOW},
        "eval": s.eval,
    }


class NamedBytes(io.BytesIO):
    """What DocumentProcessor expects from an upload: .name, .read(), seekable."""
    def __init__(self, data: bytes, name: str):
        super().__init__(data)
        self.name = name


# ── API ───────────────────────────────────────────────────────────────────────

@app.get("/api/state")
def get_state(x_session: str = Header(None)):
    return state_view(session(x_session))


@app.get("/api/chats/{chat_id}")
def get_chat(chat_id: str, x_session: str = Header(None)):
    s = session(x_session)
    c = s.chats.get(chat_id)
    if not c:
        raise HTTPException(404, "No such chat")
    return {"id": c["id"], "title": c["title"], "messages": c["messages"]}


@app.post("/api/documents")
def add_documents(request: Request, files: List[UploadFile] = File(...), x_session: str = Header(None)):
    s = session(x_session)
    need_keys()
    new = [f for f in files if os.path.basename(f.filename or "") not in s.docs]
    if len(s.docs) + len(new) > config.MAX_DOCS_PER_SESSION:
        raise HTTPException(413, f"A session can hold up to {config.MAX_DOCS_PER_SESSION} documents.")
    rate_limit("file", request, len(new))
    batch = []
    for f in files:
        name = os.path.basename(f.filename or "")
        if not name or ext_of(name) not in FILE_TYPES:
            raise HTTPException(415, f"Unsupported file: {name or '(unnamed)'}")
        if name in s.docs:
            continue
        data = f.file.read(config.MAX_FILE_MB * 1024 * 1024 + 1)
        if len(data) > config.MAX_FILE_MB * 1024 * 1024:
            raise HTTPException(413, f"{name} is larger than {config.MAX_FILE_MB} MB")
        batch.append((name, data))
    if not batch:
        return state_view(s)

    processor = DocumentProcessor()
    added = []
    try:
        for name, data in batch:
            chunks = processor.process([NamedBytes(data, name)])
            if not chunks:
                raise HTTPException(422, f"No text could be read from {name}")
            ids = vs().upsert(chunks, s.namespace)
            added.append(name)
            with s.lock:
                s.docs[name] = {"name": name, "fmt": fmt_of(name), "meta": doc_meta(name, chunks), "ids": ids}
                if ext_of(name) in IMAGE_TYPES:
                    s.images[name] = (data, IMAGE_TYPES[ext_of(name)])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Indexing failed: {e}" + (f" (indexed {', '.join(added)} before the error)" if added else "")) from e
    return state_view(s)


@app.delete("/api/documents")
def remove_document(name: str = Query(...), x_session: str = Header(None)):
    s = session(x_session)
    d = s.docs.get(name)
    if not d:
        raise HTTPException(404, "No such document")
    if d["ids"]:
        vs().delete_ids(d["ids"], s.namespace)
    with s.lock:
        s.docs.pop(name, None)
        s.images.pop(name, None)
    return state_view(s)


@app.get("/api/files")
def get_file(name: str = Query(...), sid: str = Query(...)):
    """Image bytes for the source drawer (<img> can't send headers, so the session id is a query param)."""
    s = session(sid)
    img = s.images.get(name)
    if not img:
        raise HTTPException(404, "No preview")
    return Response(content=img[0], media_type=img[1], headers={"Cache-Control": "private, max-age=3600"})


@app.patch("/api/settings")
def update_settings(patch: dict = Body(...), x_session: str = Header(None)):
    s = session(x_session)
    with s.lock:
        st = dict(s.settings)
        if patch.get("model") in MODELS:
            st["model"] = patch["model"]
        if "k" in patch:
            st["k"] = min(max(_int(patch["k"], st["k"]), 2), 60)
        if "fetch_k" in patch:
            st["fetch_k"] = min(max(_int(patch["fetch_k"], st["fetch_k"]), 2), 60)
        if "lambda" in patch:
            try:
                st["lambda"] = round(min(max(float(patch["lambda"]), 0.0), 1.0), 1)
            except (TypeError, ValueError):
                pass
        st["fetch_k"] = max(st["fetch_k"], st["k"])   # the pool must hold at least k passages
        s.settings = st
    return state_view(s)


@app.post("/api/clear")
def clear_session(x_session: str = Header(None)):
    s = session(x_session)
    if s.docs and keys_ok():
        vs().delete_namespace(s.namespace)
    with SESSIONS_LOCK:
        SESSIONS.pop(s.id, None)
    return state_view(session(x_session))


@app.post("/api/ask")
def ask(request: Request, body: dict = Body(...), x_session: str = Header(None)):
    s = session(x_session)
    need_keys()
    rate_limit("question", request)
    question = str(body.get("question") or "").strip()
    if not question:
        raise HTTPException(400, "Empty question")
    if not s.docs:
        raise HTTPException(409, "Index at least one document first")

    with s.lock:
        chat = s.chats.get(body.get("chat_id") or "")
        if chat is None:
            cid = uuid.uuid4().hex[:10]
            title = question if len(question) <= 42 else question[:40].rstrip() + "…"
            chat = {"id": cid, "title": title, "messages": [], "history": []}
            s.chats = {cid: chat, **s.chats}               # newest first
        chat["messages"].append({"role": "user", "text": question})
        history = list(chat["history"])
    rag = chain_for(s)
    n_docs = len(s.docs)

    def run():
        yield sse("chat", {"id": chat["id"], "title": chat["title"]})
        try:
            t0 = time.perf_counter()
            standalone = rag.rephrase(question, history)
            t1 = time.perf_counter()
            docs, fetched = rag.search(standalone)
            t2 = time.perf_counter()
            sources = [source_view(d) for d in docs]
            yield sse("sources", {"sources": sources, "standalone": standalone})

            full = ""
            for token in rag.stream(standalone, docs, history):
                full += token
                yield sse("token", {"t": token})
            t3 = time.perf_counter()
        except Exception as e:
            with s.lock:
                if chat["messages"] and chat["messages"][-1].get("role") == "user":
                    chat["messages"].pop()
                if not chat["messages"]:
                    s.chats.pop(chat["id"], None)   # don't leave an empty chat in Recent
            yield sse("error", {"message": str(e)})
            return

        # Which sentence of each cited source the answer relies on (meaning, not word overlap).
        try:
            highlights = highlight.best_sentences(rag.vs_manager.embeddings, full, [s["text"] for s in sources])
        except Exception:
            highlights = {}                      # the drawer falls back to word matching
        for i, h in highlights.items():
            sources[i]["hl"] = h

        turns = len(history) // 2
        files = len({src["doc"] for src in sources})
        cited = cited_numbers(full, len(docs))
        trace = {
            "standalone": standalone,
            "steps": [
                ["Rephrase", f"Follow-up rewritten using the last {turns} turn{'s' if turns != 1 else ''}" if history
                 else "First question, searched as written", f"{t1 - t0:.1f}s"],
                ["Retrieve", f"{len(docs)} of {fetched} passages kept, from {files} document{'s' if files != 1 else ''}", f"{t2 - t1:.1f}s"],
                ["Answer", f"{rag.model} wrote {count_tokens(full, rag.model):,} tokens, citing {len(cited)} passage{'s' if len(cited) != 1 else ''}", f"{t3 - t2:.1f}s"],
            ],
            "total": f"{t3 - t0:.1f}s",
        }
        msg = {"role": "bot", "content": full, "sources": sources, "trace": trace}
        with s.lock:
            chat["messages"].append(msg)
            chat["history"] = (chat["history"] + [HumanMessage(content=question), AIMessage(content=full)])[-config.MEMORY_WINDOW * 2:]
        yield sse("done", {"trace": trace, "docCount": n_docs, "highlights": highlights})

    return StreamingResponse(run(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/export")
def export_chat(chat_id: str = Query(...), sid: str = Query(...)):
    s = session(sid)
    c = s.chats.get(chat_id)
    if not c:
        raise HTTPException(404, "No such chat")
    lines = [f"# {c['title']}", f"*Exported from RAGNAROK, {datetime.now():%Y-%m-%d %H:%M}*", ""]
    for m in c["messages"]:
        if m["role"] == "user":
            lines += ["---", "", f"**You:** {m['text']}", ""]
            continue
        lines += [f"**RAGNAROK:** {m['content']}", ""]
        cited = cited_numbers(m["content"], len(m["sources"]))
        if cited:
            lines.append("**Sources**")
            lines += [f"- [Source {n}] {m['sources'][n - 1]['doc']} · {m['sources'][n - 1]['loc']}" for n in cited]
            lines.append("")
    return Response("\n".join(lines), media_type="text/markdown",
                    headers={"Content-Disposition": f'attachment; filename="ragnarok_chat_{chat_id}.md"'})


@app.post("/api/eval")
def run_eval(request: Request, body: dict = Body(...), x_session: str = Header(None)):
    from core import evaluation

    s = session(x_session)
    need_keys()
    rate_limit("eval", request)
    questions = [q.strip() for q in str(body.get("questions") or "").splitlines() if q.strip()]
    if not questions:
        raise HTTPException(400, "Add at least one question")
    if not s.docs:
        raise HTTPException(409, "Index at least one document first")
    rag = chain_for(s)

    def run():
        try:
            for ev in evaluation.run(rag, questions):
                if ev["type"] == "result":
                    rows = ev["rows"]
                    keys = [k for k, _, _ in evaluation.METRICS]
                    means = []
                    for key, label, hint in evaluation.METRICS:
                        vals = [r["scores"][key] for r in rows if r["scores"][key] is not None]
                        means.append({"key": key, "label": label, "hint": hint,
                                      "value": sum(vals) / len(vals) if vals else None})
                    s.eval = {"rows": rows, "means": means, "keys": keys,
                              "ranAt": datetime.now().strftime("%H:%M"), "n": len(rows)}
                    yield sse("result", s.eval)
                else:
                    yield sse(ev["type"], ev)
        except Exception as e:
            yield sse("error", {"message": f"RAGAS evaluation failed: {e}"})

    return StreamingResponse(run(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/eval.csv")
def eval_csv(sid: str = Query(...)):
    from core.evaluation import METRICS

    s = session(sid)
    if not s.eval:
        raise HTTPException(404, "No evaluation yet")
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["question", "answer"] + [k for k, _, _ in METRICS])
    for r in s.eval["rows"]:
        w.writerow([r["question"], r["answer"]] + ["" if r["scores"][k] is None else f"{r['scores'][k]:.4f}" for k, _, _ in METRICS])
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="ragnarok_eval_results.csv"'})


# ── Frontend ──────────────────────────────────────────────────────────────────

@app.get("/")
def index():
    return FileResponse(WEB / "index.html", headers={"Cache-Control": "no-cache"})


app.mount("/static", StaticFiles(directory=WEB), name="static")
