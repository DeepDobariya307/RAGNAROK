---
title: RAGNAROK
emoji: 📚
colorFrom: green
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
---

# RAGNAROK

**Ask questions across your own documents and see exactly where every answer came from.**

Upload PDFs, Word files, spreadsheets or images, ask in plain language, and get an answer with numbered citations. Click a citation to see the source passage, with the sentence closest to the cited claim highlighted.

**Live demo:** [huggingface.co/spaces/DeepDobariya307/RAGNAROK](https://huggingface.co/spaces/DeepDobariya307/RAGNAROK)

---

## What it does

- **Many file types.** PDF (text and tables), Word, Excel, CSV, plain text, and images (photos, scans and handwriting are read with GPT-4o vision).
- **Cited answers.** Every claim carries a numbered badge. Clicking it opens the source passage, its location (page, sheet and rows) and a similarity score.
- **Follow-up questions.** Follow-ups like "and how much of it do we hold?" are rewritten into full questions before searching, using the last 5 turns.
- **Transparent pipeline.** "How this was found" shows each step (rephrase, retrieve, answer) with timings and passage counts.
- **Built-in evaluation.** Scores the pipeline with RAGAS (faithfulness, answer relevancy, context precision). No reference answers needed.
- **Adjustable retrieval.** Settings changes the model, how many passages are used, and the relevance-versus-variety balance (MMR).
- **Private sessions.** Each browser tab gets its own Pinecone namespace, so users never see each other's documents.

## How it works

```
Upload ─► Read & split ─► Embed ─► Pinecone
          (800-char chunks,  (text-embedding-3-large,
           tables kept whole)  3072 dims)

Question ─► Rewrite follow-up ─► Search 30 passages ─► Keep 15 with MMR ─► GPT-4o answers
            (chat history)       (cosine similarity)   (relevant + varied)  with [Source N] citations
```

## Run it locally (Windows)

1. Install **Python 3.12** from [python.org](https://www.python.org/downloads/).
2. Double-click **`start.bat`**.
   - The first run installs everything, which takes a few minutes.
   - It then opens a `.env` file. Paste in your [OpenAI](https://platform.openai.com/api-keys) and [Pinecone](https://app.pinecone.io) keys, save, and double-click `start.bat` again.
3. RAGNAROK opens at **http://localhost:7860**. Close the black window to stop it.

On Mac or Linux:

```bash
python3.12 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then add your keys
uvicorn server:app --port 7860
```

## Project structure

```
server.py        Web server and API (FastAPI)
config.py        All settings in one place
core/
  document_processor.py   Reads each file type and splits it into passages
  vector_store.py         Pinecone storage and MMR search
  rag_chain.py            Rewrites the question, retrieves, and streams the answer
  evaluation.py           RAGAS scoring
web/             The interface (HTML, CSS, JavaScript)
start.bat        One-click start on Windows
Dockerfile       Used by Hugging Face Spaces
```

## Tech stack

| Layer | Technology |
|---|---|
| Language model | OpenAI GPT-4o (or GPT-4o-mini, switchable) |
| Embeddings | OpenAI text-embedding-3-large |
| Vector database | Pinecone serverless |
| RAG pipeline | LangChain (LCEL) |
| Evaluation | RAGAS |
| Backend | FastAPI, streaming answers over server-sent events |
| Frontend | Plain HTML, CSS and JavaScript |
| Deployment | Docker on Hugging Face Spaces |

## Deploy your own

1. Create a new Space on Hugging Face and choose **Docker**.
2. Push this repository to it.
3. In the Space's **Settings → Secrets**, add `OPENAI_API_KEY` and `PINECONE_API_KEY`.

## Limitations

- Chats and uploaded documents are kept in server memory, so a restart clears them.
- Answers are only as good as the retrieved passages. Questions about document metadata (for example "how many pages is each file?") aren't answered, because that information isn't in the text.
