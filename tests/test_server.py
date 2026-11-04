"""Server helpers: source labels, citation parsing, rate limiting, namespace naming."""
import server
from server import RateLimiter, Session, cited_numbers, location, NAMESPACE_RE


def test_location_labels():
    assert location({"source_file": "a.pdf", "type": "text", "page": 2}) == "Page 3"
    assert location({"source_file": "a.pdf", "type": "table", "page": 7, "caption": "Table 3: X"}) == "Table 3: X · page 8"
    assert location({"source_file": "h.docx", "type": "table"}) == "Table"
    assert location({"source_file": "t.xlsx", "type": "table", "row_start": 56, "row_end": 60, "sheet": "Apps"}) == "Sheet “Apps” · rows 56–60"
    assert location({"source_file": "i.png", "type": "image"}) == "Text read from image"


def test_cited_numbers_in_order_of_first_use_and_in_range():
    text = "A [Source 2]. B [Source 1, Source 2]. C [Source 7]."
    assert cited_numbers(text, 3) == [2, 1]


def test_rate_limiter():
    limiter = RateLimiter(limit=3, window=60)
    assert limiter.allow("ip", 2) and limiter.allow("ip")
    assert not limiter.allow("ip")
    assert limiter.allow("other-ip")


def test_namespace_names_carry_creation_hour():
    s = Session(id="0" * 32)
    m = NAMESPACE_RE.match(s.namespace)
    assert m and len(m.group(1)) == 10
    assert NAMESPACE_RE.match("s-" + "a" * 32)              # older format still recognised
    assert not NAMESPACE_RE.match("someone-elses-namespace")


def test_cleanup_deletes_only_old_namespaces_of_this_app(monkeypatch):
    deleted = []

    class FakeStore:
        def list_namespaces(self):
            return ["s-2020010100-" + "a" * 32, "s-" + "b" * 32, server.Session(id="c" * 32).namespace, "other-app"]

        def delete_namespace(self, ns):
            deleted.append(ns)

    monkeypatch.setattr(server, "vs", lambda: FakeStore())
    server.cleanup_namespaces()
    assert deleted == ["s-2020010100-" + "a" * 32, "s-" + "b" * 32]
