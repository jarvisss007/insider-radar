"""ATOMIC BOOKS — one way to rewrite a shared book (BOOK-001, 2026-09-07).

Labor Day 2026-09-07, 11:12 PT: the Mac woke, the app fired every task it had missed on
Sunday at once, and ipo_radar.py read agent/ipo_strategy.csv while another process was
rewriting it — open(path, "w") truncates first, so the reader saw an EMPTY file, rebuilt
the book from scratch, and wrote 9 rows over 27. Two rulings' columns vanished with it.

Two rules, both mechanical:
  * a book is never truncated in place: write the whole file beside it, fsync, then
    os.replace() — a reader sees the old book or the new one, never nothing;
  * a read-modify-write holds the book's lock from the first read to process exit, so two
    writers cannot interleave (one waits, at most LOCK_TIMEOUT_S, then fails LOUD).

MIRROR: zero-dte-lab/src/atomicio.py is a byte-identical copy (CI runs that repo alone);
the resolver check books_write_atomically fails if the two ever differ.
"""
import atexit, csv, fcntl, io, json, os, time

LOCK_TIMEOUT_S = 120
_HELD = {}


def atomic_write_text(path, text):
    tmp = f"{path}.tmp.{os.getpid()}"
    with open(tmp, "w", newline="") as f:
        f.write(text); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)


def atomic_json(path, obj, **kw):
    atomic_write_text(path, json.dumps(obj, **kw))


def atomic_csv(path, fieldnames, rows, **kw):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fieldnames, **kw); w.writeheader(); w.writerows(rows)
    atomic_write_text(path, buf.getvalue())


def hold_book(path, timeout=LOCK_TIMEOUT_S):
    """Take the book's exclusive lock for the life of this process (idempotent per path).
    Fails LOUD after `timeout` seconds rather than writing over a book someone else holds."""
    path = os.path.abspath(path)
    if path in _HELD: return
    fd = os.open(path + ".lock", os.O_CREAT | os.O_RDWR, 0o644)
    t0 = time.time()
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB); break
        except BlockingIOError:
            if time.time() - t0 > timeout:
                os.close(fd)
                raise SystemExit(f"REFUSED: {os.path.basename(path)} is held by another writer for >{timeout}s — not writing over it (BOOK-001)")
            time.sleep(0.5)
    _HELD[path] = fd
    atexit.register(_release, path)


def _release(path):
    fd = _HELD.pop(path, None)
    if fd is not None:
        try: fcntl.flock(fd, fcntl.LOCK_UN); os.close(fd)
        except OSError: pass
