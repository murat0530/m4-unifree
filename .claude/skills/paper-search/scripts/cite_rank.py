#!/usr/bin/env python3
"""Keyless citation helpers for the paper-search skill.

Subcommands:
  status   Show which API keys are set and whether OpenAlex / Semantic Scholar answer.
  epmc     Search Europe PMC sorted server-side by citation count (no key needed).
  enrich   Fill/refresh citation counts in `paper-search search` JSON using
           iCite (PMIDs), OpenCitations and Crossref (DOIs), then sort by citations.

Standard library only, so it runs anywhere Python 3.8+ is available.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

UA = "paper-search-skill/1.0 (cite_rank.py)"
TIMEOUT = 30


def _get(url, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


def _env(name):
    return os.environ.get(f"PAPER_SEARCH_MCP_{name}") or os.environ.get(name) or ""


def _probe(url, headers=None):
    try:
        code, _ = _get(url, headers)
        return f"OK ({code})"
    except urllib.error.HTTPError as e:
        return f"HTTP {e.code}" + (" (rate limited / budget used up)" if e.code == 429 else "")
    except Exception as e:  # network errors, proxy denials
        return f"error: {e.__class__.__name__}"


def cmd_status(_args):
    oa_key = _env("OPENALEX_API_KEY")
    s2_key = _env("SEMANTIC_SCHOLAR_API_KEY")
    print(f"OPENALEX_API_KEY:         {'set' if oa_key else 'missing'}")
    print(f"SEMANTIC_SCHOLAR_API_KEY: {'set' if s2_key else 'missing'}")
    oa_headers = {"Authorization": f"Bearer {oa_key}"} if oa_key else None
    s2_headers = {"x-api-key": s2_key} if s2_key else None
    print("OpenAlex:         " + _probe("https://api.openalex.org/works?search=test&per-page=1", oa_headers))
    print("Semantic Scholar: " + _probe(
        "https://api.semanticscholar.org/graph/v1/paper/search?query=test&limit=1", s2_headers))
    print("Europe PMC:       " + _probe(
        "https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=test&format=json&pageSize=1"))
    print("Crossref:         " + _probe("https://api.crossref.org/works?query=test&rows=1"))


def cmd_epmc(args):
    params = {"query": args.query, "sort": "CITED desc", "format": "json",
              "pageSize": str(min(args.n, 1000)), "resultType": "lite"}
    url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search?" + urllib.parse.urlencode(params)
    _, data = _get(url)
    papers = []
    for r in data.get("resultList", {}).get("result", []):
        papers.append({
            "title": r.get("title"),
            "authors": r.get("authorString"),
            "year": r.get("pubYear"),
            "journal": r.get("journalTitle"),
            "doi": r.get("doi"),
            "pmid": r.get("pmid"),
            "citations": r.get("citedByCount"),
            "citation_source": "europepmc",
        })
    json.dump({"query": args.query, "hit_count": data.get("hitCount"), "papers": papers},
              sys.stdout, ensure_ascii=False, indent=2)
    print()


def _icite(pmids):
    counts = {}
    pmids = [p for p in pmids if p and str(p).isdigit()]
    for i in range(0, len(pmids), 200):
        batch = ",".join(pmids[i:i + 200])
        try:
            _, data = _get(f"https://icite.od.nih.gov/api/pubs?pmids={batch}&fl=pmid,citation_count")
            for row in data.get("data", []):
                if row.get("citation_count") is not None:
                    counts[str(row["pmid"])] = int(row["citation_count"])
        except Exception as e:
            print(f"iCite failed: {e}", file=sys.stderr)
    return counts


def _doi_count(doi):
    quoted = urllib.parse.quote(doi, safe="/")
    try:
        _, data = _get(f"https://api.opencitations.net/index/v2/citation-count/doi:{quoted}")
        if data and data[0].get("count") is not None:
            return int(data[0]["count"]), "opencitations"
    except Exception:
        pass
    try:
        _, data = _get(f"https://api.crossref.org/works/{quoted}")
        return int(data["message"].get("is-referenced-by-count", 0)), "crossref"
    except Exception:
        return None, None


def _pmid_of(p):
    for key in ("pmid", "paper_id"):
        val = str(p.get(key) or "").replace("PMID:", "").strip()
        if val.isdigit():
            return val
    return ""


def cmd_enrich(args):
    src = open(args.file) if args.file != "-" else sys.stdin
    data = json.load(src)
    papers = data["papers"] if isinstance(data, dict) else data

    # Deduplicate by DOI, falling back to a normalized title.
    seen, unique = set(), []
    for p in papers:
        key = (p.get("doi") or "").lower() or (p.get("title") or "").lower().strip()[:80]
        if key and key not in seen:
            seen.add(key)
            unique.append(p)

    icite = _icite([_pmid_of(p) for p in unique])
    lookups = 0
    for p in unique:
        old = p.get("citations")
        pmid = _pmid_of(p)
        if pmid in icite:
            p["citations"], p["citation_source"] = icite[pmid], "icite"
        elif p.get("doi") and lookups < args.max_doi_lookups:
            lookups += 1
            count, source = _doi_count(p["doi"])
            if count is not None:
                p["citations"], p["citation_source"] = count, source
        if "citation_source" not in p and old is not None:
            p["citation_source"] = p.get("source", "original")

    unique.sort(key=lambda p: p.get("citations") or 0, reverse=True)
    out = {"papers": unique[:args.top] if args.top else unique}
    json.dump(out, sys.stdout, ensure_ascii=False, indent=2)
    print()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status").set_defaults(func=cmd_status)
    e = sub.add_parser("epmc")
    e.add_argument("query", help="Europe PMC query syntax, e.g. 'TITLE:\"weight gain\" AND underweight'")
    e.add_argument("-n", type=int, default=25)
    e.set_defaults(func=cmd_epmc)
    r = sub.add_parser("enrich")
    r.add_argument("file", nargs="?", default="-", help="paper-search JSON file (default: stdin)")
    r.add_argument("--top", type=int, default=0)
    r.add_argument("--max-doi-lookups", type=int, default=60)
    r.set_defaults(func=cmd_enrich)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
