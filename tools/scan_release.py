#!/usr/bin/env python3
"""Release scanner — four-layer secret/PII scan before publishing this repo.

Layers: (1) every tracked working-tree file; (2) every blob in every commit,
decompressing committed .gz (grep and `git log -S` cannot see inside
compressed blobs); (3) credential-shaped patterns; (4) PII (emails).

Read-only. Masks all match content in output; writes a masked report to
tmp/ (gitignored). Used for the 2026-09-11 post-freeze scan (found the two
cloudflared token traces; see docs/agentic-process/AGENTIC-PROCESS.md §5).

Run: python3 tools/scan_release.py
"""
import datetime
import gzip
import re
import subprocess
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
REPORT = REPO / "tmp" / f"release-scan-{datetime.date.today():%Y%m%d}.txt"

PATTERNS = [
    ("cloudflared-token", re.compile(rb"--token\s+[A-Za-z0-9_\-\.]{30,}")),
    ("jwt-long", re.compile(rb"eyJ[A-Za-z0-9_\-]{40,}")),
    ("sk-key", re.compile(rb"sk-[A-Za-z0-9]{16,}")),
    ("github-pat", re.compile(rb"ghp_[A-Za-z0-9]{20,}")),
    ("hf-token", re.compile(rb"hf_[A-Za-z0-9]{20,}")),
    ("aws-key", re.compile(rb"AKIA[0-9A-Z]{12,}")),
    ("private-key", re.compile(rb"BEGIN [A-Z ]{0,20}PRIVATE KEY")),
    ("cookie-hdr", re.compile(rb"Cookie:\s*[A-Za-z0-9%_\-\.=]{35,}")),
    ("authz-hdr", re.compile(rb"Authorization:\s*(?:Bearer\s+)?[A-Za-z0-9%_\-\.=]{30,}")),
    ("supabase-key", re.compile(rb"sbp_[a-z0-9]{20,}")),
]
EMAIL_RE = re.compile(rb"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


def mask(b: bytes) -> bytes:
    if len(b) <= 10:
        return b[:2] + b"..."
    return b[:4] + b"[...]" + b[-3:] + b"(len=" + str(len(b)).encode() + b")"


def scan_bytes(data: bytes, label: str, out: list, hits: list, emails: set):
    for name, rx in PATTERNS:
        for m in rx.finditer(data):
            ctx = data[max(0, m.start() - 60):m.end() + 60]
            ctx_masked = ctx.replace(m.group(0), mask(m.group(0)))
            out.append(f"{label} :: {name} :: {ctx_masked[:200]!r}")
            hits.append((name, label))
    for m in EMAIL_RE.finditer(data):
        emails.add(m.group(0).decode("utf8", "replace"))


def main():
    out, hits, blob_hits, emails = [], [], [], set()

    files = [f for f in subprocess.run(
        ["git", "ls-files", "-z"], cwd=REPO, capture_output=True).stdout.split(b"\0") if f]
    for fb in files:
        p = REPO / fb.decode()
        if not p.is_file():
            continue
        data = p.read_bytes()
        if data[:2] == b"\x1f\x8b":
            try:
                data = gzip.decompress(data)
            except Exception as e:
                out.append(f"TREE:{fb.decode()} :: GZ-DECOMPRESS-FAIL {e}")
                continue
        scan_bytes(data, "TREE:" + fb.decode(), out, hits, emails)
    print(f"working-tree: {len(files)} tracked files scanned")

    objs = subprocess.run(["git", "rev-list", "--objects", "--all"],
                          cwd=REPO, capture_output=True).stdout
    pairs = []
    for line in objs.split(b"\n"):
        if not line.strip():
            continue
        parts = line.split(b" ", 1)
        pairs.append((parts[0].decode(), parts[1].decode() if len(parts) > 1 else ""))
    inp = ("\n".join(s for s, _ in pairs) + "\n").encode()
    bc = subprocess.run(["git", "cat-file", "--batch-check"], cwd=REPO,
                        input=inp, capture_output=True).stdout.decode(errors="replace")
    types = {}
    for line in bc.splitlines():
        f = line.split()
        if len(f) >= 2:
            types[f[0]] = f[1]
    seen, uniq = set(), []
    for s, path in pairs:
        if types.get(s) == "blob" and s not in seen:
            seen.add(s)
            uniq.append(s)
    print(f"history: {len(pairs)} objects, {len(uniq)} unique blobs")

    B = 400
    gz_scanned = 0
    for i in range(0, len(uniq), B):
        chunk = uniq[i:i + B]
        pr = subprocess.run(["git", "cat-file", "--batch"], cwd=REPO,
                            input=("\n".join(chunk) + "\n").encode(), capture_output=True)
        data = pr.stdout
        pos = 0
        for sha in chunk:
            nl = data.find(b"\n", pos)
            header = data[pos:nl].split()
            size = int(header[2])
            body = data[nl + 1: nl + 1 + size]
            pos = nl + 1 + size + 1
            scan_bytes(body, "BLOB:" + sha, out, blob_hits, emails)
            if body[:2] == b"\x1f\x8b":
                gz_scanned += 1
                try:
                    raw = gzip.decompress(body)
                except Exception:
                    raw = None
                if raw is not None:
                    scan_bytes(raw, "BLOB-GZ:" + sha, out, blob_hits, emails)
    print(f"gz blobs decompressed+scanned: {gz_scanned}")
    print(f"blob scan hits: {len(blob_hits)}")
    print("by pattern:", dict(Counter(n for n, _ in blob_hits)))
    cf = sorted(set(l for n, l in blob_hits if n == "cloudflared-token"))
    cft = sorted(set(l for n, l in hits if n == "cloudflared-token"))
    print(f"cloudflared-token hits: tree={cft} blobs={cf}")

    print("\n-- unique emails (for PII adjudication) --")
    for e in sorted(emails):
        print("  ", e)

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(out)[:2_000_000])
    print("\nreport written:", REPORT)


if __name__ == "__main__":
    main()
