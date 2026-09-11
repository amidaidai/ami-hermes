---
name: arxiv
category: community
description: Search arXiv papers by keyword, author, category, or ID. (moved from research)
---

# arXiv — Search Academic Papers

Search and retrieve papers from arXiv (arxiv.org) by keyword, author, category, or paper ID using the arXiv API.

## When to use

- You need to find recent papers on a specific topic
- You want to look up papers by a known author
- You're doing literature review or related work analysis
- You need to retrieve paper metadata (title, authors, abstract, PDF link)

## Requirements

- Internet access to `export.arxiv.org`
- Python with `requests` and `feedparser` (or the `arxiv` Python package)
- Respect arXiv API rate limits (~1 request per few seconds for bulk queries)

## Usage

### Search by keyword (using arxiv Python package)

```python
import arxiv

search = arxiv.Search(
  query="transformer attention mechanism",
  max_results=10,
  sort_by=arxiv.SortCriterion.Relevance
)

for result in search.results():
    print(f"Title: {result.title}")
    print(f"Authors: {', '.join(a.name for a in result.authors)}")
    print(f"Published: {result.published}")
    print(f"PDF: {result.pdf_url}")
    print(f"Abstract: {result.summary[:200]}...")
    print("---")
```

### Search by author

```python
import arxiv

search = arxiv.Search(query="au:Karpathy", max_results=5)
for r in search.results():
    print(f"{r.title} ({r.entry_id})")
```

### Search by category

```python
import arxiv

search = arxiv.Search(query="cat:cs.CL AND abs:reasoning", max_results=20)
for r in search.results():
    print(f"[{r.primary_category}] {r.title}")
```

### Fetch by specific ID

```python
import arxiv

paper = next(arxiv.Search(id_list=["2302.13971"]).results())
print(f"Title: {paper.title}")
print(f"Abstract: {paper.summary}")
```

### Using raw API (no external package)

```python
import requests, feedparser

url = "http://export.arxiv.org/api/query"
params = {
    "search_query": "ti:deep learning AND cat:cs.LG",
    "start": 0,
    "max_results": 5
}
feed = feedparser.parse(requests.get(url, params=params).text)
for entry in feed.entries:
    print(entry.title)
    print(entry.summary[:150] + "...")
    print(entry.links[0].href if entry.links else "No link")
    print()
```

## Query Syntax

- `au:` — author (e.g., `au:Karpathy`)
- `ti:` — title (e.g., `ti:attention`)
- `abs:` — abstract (e.g., `abs:reinforcement learning`)
- `cat:` — category (e.g., `cat:cs.CL`, `cat:stat.ML`)
- `all:` — all fields
- Combine with `AND`, `OR`, `ANDNOT`
- Group with parentheses

## Common Categories

| Code | Area |
|------|------|
| cs.AI | Artificial Intelligence |
| cs.CL | Computation and Language |
| cs.CV | Computer Vision |
| cs.LG | Machine Learning |
| stat.ML | Machine Learning (Statistics) |
| cs.NE | Neural and Evolutionary Computing |
| cs.IR | Information Retrieval |

## Pitfalls

- Expect 401/403 if rate limit is hit — insert `time.sleep(3)` between bulk requests
- Abstracts are truncated by the API (~700 chars) — use the `abs:` prefix for full text queries
- The `arxiv` package requires installation: `pip install arxiv`
- Old papers may have non-standard IDs (like `astro-ph/1234567`)

## Verification

Run a simple search and verify that result titles and authors match what you'd see on arxiv.org for the same query.
