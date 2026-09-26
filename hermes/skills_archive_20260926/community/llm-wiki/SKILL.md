---
name: llm-wiki
category: community
description: "Karpathy's LLM Wiki: build/query interlinked markdown KB. (moved from research)"
---

# LLM Wiki — Interlinked Markdown Knowledge Base

Build and query an interlinked markdown knowledge base following Andrej Karpathy's "LLM Wiki" concept. A personal wiki of markdown files linked via `[[wiki-links]]`, optimized for LLM context retrieval.

## When to use

- You want to build a personal knowledge base that an LLM can effectively query
- You need to store structured information in markdown with cross-references
- You're organizing research notes, project docs, or learning materials in a wiki format
- You want to leverage `[[wiki-links]]` for easy navigation and context stitching

## Structure

```
llm-wiki/
├── index.md              # Root index with links to all major topics
├── concepts/
│   ├── attention.md
│   ├── transformers.md
│   └── fine-tuning.md
├── papers/
│   ├── attention-is-all-you-need.md
│   └── gpt-3.md
├── tools/
│   ├── pytorch.md
│   └── huggingface.md
└── projects/
    └── my-research.md
```

## Wiki Link Convention

Use `[[Page Name]]` or `[[Page Name|display text]]` for cross-references:

```markdown
# Attention Mechanism

The [[Transformer]] architecture relies heavily on [[Multi-Head Attention]].
See also: [[Self-Attention|scaled dot-product attention]].
```

## Index File Pattern

```markdown
# LLM Wiki Index

## Concepts
- [[Attention Mechanism]] — core building block
- [[Transformer]] — the architecture
- [[Fine-tuning]] — adapting pretrained models

## Papers
- [[Attention Is All You Need]] — Vaswani et al. 2017
- [[GPT-3]] — Brown et al. 2020

## Tools
- [[PyTorch]] — deep learning framework
- [[Hugging Face Transformers]] — model library
```

## Querying the Wiki

When querying with an LLM, include the relevant wiki pages in context:

```
Based on my LLM Wiki, explain how the attention mechanism works.
Relevant pages:
[[concepts/attention.md]]
[[concepts/transformers.md]]
```

Or for full-wiki context retrieval, concatenate related pages:

```bash
cat llm-wiki/concepts/*.md > _context.md
```

## Best Practices

- Keep each page focused on one topic (single responsibility)
- Use `[[Page Name]]` links generously — they help LLMs navigate context
- Start every page with a one-paragraph summary (serves as the "abstract")
- Use consistent heading hierarchy: `# Title`, `## Section`, `### Subsection`
- Tag pages with categories in frontmatter if you want structured metadata
- Periodically review the index to ensure all new pages are linked

## Pitfalls

- Orphan pages (no incoming links) are hard for LLMs to discover — always link from index or related pages
- Very deep hierarchies (>3 levels) make retrieval harder — flatten where possible
- Avoid duplicate content across pages — use `[[wiki-links]]` instead of copying text
- Markdown formatting is preserved in context — use tables, code blocks, and lists for structured data

## Verification

After building the wiki, verify by following every `[[link]]` from the index page to ensure all targets exist and the graph is connected.
