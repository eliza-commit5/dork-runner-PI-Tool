# dork_runner

A small command-line tool for open-source investigations. It runs a list of search queries ("dorks") through the open-source [`ddgs`](https://pypi.org/project/ddgs/) metasearch library and logs every result for the case file: a CSV of all hits, including searches that returned nothing or errored, a summary that lists flagged hits first, and a SHA-256 hash record of the outputs.

**Every result is a lead, not evidence.** Open each hit yourself, confirm identity, and capture the page with its URL and date visible before you use it.

## Setup

Requires Python 3.9+.

```powershell
py -m pip install --user ddgs
```

On Windows, use `py` rather than `python` if `python` opens the Microsoft Store.

## Usage

```powershell
py dork_runner.py dorks_<case>.txt
py dork_runner.py dorks_<case>.txt --max 20 --delay 15
```

| Option | Default | Purpose |
|---|---|---|
| `--max` | 15 | Max results per search |
| `--delay` | 6 | Base seconds between searches; raise this if you get blocked |
| `--backend` | auto | ddgs backend, such as `duckduckgo`, `bing`, or `brave` |
| `--out-dir` | `.` | Folder for output files |

Keep runs to roughly 15–40 queries. Larger runs tend to get rate-limited.

## Dork file format

A UTF-8 text file with one search per line. A byte-order mark (BOM) from PowerShell is handled.

```
# comment                      -> ignored
@case: 00-0000000 EXAMPLE      -> case label written on every row
@subject: Jane Q. Example      -> tags the searches below it
@flag: example, smallville     -> keywords that mark a likely hit (reset per subject)
site:facebook.com "Jane Example" Smallville
```

See [`examples/dorks_example.txt`](examples/dorks_example.txt). Every name in it is fictitious.

## Outputs

All outputs share one timestamp.

- `dork_results_<stamp>.csv`: every query and result, with its domain, flag matches, the row where a duplicate URL first appeared, and a status
- `dork_summary_<stamp>.txt`: per-subject counts, with flagged hits listed first
- `dork_hashes_<stamp>.txt`: SHA-256 hashes of the CSV, the dork file, and the summary

Store these unaltered in the case folder.

## Responsible use

- Search public results only. Don't follow, friend, like, or message subjects, and don't use pretext accounts.
- Never put SSNs, driver's license numbers, or account numbers in queries. That sends protected data to third-party search engines.
- Search engines and ddgs backends treat `OR` and parentheses differently. Re-check key searches by hand.
- Comply with the laws and licensing rules that apply to you.

## Keeping case data out of this repo

`.gitignore` excludes real dork files (`dorks_*.txt`) and all outputs. Keep working case files in your case folders, not in this repo.
