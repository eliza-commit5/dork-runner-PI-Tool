"""
dork_runner.py v2 - run a case dork list and log every result for the case file.

Open-source search via the `ddgs` metasearch library (MIT). Every hit is a LEAD,
not evidence: open it yourself, confirm identity, and capture the page with
URL + date before anything goes in a report.

Setup (once, PowerShell):   py -m pip install --user ddgs
Run (from the case's Dorking folder):
    py dork_runner.py dorks_<case>.txt
    py dork_runner.py dorks_<case>.txt --max 20 --delay 10

Dork file format (UTF-8 text, one search per line):
    # comment                      -> ignored
    @case: 00-0000000 EXAMPLE      -> case label written on every row
    @subject: Jane Q. Example     -> tags the searches below it
    @flag: example, smallville, sampleton
                                   -> keywords; hits containing them are marked
    site:facebook.com "Jane Example" Smallville
    (any other line is a search)

Outputs (all in --out-dir, default = current folder), same timestamp:
    dork_results_<stamp>.csv    every query + result (zero-result and error rows too)
    dork_summary_<stamp>.txt    per-subject counts + flagged hits to review first
    dork_hashes_<stamp>.txt     SHA-256 of the CSV and the dork file (integrity record)
"""

import argparse
import csv
import hashlib
import os
import random
import sys
import time
from datetime import datetime
from urllib.parse import urlparse

VERSION = "2.0"

try:
    from ddgs import DDGS
except ImportError:
    sys.exit("ddgs is not installed. Run:  py -m pip install --user ddgs")


def parse_dork_file(path):
    """Return (case, [ {subject, flags, query} ... ])."""
    case, subject, flags, jobs = "", "", [], []
    # utf-8-sig strips the byte-order mark PowerShell adds to text files.
    with open(path, encoding="utf-8-sig") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            low = line.lower()
            if low.startswith("@case:"):
                case = line.split(":", 1)[1].strip()
            elif low.startswith("@subject:"):
                subject = line.split(":", 1)[1].strip()
                flags = []  # flags reset for each new subject
            elif low.startswith("@flag:"):
                flags = [t.strip().lower() for t in line.split(":", 1)[1].split(",") if t.strip()]
            else:
                jobs.append({"subject": subject, "flags": list(flags), "query": line})
    return case, jobs


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser(description="Run a case dork list and log results to CSV.")
    ap.add_argument("dork_file", help="text file of searches (see header for format)")
    ap.add_argument("--max", type=int, default=15, help="max results per search (default 15)")
    ap.add_argument("--delay", type=float, default=6.0,
                    help="base seconds between searches (default 6; raise if blocked)")
    ap.add_argument("--backend", default="auto",
                    help="ddgs backend (default auto). Example: duckduckgo, bing, brave")
    ap.add_argument("--out-dir", default=".", help="folder for output files (default: current)")
    args = ap.parse_args()

    case, jobs = parse_dork_file(args.dork_file)
    if not jobs:
        sys.exit("No searches found in " + args.dork_file)
    os.makedirs(args.out_dir, exist_ok=True)

    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    csv_path = os.path.join(args.out_dir, f"dork_results_{stamp}.csv")
    sum_path = os.path.join(args.out_dir, f"dork_summary_{stamp}.txt")
    hash_path = os.path.join(args.out_dir, f"dork_hashes_{stamp}.txt")
    fields = ["run_timestamp", "case", "subject", "query", "rank", "title", "url",
              "domain", "snippet", "flag_hits", "first_seen_row", "status"]

    seen = {}          # url -> CSV row number where first seen
    stats = {}         # subject -> counters
    flagged = []       # (subject, flag_hits, title, url)
    row_no = 1         # header is row 1 in Excel

    print(f"dork_runner v{VERSION} | case: {case or '(none)'} | {len(jobs)} searches -> {csv_path}\n")
    ddgs = DDGS()
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as out:  # -sig so Excel reads UTF-8
        w = csv.DictWriter(out, fieldnames=fields)
        w.writeheader()
        try:
            for i, job in enumerate(jobs, 1):
                q, subj = job["query"], job["subject"] or "(untagged)"
                st = stats.setdefault(subj, {"searches": 0, "results": 0, "empty": 0,
                                             "errors": 0, "flagged": 0})
                st["searches"] += 1
                ts = datetime.now().isoformat(timespec="seconds")
                base = {"run_timestamp": ts, "case": case, "subject": subj, "query": q}
                try:
                    results = ddgs.text(q, max_results=args.max, backend=args.backend) or []
                except Exception as e:
                    msg = f"{type(e).__name__}: {e}"
                    status = "no results" if "no results" in msg.lower() else f"error: {msg}"
                    st["empty" if status == "no results" else "errors"] += 1
                    w.writerow({**base, "status": status})
                    row_no += 1
                    print(f"[{i}/{len(jobs)}] {'  0 results' if status == 'no results' else 'ERROR    '}  {q}")
                    results = None
                if results is not None:
                    if not results:
                        st["empty"] += 1
                        w.writerow({**base, "status": "no results"})
                        row_no += 1
                    for rank, r in enumerate(results, 1):
                        url = r.get("href", "")
                        title, snip = r.get("title", ""), r.get("body", "")
                        hay = f"{title} {url} {snip}".lower()
                        hits = [t for t in job["flags"] if t in hay]
                        row_no += 1
                        first = seen.setdefault(url, row_no) if url else row_no
                        w.writerow({**base, "rank": rank, "title": title, "url": url,
                                    "domain": urlparse(url).netloc,
                                    "snippet": snip, "flag_hits": "; ".join(hits),
                                    "first_seen_row": "" if first == row_no else first,
                                    "status": "ok"})
                        st["results"] += 1
                        if hits and first == row_no:
                            st["flagged"] += 1
                            flagged.append((subj, "; ".join(hits), title, url))
                    print(f"[{i}/{len(jobs)}] {len(results):>3} results  {q}")
                out.flush()
                if i < len(jobs):
                    time.sleep(args.delay + random.uniform(0, 3))
        except KeyboardInterrupt:
            print("\nStopped early (Ctrl+C). Everything run so far is saved.")

    with open(sum_path, "w", encoding="utf-8") as s:
        s.write(f"dork_runner v{VERSION} summary\nCase: {case}\nRun: {stamp}\n"
                f"Dork file: {os.path.abspath(args.dork_file)}\nResults: {os.path.abspath(csv_path)}\n\n")
        for subj, st in stats.items():
            s.write(f"{subj}: {st['searches']} searches, {st['results']} results, "
                    f"{st['empty']} empty, {st['errors']} errors, {st['flagged']} flagged\n")
        s.write("\nFLAGGED HITS (review these first; verify identity before use):\n")
        for subj, hits, title, url in flagged:
            s.write(f"- [{subj}] ({hits}) {title}\n  {url}\n")
        if not flagged:
            s.write("(none)\n")

    with open(hash_path, "w", encoding="utf-8") as h:
        for p in (csv_path, args.dork_file, sum_path):
            h.write(f"{sha256(p)}  {os.path.basename(p)}\n")

    print(f"\nDone. Review {sum_path} first, then the CSV in Excel.")
    print("Every hit is a lead: open it, confirm identity, capture URL + date.")


if __name__ == "__main__":
    main()
