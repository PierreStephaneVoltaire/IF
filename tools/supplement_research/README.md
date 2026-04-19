# supplement_research

Hybrid retrieval (BM25 + vector) over the Examine.com-style supplement research PDF corpus. Specialist-scope only — not exposed to the main agent.

Used by: `research_assistant`, `health_write`.

## S3 layout

PDFs live under the existing powerlifting bucket with a dedicated prefix:

```
s3://$POWERLIFTING_S3_BUCKET/supplement-research/
├── strength/
│   ├── creatine.pdf
│   └── citrulline.pdf
├── hypertrophy/
├── sleep/
│   ├── ashwagandha.pdf
│   └── magnesium.pdf
├── recovery/
├── cognition/
├── longevity/
└── general/       # catch-all; used when the PDF sits at the prefix root
```

The first path segment after `supplement-research/` becomes the context tag. PDFs dropped at the prefix root are tagged `general`.

Valid context tags: `strength`, `hypertrophy`, `sleep`, `recovery`, `cognition`, `longevity`, `general`.

## Behavior

First `supplement_search` call of the process lifetime lazy-initializes:

1. Pulls all PDFs from `s3://$POWERLIFTING_S3_BUCKET/supplement-research/**.pdf` into `$SUPPLEMENT_PDF_DIR`.
2. Extracts text via Apache Tika.
3. Chunks at ~500 tokens with 50-token overlap.
4. Embeds via `all-MiniLM-L6-v2` (384-dim).
5. Writes rows to a LanceDB table at `$SUPPLEMENT_DATA_DIR`.
6. Builds a Tantivy-backed FTS index on the `text` column.

Incremental updates: SHA256 hashes of each PDF are cached in `.index_hashes.json` next to the LanceDB table. Unchanged files are skipped on subsequent inits.

## Rebuild

```json
{"query": "creatine loading", "rebuild": true}
```

Wipes the LanceDB table and the hash file, then re-pulls and re-indexes the entire S3 prefix. Takes minutes; log lines mark start/end.

## Search

Hybrid search via LanceDB's native FTS + vector ANN, reranked with RRF:

```
table.search(query_type="hybrid")
    .vector(embedding)
    .text(query)
    .rerank(RRFReranker())
    .limit(top_k)
```

Optional `filter_context` applies a `WHERE context = '<tag>'` filter before ranking.

## Result shape

```json
{
  "text": "...",
  "source_pdf": "creatine.pdf",
  "source_key": "supplement-research/strength/creatine.pdf",
  "context": "strength",
  "chunk_index": 12,
  "score": 0.0234
}
```

## Environment

| Var | Default | Purpose |
|-----|---------|---------|
| `POWERLIFTING_S3_BUCKET` | required | S3 bucket holding PDFs |
| `SUPPLEMENT_S3_PREFIX` | `supplement-research/` | Key prefix inside the bucket |
| `SUPPLEMENT_DATA_DIR` | `./data/supplement-research.lancedb` | LanceDB table location |
| `SUPPLEMENT_PDF_DIR` | `./data/supplement-research-pdfs` | Local PDF cache |
