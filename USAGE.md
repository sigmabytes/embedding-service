# Indexing and Embedding Service — Usage

How to call the chunking, embedding, and indexing APIs. All configurations are **optional**, **backward compatible**, and configurable via request parameters.

**Backend config:** Defaults and profiles (chunking strategy, embedding model, indexing similarity) are defined in **static config files** on the server (e.g. `static.json` under `app/config/chunking`, `app/config/embedding`, `app/config/indexing`). Requests can override these per call; if you omit a parameter, the backend uses the value from the active profile in those static files.

---

## Sample API Requests

Base URL: your service root (e.g. `https://api.example.com`).

### 1. Chunk documents — `POST /chunk`

```json
{
  "tenant_id": "tenant-001",
  "limit": 100,
  "chunk_size": 512,
  "overlap": 50
}
```

- **Required:** `tenant_id`, `limit` (1–1000).
- **Optional:** `chunk_size` (1–10000), `overlap` (0–5000). Omit to use server defaults.

### 2. Embed chunks — `POST /embed`

Embedding config (model, normalize, preprocessing, etc.) is **set by the backend** in static config; you only send `embedding_config` in the request when you want to override.

**Minimal request (use backend defaults):**

```json
{
  "tenant_id": "tenant-001",
  "limit": 100
}
```

**With overrides (optional):**

```json
{
  "tenant_id": "tenant-001",
  "limit": 100,
  "embedding_config": {
    "model": "all-MiniLM-L6-v2",
    "normalize": true,
    "normalization_type": "L2",
    "preprocessing": {
      "lowercase": false,
      "remove_punctuation": false,
      "max_length": 8192
    }
  }
}
```

- **Required:** `tenant_id`, `limit` (1–1000).
- **Optional:** `embedding_config` — override any subset of the backend config (model, normalize, normalization_type, preprocessing, etc.). Omit to use the active profile from backend static config.

### 3. Index embeddings — `POST /index`

Indexing strategy (similarity, hnsw_config, index_settings, etc.) is **set by the backend** in static config. Use a **profile name** (e.g. `cosine_knn`) to use that profile’s settings, or send an **inline** object to override.

**Minimal request (use a backend profile by name):**

```json
{
  "tenant_id": "tenant-001",
  "index_name": "my-search-index",
  "indexing_strategy": "cosine_knn",
  "limit": 500
}
```

**With specific embedding IDs (optional):**

```json
{
  "tenant_id": "tenant-001",
  "index_name": "my-search-index",
  "indexing_strategy": "cosine_knn",
  "embedding_ids": ["emb-1", "emb-2"]
}
```

**With inline config (override backend profile):**

```json
{
  "tenant_id": "tenant-001",
  "index_name": "my-search-index",
  "indexing_strategy": {
    "similarity": "cosine",
    "hnsw_config": { "m": 16, "ef_construction": 200, "ef_search": 100 },
    "index_settings": { "number_of_shards": 1, "number_of_replicas": 1 }
  },
  "limit": 500
}
```

- **Required:** `tenant_id`, `index_name`, `indexing_strategy` (profile name, e.g. `cosine_knn`, `l2_knn`, `dot_product_knn`, or inline object to override backend config).
- **Exactly one of:** `embedding_ids` (max 1000) or `limit` (1–1000) — which embeddings to publish.

---

## Chunking

- **What:** Splits documents into smaller text segments (chunks) so they can be embedded and searched efficiently.
- **Supported strategy:** `fixed_token` — chunks by a target token count with optional overlap. Server default uses this (e.g. 512 tokens, 50 overlap). Override via request: `chunk_size`, `overlap`.
- **Why:** Embedding and similarity search work best on bounded-size units; chunking keeps context manageable and retrieval precise.

---

## Embedding

- **Model:** Default profile uses **all-MiniLM-L6-v2** (sentence-transformers). Override with `embedding_config.model` or another profile.
- **Normalization:** Vectors can be L2-normalized (`normalize: true`, `normalization_type: "L2"`). Default is L2; use when you want cosine similarity to match dot product on normalized vectors.
- **Purpose:** Converts chunk text into dense vectors for similarity search (e.g. in OpenSearch).

---

## Indexing

- **Similarity types:** `cosine`, `l2`, `dot_product`. Choose via `indexing_strategy` (profile name or inline `similarity`).
  - **cosine** — angle between vectors; good for normalized embeddings and semantic similarity.
  - **l2** — Euclidean distance; use when magnitude matters or you prefer distance-based search.
  - **dot_product** — inner product; use for normalized vectors when you want score proportional to cosine.
- **When to use:** Prefer **cosine** (or **dot_product** on normalized vectors) for typical semantic search; use **l2** if your use case is distance-based.

---

## Summary

| Area       | Configurable via                          | Defaults / notes                          |
|-----------|--------------------------------------------|-------------------------------------------|
| Chunking  | `chunk_size`, `overlap`                    | fixed_token, 512 / 50                     |
| Embedding | `embedding_config` (model, normalize, …)   | all-MiniLM-L6-v2, L2 normalize            |
| Indexing  | `indexing_strategy` (name or inline)       | e.g. cosine_knn → cosine similarity       |

All of the above are optional and backward compatible; omit any parameter to use server defaults.
