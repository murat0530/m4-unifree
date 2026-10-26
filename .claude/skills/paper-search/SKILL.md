---
name: paper-search
description: Search, download, and read academic papers from 20+ sources (arXiv, PubMed, Semantic Scholar, OpenAlex, Crossref, etc.), including sorting by citation count. Use when the user asks to find papers, search research or academic literature, find most-cited papers, download a paper PDF, or extract text from a paper. Turkish triggers: makale bul, literatür taraması, en çok atıf alan makaleler, akademik yayın ara, PDF indir.
---


# Paper Search

Search, download, and read academic papers via the `paper-search` CLI.

## CLI Usage

All commands run via:
```bash
paper-search <command> [args]
```

## Setup (run once per session)

Check first: `paper-search --help`. If the command is missing, install it:
```bash
pip install --quiet --force-reinstall "git+https://github.com/openags/paper-search-mcp.git"
```
Install from GitHub, not plain `pip install paper-search-mcp`: the PyPI release (0.1.4) is outdated and
lacks `--sort` and the `tool` subcommand. Verify with `paper-search -h` (must list `tool`).
If GitHub is unreachable, fall back to `pip install paper-search-mcp` and skip `--sort` / `tool`.
If install or searches fail with network/proxy errors (403, connection refused), tell the user
(in their language) that code-execution network access must allow these domains, or "All domains":
pypi.org, files.pythonhosted.org, github.com, codeload.github.com, api.openalex.org, api.crossref.org, export.arxiv.org, arxiv.org,
eutils.ncbi.nlm.nih.gov, www.ebi.ac.uk, api.semanticscholar.org, api.unpaywall.org.

Optional API keys go in `~/.config/paper-search-mcp/.env` (e.g. `PAPER_SEARCH_MCP_UNPAYWALL_EMAIL`,
`PAPER_SEARCH_MCP_SEMANTIC_SCHOLAR_API_KEY`). Never invent keys; ask the user if one is needed.

### API keys and rate limits

Without keys, OpenAlex and Semantic Scholar often return HTTP 429: OpenAlex gives keyless requests a
small free daily budget shared by everyone on the same IP (resets at midnight UTC), and Semantic
Scholar shares one anonymous pool. On cloud machines with shared egress IPs this budget is usually gone.
Check before searching:
```bash
python3 <skill_dir>/scripts/cite_rank.py status
```
The CLI reads these environment variables automatically (prefix optional):
`PAPER_SEARCH_MCP_OPENALEX_API_KEY` and `PAPER_SEARCH_MCP_SEMANTIC_SCHOLAR_API_KEY`. Both keys are
free, but the user must sign up themselves (openalex.org; semanticscholar.org/product/api). Tell them
to add keys to their environment settings or `.env`, never to paste keys into the chat. Do not try to
bypass rate limits (rotating IPs, proxies, many emails); use the keyless fallbacks below instead.

### Search
```bash
paper-search search "<query>" -n <max_per_source> -s <sources> -y <year>
```
- `-n`: results per source (default: 5)
- `-s`: comma-separated sources, "fast", "fastest", or "all" (default: all)
- `--exhaustive`: compatibility no-op (broad search is already the default); explicit `-s` always takes precedence
- `-y`: year filter for Semantic Scholar (e.g. "2020", "2018-2022")

For speed, use `-s fast` (OpenAlex, Crossref, arXiv, PubMed, Europe PMC; also Semantic Scholar when its API key is nonblank) or `-s fastest` (OpenAlex and Crossref). Explicit source choices are never expanded, even for DOI queries. Use `-s unpaywall` for DOI lookup; "all" already includes it. These presets do not enable optional paid sources.

### Download PDF
```bash
paper-search download <source> <paper_id> [-o ./downloads]
```

### Read (extract text)
```bash
paper-search read <source> <paper_id> [-o ./downloads]
```

### List sources
```bash
paper-search sources
```

### MCP tools from the CLI

`paper-search tool` calls the same registered tools as the MCP server, including
source-specific options and DOI lookup. Required arguments are positional;
optional arguments use kebab-case flags. Boolean flags use `--flag` and
`--no-flag`; omitted options retain their MCP defaults.

```bash
paper-search tool --help
paper-search tool --list  # JSON tool list, schemas, and annotations
paper-search tool search_crossref --help
paper-search tool search_crossref "transformer attention" --filter from-pub-date:2024-01-01 --sort published --order desc --max-results 2
paper-search tool get_crossref_paper_by_doi 10.1038/nature12373
paper-search tool search_iacr "cryptography" --no-fetch-details
```

Objects and lists return JSON; text and download paths return plain text. An
exception returns a JSON error with exit code 1; invalid CLI syntax exits with
code 2. A normal MCP result retains its original meaning, including error or
partial-result fields returned by the tool itself. `--list` shows only tools
enabled by the current configuration, so IEEE tools still require their API
key. The existing `search`, `download`, `read`, and `sources` commands are
unchanged. Tool calls keep the MCP tools' source selection and timeout behavior;
Sci-Hub fallback remains opt-in through `--use-scihub`.

## Output

`search` and `download` return JSON. `read` returns plain text. Config warnings go to stderr and can be ignored.

## Sources

arxiv, pubmed, biorxiv, medrxiv, google_scholar, iacr, semantic, crossref, openalex, pmc, core, europepmc, dblp, openaire, citeseerx, doaj, base, zenodo, hal, ssrn, openreview, unpaywall, acm

Optional (env vars): ieee (`IEEE_API_KEY`). ACM search is keyless and uses Crossref metadata; publisher PDF access may require the OA fallback.

Web of Science (`wos`) and Scopus (`scopus`) require their runtime API keys and
explicit source selection; they are never added to `all`, `fast`, or `fastest`.
Use `--wos-db` or the `--scopus-view`, `--scopus-sort`, `--scopus-field`, and
`--scopus-date` options on ordinary search, or inspect their corresponding tool
help. `read scopus <id>` returns structured abstract metadata; `--full-text`
explicitly attempts identity-verified article text and returns a nonzero exit
when full text remains unavailable. An abstract-only result is not full text.

The tool command also exposes `get_citing_papers`, `get_referenced_papers`,
`get_search_cache_status`, and `clear_search_cache`. Relationship lookups accept
DOIs/OpenAlex IDs, with bounded one-hop retrieval. Caching is off by default;
enabling it persists queries and public results, and requires an explicit
operator choice. Clearing the search cache does not remove downloaded PDFs.

## Most-cited papers

`--sort citations` only re-orders the top `-n` relevance hits fetched from each source; it does NOT
return the globally most-cited papers. To approximate "most cited on topic X":

1. Pull a large relevance pool from sources that report citation counts:
   ```bash
   paper-search search "<english query>" -s openalex,semantic,crossref --sort citations -n 40
   ```
   If `cite_rank.py status` shows 429 for these sources, use the keyless fallbacks below instead.
   (An OpenAlex email no longer avoids 429s: the keyless budget is per IP.)
2. Drop off-topic hits: keep only papers whose title/abstract is actually about the topic.
3. Deduplicate by DOI/title, then rank by citations and show the top N.

Do not use Crossref server-side sort (`tool search_crossref ... --sort is-referenced-by-count`) with a
plain keyword query: Crossref matches words loosely and returns famous unrelated papers. Use it only
with narrowing filters (e.g. `--filter from-pub-date:2020-01-01,type:journal-article`) and still check relevance.

### Keyless fallbacks (use when `status` shows 429 for OpenAlex / Semantic Scholar)

`scripts/cite_rank.py` uses only the Python standard library and needs no keys. `<skill_dir>` is this
skill's base directory (e.g. `.claude/skills/paper-search` in a project).

- **Biomedical / health topics: Europe PMC, sorted server-side by citations.** This returns the
  genuinely most-cited matches, not a re-ordered top-N:
  ```bash
  python3 <skill_dir>/scripts/cite_rank.py epmc 'TITLE:"weight gain" AND (TITLE:underweight OR TITLE:"constitutional thinness") AND NOT (TITLE:pregnan* OR TITLE:anorexi*)' -n 25
  ```
  Use Europe PMC query syntax (`TITLE:`, `ABSTRACT:`, `AND`/`OR`/`NOT`, quotes, `*`) to keep results on topic.
- **Any topic: fill in missing citation counts.** PubMed/Europe PMC/arXiv results from
  `paper-search search` have no or zero citation counts. Pipe them through `enrich`, which dedupes,
  adds counts from iCite (NIH, by PMID), OpenCitations or Crossref (by DOI), and sorts:
  ```bash
  paper-search search "<query>" -s crossref,pubmed,europepmc -n 40 2>/dev/null \
    | python3 <skill_dir>/scripts/cite_rank.py enrich --top 20
  ```
  Each paper gets a `citation_source` field. `enrich` makes one request per DOI not found in iCite
  (capped by `--max-doi-lookups`, default 60), so large pools take ~30 s.

Citation counts differ by database (Crossref > OpenCitations; iCite counts only PubMed-indexed citers);
label each count's source, and say clearly that this is an approximation, not an official ranking
(Scopus/WoS are authoritative).

## Workflow

1. Search with targeted sources to find papers (translate non-English queries to English search terms; most indexes are English)
2. Present results as a table: title, authors, year, citations (if available), source, DOI/URL. Reply in the user's language.
3. If the user wants full text, use `read <source> <paper_id>`
4. If the user wants the PDF, use `download <source> <paper_id>` and report the saved path

## Credit

Based on openags/paper-search-mcp (MIT License).
