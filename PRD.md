# Product Requirements Document (PRD)
## Embedding Service for RAG System

### Document Information
- **Service Name**: Embedding Service
- **Purpose**: Prepare and publish knowledge for a RAG (Retrieval-Augmented Generation) system
- **Version**: 1.0
- **Date**: 2024

---

## 1. Executive Summary

This service is a backend service designed to prepare and publish knowledge for a RAG system. It processes cleaned content from a crawler service through three independent stages: chunking, embedding generation, and vector indexing.

### What This Service Does
- Takes cleaned content from a crawler service
- Chunks the content using configurable strategies
- Generates embeddings using different embedding models
- Stores all intermediate states in MongoDB
- Publishes vectors into OpenSearch using different indexing styles

### What This Service Does NOT Do
- Chat functionality
- Retrieval operations
- Ranking algorithms
- LLM text generation
- Session management

---

## 2. High-Level Design

### 2.1 Pipeline Architecture

The pipeline is intentionally split into three clear, independent stages:

1. **Prepare Raw Data** (Chunking)
2. **Understand Data** (Embeddings)
3. **Publish Data** (Indexing)

### 2.2 Independence Principle

Each stage must be independent so that:
- **Re-chunking** does not require re-crawling
- **Re-embedding** does not require re-chunking
- **Re-indexing** does not require re-embedding

This design allows for:
- Flexible re-processing at any stage
- Independent optimization of each stage
- Easy debugging and troubleshooting
- Cost-effective updates (only re-run what changed)

---

## 3. Data Model

### 3.1 MongoDB Collections

MongoDB serves as the **source of truth** for all data. Three primary collections are used:

#### 3.1.1 Raw Documents Collection

**Purpose:**
- Source of truth for raw content
- Audit trail for all processed documents
- Enables re-processing without re-crawling

**Schema:**
```json
{
  "document_id": "string (unique)",
  "tenant_id": "string",
  "source_information": {
    "url": "string",
    "crawler_id": "string",
    "crawled_at": "datetime"
  },
  "full_content": "string",
  "content_hash": "string (SHA-256)",
  "metadata": {
    "title": "string",
    "author": "string",
    "created_at": "datetime",
    "updated_at": "datetime",
    "custom_fields": "object"
  },
  "status": "string (pending|processed|failed)",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

#### 3.1.2 Chunks Collection

**Purpose:**
- Stores how documents were split
- Enables independent chunking strategies
- Allows same document to be chunked differently in the future

**Schema:**
```json
{
  "chunk_id": "string (unique)",
  "document_id": "string (reference to raw_documents)",
  "tenant_id": "string",
  "chunk_text": "string",
  "chunk_index": "integer",
  "chunking_strategy": "string",
  "chunking_config": {
    "strategy": "fixed_token|sliding_window|sentence_based|html_structure",
    "chunk_size": "integer",
    "overlap": "integer",
    "tokenizer": "string",
    "custom_params": "object"
  },
  "chunk_hash": "string (SHA-256 of chunk_text + strategy + config)",
  "status": "string (pending|processed|failed)",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

#### 3.1.3 Embeddings Collection

**Purpose:**
- Stores prepared knowledge (chunk + embedding model + vector)
- Enables re-indexing without re-embedding
- Allows model comparison
- Facilitates embedding debugging

**Schema:**
```json
{
  "embedding_id": "string (unique)",
  "chunk_id": "string (reference to chunks)",
  "document_id": "string (reference to raw_documents)",
  "tenant_id": "string",
  "embedding_model": "string",
  "embedding_strategy": "string",
  "vector_dimension": "integer",
  "embedding_vector": "array[float]",
  "normalization_info": {
    "normalized": "boolean",
    "norm_type": "L2|L1|none",
    "original_norm": "float"
  },
  "status": "string (pending|processed|failed)",
  "error_message": "string (if failed)",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### 3.2 OpenSearch Role

**Important:** OpenSearch is **NOT** a source of truth.

- OpenSearch is only a **materialized index** used for fast retrieval
- Vectors are **copied** from MongoDB
- Indexing strategy lives in OpenSearch
- Can be rebuilt at any time from MongoDB data
- Multiple indices can exist for the same embeddings with different strategies

---

## 4. API Endpoints

### 4.1 `/chunk` Endpoint

**Purpose:** Only chunking operations

**Flow:**
1. Read raw document from MongoDB
2. Apply chunking strategy (from config)
3. Save chunks to MongoDB
4. Return chunking results

**Rules:**
- ❌ No embeddings generated
- ❌ No OpenSearch interaction
- ✅ Idempotent: Same document + same strategy → skip or update
- ✅ Partial failures allowed (record per chunk)

**Use Cases:**
- Chunking logic changes
- Debugging chunks
- Preparing data step-by-step
- Re-chunking with different strategy

**Request:**
```json
{
  "document_id": "string",
  "tenant_id": "string",
  "chunking_strategy": "string",
  "chunking_config": {
    "chunk_size": 512,
    "overlap": 50,
    "strategy": "fixed_token"
  }
}
```

**Response:**
```json
{
  "document_id": "string",
  "chunks_created": 10,
  "chunks_failed": 0,
  "chunk_ids": ["chunk_1", "chunk_2", ...],
  "status": "success|partial|failed"
}
```

### 4.2 `/embed` Endpoint

**Purpose:** Only embedding generation

**Flow:**
1. Read chunks from MongoDB
2. Select embedding strategy from config
3. Generate embeddings
4. Store embeddings back into MongoDB
5. Return embedding results

**Rules:**
- ❌ Do not talk to OpenSearch
- ✅ Same chunk + same model should not be embedded twice (idempotent)
- ✅ Partial failures are allowed (record per embedding)
- ✅ Skip if embedding already exists with same hash

**Use Cases:**
- Generating embeddings for new chunks
- Re-embedding with different model
- Debugging embeddings
- Model comparison

**Request:**
```json
{
  "chunk_ids": ["chunk_1", "chunk_2", ...],
  "tenant_id": "string",
  "embedding_strategy": "openai|sentence_transformers",
  "embedding_config": {
    "model": "text-embedding-ada-002",
    "normalize": true,
    "preprocessing": {}
  }
}
```

**Response:**
```json
{
  "embeddings_created": 8,
  "embeddings_skipped": 2,
  "embeddings_failed": 0,
  "embedding_ids": ["emb_1", "emb_2", ...],
  "status": "success|partial|failed"
}
```

### 4.3 `/index` Endpoint

**Purpose:** Publish data to OpenSearch

**Flow:**
1. Read embeddings from MongoDB
2. Select indexing strategy (cosine, L2, dot, etc.)
3. Create or update OpenSearch index if needed
4. Push vectors + metadata into OpenSearch
5. Return indexing results

**Rules:**
- ❌ No embedding happens here
- ✅ Re-indexing must be cheap and safe
- ✅ Idempotent: Same embedding + same index → update or skip
- ✅ Partial failures allowed (record per vector)
- ✅ Can rebuild index from MongoDB at any time

**Use Cases:**
- Publishing embeddings to OpenSearch
- Re-indexing with different strategy
- Updating existing indices
- Creating multiple indices from same embeddings

**Request:**
```json
{
  "embedding_ids": ["emb_1", "emb_2", ...],
  "tenant_id": "string",
  "index_name": "string",
  "indexing_strategy": {
    "similarity": "cosine|l2|dot_product",
    "hnsw_config": {
      "m": 16,
      "ef_construction": 200
    }
  }
}
```

**Response:**
```json
{
  "index_name": "string",
  "vectors_indexed": 8,
  "vectors_failed": 0,
  "status": "success|partial|failed",
  "index_info": {
    "dimension": 1536,
    "similarity": "cosine",
    "total_vectors": 1000
  }
}
```

---

## 5. Chunking Design

### 5.1 Strategy-Based Chunking

Chunking is implemented using pluggable strategies:

#### Supported Strategies:
1. **Fixed Token Chunking**
   - Splits text into fixed-size token chunks
   - Configurable tokenizer (tiktoken, transformers, etc.)
   - Overlap support

2. **Sliding Window Chunking**
   - Overlapping chunks with configurable window size
   - Useful for context preservation

3. **Sentence-Based Chunking**
   - Splits on sentence boundaries
   - Respects natural language structure
   - Configurable min/max chunk size

4. **HTML Structure-Based Chunking**
   - Uses HTML tags for chunk boundaries
   - Respects document structure
   - Preserves semantic sections

### 5.2 Requirements

- **Deterministic:** Same input + same config → same chunks
- **Configurable:** Overlap and size must be configurable
- **Idempotent:** Same document + same strategy → same chunks
- **Hash-based:** Chunk hash = SHA-256(chunk_text + strategy + config)

### 5.3 Chunking Configuration

```json
{
  "strategy": "fixed_token|sliding_window|sentence_based|html_structure",
  "chunk_size": 512,
  "overlap": 50,
  "tokenizer": "tiktoken|transformers",
  "min_chunk_size": 100,
  "max_chunk_size": 2048,
  "preserve_whitespace": true,
  "custom_params": {}
}
```

---

## 6. Embedding Design

### 6.1 Strategy-Based Embedding

Embedding is implemented using pluggable strategies:

#### Supported Strategies:

1. **OpenAI Embedding API**
   - Models: text-embedding-ada-002, text-embedding-3-small, text-embedding-3-large
   - API-based (requires API key)
   - Automatic normalization support

2. **Sentence Transformers (Local)**
   - Model: sentence-transformers/all-MiniLM-L6-v3 (default)
   - Local execution (no API calls)
   - Configurable model selection

### 6.2 Strategy Definition

Each strategy defines:
- **Model:** Which model to use
- **Preprocessing:** Text preprocessing steps
- **Normalization:** Vector normalization (L2, L1, none)
- **Dimension:** Expected vector dimension

### 6.3 Requirements

- **Idempotent:** Same chunk + same model → same embedding (skip if exists)
- **Hash-based:** Embedding hash = SHA-256(chunk_hash + model + strategy + config)
- **Partial Failures:** Individual chunk failures don't stop batch
- **Error Recording:** Failed embeddings stored with error message

### 6.4 Embedding Configuration

```json
{
  "strategy": "openai|sentence_transformers",
  "model": "text-embedding-ada-002",
  "normalize": true,
  "normalization_type": "L2",
  "preprocessing": {
    "lowercase": false,
    "remove_punctuation": false,
    "max_length": 8192
  },
  "api_key": "string (for OpenAI)",
  "batch_size": 100
}
```

---

## 7. Indexing Design

### 7.1 Strategy-Based Indexing

Indexing is implemented using pluggable strategies:

#### Supported Strategies:

1. **Cosine Similarity**
   - Standard cosine similarity for normalized vectors
   - Most common for text embeddings

2. **L2 Distance (Euclidean)**
   - Euclidean distance metric
   - Requires appropriate normalization

3. **Dot Product**
   - Inner product similarity
   - Efficient for normalized vectors

4. **HNSW Tuning**
   - Hierarchical Navigable Small World graphs
   - Configurable parameters (m, ef_construction, ef_search)

### 7.2 Requirements

- **Independent of Embedding:** Indexing strategy is independent of embedding model
- **Multiple Indices:** Same embeddings can be indexed with different strategies
- **Rebuildable:** Index can be rebuilt from MongoDB at any time
- **Idempotent:** Same embedding + same index → update or skip
- **Metadata Support:** Store chunk metadata alongside vectors

### 7.3 Indexing Configuration

```json
{
  "similarity": "cosine|l2|dot_product",
  "hnsw_config": {
    "m": 16,
    "ef_construction": 200,
    "ef_search": 100
  },
  "index_settings": {
    "number_of_shards": 1,
    "number_of_replicas": 1
  },
  "metadata_fields": ["chunk_text", "document_id", "tenant_id"]
}
```

---

## 8. Idempotency Rules

### 8.1 General Rules

- **Same content hash + same strategy + same model → skip**
- **Re-processing allowed only if config or model changes**
- **MongoDB enforces idempotency** through unique constraints and hash checks

### 8.2 Per-Stage Rules

#### Chunking:
- Document hash + chunking strategy + config → unique chunks
- If chunks exist, skip or update based on hash comparison

#### Embedding:
- Chunk hash + embedding model + strategy + config → unique embedding
- If embedding exists, skip (no re-embedding)

#### Indexing:
- Embedding ID + index name + indexing strategy → unique index entry
- If entry exists, update (allows index refresh)

---

## 9. Error Handling

### 9.1 Failure Tolerance

- **Chunk-level failures are allowed**
- **Embedding-level failures are allowed**
- **Indexing-level failures are allowed**

### 9.2 Failure Recording

- Failures are recorded per item in MongoDB
- Status field tracks: `pending`, `processed`, `failed`
- Error messages stored for debugging
- Successful items continue processing

### 9.3 Retry Strategy

- Failed items can be retried independently
- No automatic retries (manual or scheduled retry endpoint)
- Batch operations continue even with partial failures

### 9.4 Error Response Format

```json
{
  "status": "partial",
  "successful": 8,
  "failed": 2,
  "errors": [
    {
      "item_id": "chunk_5",
      "error": "Tokenization failed: Invalid encoding",
      "error_code": "TOKENIZATION_ERROR"
    }
  ]
}
```

---

## 10. Tech Stack

### 10.1 Core Technologies

- **Language:** Python 3.10+
- **Framework:** FastAPI
- **Database:** MongoDB (source of truth)
- **Search Engine:** OpenSearch
- **Embedding Models:**
  - OpenAI Embeddings API
  - sentence-transformers (local)

### 10.2 Key Libraries

- **FastAPI:** Web framework and API
- **pymongo:** MongoDB client
- **opensearch-py:** OpenSearch client
- **openai:** OpenAI API client
- **sentence-transformers:** Local embedding models
- **tiktoken:** Token counting for chunking
- **pydantic:** Data validation

### 10.3 Infrastructure

- **Docker:** Containerization
- **Docker Compose:** Local development setup
- **MongoDB:** Document database
- **OpenSearch:** Vector search engine

---

## 11. Development Approach

### 11.1 Incremental Development

Build incrementally, following this order:

1. **Infrastructure Setup**
   - MongoDB connection and client
   - OpenSearch connection and client
   - Docker setup
   - Basic project structure

2. **Chunking Service**
   - Chunking strategies implementation
   - MongoDB chunks collection
   - Chunking endpoint

3. **Embedding Service**
   - Embedding strategies implementation
   - MongoDB embeddings collection
   - Embedding endpoint

4. **Indexing Service**
   - Indexing strategies implementation
   - OpenSearch integration
   - Indexing endpoint

5. **API Layer**
   - Wire all endpoints
   - Error handling
   - Validation
   - Documentation

### 11.2 Folder Structure

```
embedding-service/
├── app/
│   ├── main.py                          # FastAPI app entry
│   │
│   ├── config/                          # Runtime & static configuration
│   │   ├── __init__.py
│   │   ├── settings.py
│   │   ├── logging.py
│   │   ├── chunking/                    # Chunking configuration
│   │   │   ├── __init__.py
│   │   │   ├── models.py
│   │   │   ├── static.py
│   │   │   └── static.json
│   │   ├── embedding/                   # Embedding configuration
│   │   │   ├── __init__.py
│   │   │   ├── models.py
│   │   │   ├── providers.py
│   │   │   └── static.json
│   │   ├── indexing/                    # Indexing configuration
│   │   │   ├── __init__.py
│   │   │   ├── models.py                # IndexingConfig (cosine, l2, dot, hnsw)
│   │   │   ├── static.py
│   │   │   └── static.json              # Indexing profiles
│   │   └── storage/
│   │       ├── __init__.py
│   │       ├── mongo.py
│   │       └── opensearch.py
│   │
│   ├── resources/                       # Managed external resources
│   │   ├── __init__.py
│   │   ├── mongo/
│   │   │   ├── __init__.py
│   │   │   ├── client.py
│   │   │   └── session.py
│   │   └── opensearch/
│   │       ├── __init__.py
│   │       ├── client.py
│   │       ├── index_manager.py         # Create/update indices
│   │       └── health.py
│   │
│   ├── controllers/                     # API layer
│   │   ├── __init__.py
│   │   ├── routes/
│   │   │   ├── chunk.py                 # POST /chunk
│   │   │   ├── embed.py                 # POST /embed
│   │   │   └── index.py                 # POST /index
│   │   └── schema/
│   │       ├── chunk.py
│   │       ├── embed.py
│   │       └── index.py
│   │
│   ├── services/                        # Stateless business logic
│   │   ├── __init__.py
│   │   ├── chunking/
│   │   │   ├── __init__.py
│   │   │   ├── chunker.py
│   │   │   ├── strategies/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── fixed_tokens.py
│   │   │   │   ├── sliding_window.py
│   │   │   │   ├── sentence_boundary.py
│   │   │   │   └── html_structure.py
│   │   │   ├── tokenizer.py
│   │   │   └── cleaners.py
│   │   ├── embedder/                    # Knowledge preparation
│   │   │   ├── __init__.py
│   │   │   ├── base.py                  # BaseEmbeddingStrategy
│   │   │   ├── resolver.py
│   │   │   ├── preprocessing.py
│   │   │   ├── validator.py
│   │   │   └── strategies/
│   │   │       ├── __init__.py
│   │   │       ├── openai_strategy.py
│   │   │       ├── sentence_transformer.py
│   │   │       └── mock_strategy.py
│   │   ├── indexing/                    # Index materialization
│   │   │   ├── __init__.py
│   │   │   ├── base.py                  # BaseIndexingStrategy
│   │   │   ├── resolver.py
│   │   │   ├── strategies/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── cosine_knn.py
│   │   │   │   ├── l2_knn.py
│   │   │   │   ├── dot_product_knn.py
│   │   │   │   └── hnsw.py
│   │   │   └── publisher.py             # Push to OpenSearch
│   │   └── orchestrator.py             # Calls chunk → embed → index
│   │
│   ├── repositories/                   # Data access layer
│   │   ├── __init__.py
│   │   ├── mongodb/
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── documents_repository.py
│   │   │   ├── chunks_repository.py
│   │   │   └── embeddings_repository.py
│   │   └── opensearch/
│   │       ├── __init__.py
│   │       └── chunks_repo.py
│   │
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── ids.py
│   │   ├── time.py
│   │   ├── telemetry.py
│   │   ├── retry.py
│   │   └── validation.py
│   │
│   └── docker/
│       └── Dockerfile
│
├── tests/
├── docker-compose.yml
└── requirements.txt
```

### 11.3 Five-Phase Implementation Plan

The plan follows the fixed architecture: three MongoDB collections (raw_documents, chunks, embeddings), independent stages (chunk → embed → index), embeddings stored in MongoDB first, OpenSearch as materialized index only, and idempotency (same chunk + same embedding model not embedded twice). The folder structure in §11.2 is final and must not be changed.

---

**Phase 1: Foundation & Infrastructure**

**Goal:** Have a runnable service with configuration, logging, containerization, and database connectivity so all later stages can rely on it.

**What will be implemented:**
- Python project setup: virtualenv/poetry, `requirements.txt` with FastAPI, pydantic, and transitive dependencies per §10.2.
- Exact folder structure from §11.2 under `app/` (no new top-level folders or renames).
- `app/config/`: `settings.py` (env-based), `logging.py` (structured logging), and static config loaders for chunking/embedding/indexing/storage where they are only read (no business logic).
- `app/docker/Dockerfile` and project-root `docker-compose.yml` defining MongoDB and OpenSearch services plus the app service, with correct wiring of env and ports.
- `app/main.py`: FastAPI app bootstrap, config/logging init, and placeholder health route (e.g. `/health`) that returns OK.
- `app/resources/mongo/`: MongoDB client and session/connection handling; `app/resources/opensearch/`: OpenSearch client. Connection pooling, timeouts, and graceful shutdown. No repositories or business logic in this phase.
- Health checks that verify MongoDB and OpenSearch connectivity (e.g. `/health` or `/ready` extending to DB checks).
- Centralized error handling for connection failures and timeouts, with clear, non-leaking error messages.

**Exit criterion:** Service starts via Docker Compose, serves a health endpoint, and can open pooled connections to MongoDB and OpenSearch with basic error handling and logging.

---

**Phase 2: Data Access & Chunking Stage**

**Goal:** Implement the document → chunks pipeline with MongoDB as source of truth. `/chunk` is the only pipeline endpoint delivered in this phase.

**What will be implemented:**
- `app/repositories/mongodb/base.py`: Shared MongoDB access patterns, tenant/document filters, and common error handling.
- `app/repositories/mongodb/documents_repository.py`: Read raw documents by `document_id` and `tenant_id` from the `raw_documents` collection per §3.1.1; no writes in this service (raw_documents are assumed to exist from a crawler).
- `app/repositories/mongodb/chunks_repository.py`: Insert/upsert chunks into the `chunks` collection per §3.1.2; support idempotency by `chunk_hash` (+ document + strategy + config) so same document + same strategy + config does not duplicate chunks.
- `app/config/chunking/`: Wire `models.py`, `static.py`, and `static.json` so chunking strategies and configs can be resolved by name.
- `app/services/chunking/`: Tokenizer and cleaners; strategy implementations for fixed_token, sliding_window, sentence_boundary, and html_structure per §5.1; chunker that takes a raw document + strategy + config and returns chunks with `chunk_hash` and full chunk schema fields.
- Chunking service orchestration: load document via documents repository → run chunker → persist via chunks repository; enforce determinism and idempotency (skip or update by hash).
- `app/controllers/routes/chunk.py` and `app/controllers/schema/chunk.py`: POST `/chunk` with request/response shapes per §4.1; validation and tenant/document presence checks.
- No embedding logic, no OpenSearch usage, no `/embed` or `/index` in this phase.

**Exit criterion:** Given a `document_id` and `tenant_id` for an existing raw_document, POST `/chunk` with a chosen chunking strategy and config produces chunks in the `chunks` collection idempotently and returns the §4.1 response shape.

---

**Phase 3: Embedding Stage**

**Goal:** Implement the chunks → embeddings pipeline and store results only in MongoDB. Same chunk + same embedding model must not be embedded twice.

**What will be implemented:**
- `app/repositories/mongodb/embeddings_repository.py`: CRUD for the `embeddings` collection per §3.1.3; read chunks by `chunk_id`/`tenant_id`; write embeddings with `embedding_id`, references to `chunk_id`/`document_id`, `embedding_model`, `embedding_strategy`, vector, normalization_info, status, and timestamps. Idempotency enforced by a unique constraint or lookup on (chunk_id, embedding_model, strategy, config hash) so existing embeddings are skipped.
- `app/config/embedding/`: `models.py`, `providers.py`, and `static.json` for resolving embedding strategy and config by name.
- `app/services/embedder/`: `BaseEmbeddingStrategy`, resolver, preprocessing, and validator; strategy implementations for OpenAI and sentence_transformers per §6.1; optional mock strategy for tests. Each strategy produces vectors with consistent dimension and supports normalization (L2/L1/none) per §6.4.
- Embedding service flow: accept chunk_ids + tenant_id + embedding strategy/config; load chunks via chunks repository; for each chunk, compute embedding config hash (chunk_hash + model + strategy + config); if an embedding already exists for that hash, skip; otherwise call the selected strategy, then persist to embeddings repository. Record status and error_message per chunk for partial failures per §9.2.
- `app/controllers/routes/embed.py` and `app/controllers/schema/embed.py`: POST `/embed` with request/response per §4.2; validate chunk_ids, tenant_id, and embedding config.
- No OpenSearch writes or reads; no indexing logic. Chunking and indexing are unchanged and out of scope for this phase.

**Exit criterion:** Given chunk_ids and tenant_id for existing chunks, POST `/embed` with an embedding strategy and config creates embeddings in the `embeddings` collection, skips when an embedding already exists for the same chunk + model + config, and returns the §4.2 response (including counts for created/skipped/failed).

---

**Phase 4: Indexing Stage**

**Goal:** Implement the embeddings → OpenSearch pipeline. OpenSearch is used only as a materialized index; all source data comes from MongoDB.

**What will be implemented:**
- `app/resources/opensearch/index_manager.py`: Create or update OpenSearch indices from an indexing strategy (similarity, HNSW params, index settings); support cosine, L2, and dot_product similarity and HNSW tuning per §7.1–7.3; no business logic beyond index definition and mapping.
- `app/repositories/opensearch/chunks_repo.py` (or equivalent): Write operations to push vectors and metadata (e.g. chunk_text, document_id, tenant_id) from in-memory embedding records into a given OpenSearch index; support idempotent updates (same embedding + same index → update or skip) so re-indexing is safe and cheap.
- `app/config/indexing/`: `models.py`, `static.py`, and `static.json` for indexing profiles (similarity, hnsw_config, metadata_fields) per §7.3.
- `app/services/indexing/`: `BaseIndexingStrategy`, resolver, and strategy implementations (cosine_knn, l2_knn, dot_product_knn, hnsw) that define how the index is built and which similarity/mapping to use; `publisher.py` loads embeddings from the embeddings repository, optionally applies strategy-specific mapping, and uses the OpenSearch repository and index manager to create/update the index and bulk-index vectors.
- Indexing service flow: accept embedding_ids + tenant_id + index_name + indexing_strategy; load embeddings from MongoDB; ensure index exists/updated via index manager; bulk-publish vectors + metadata to OpenSearch with idempotent semantics per §4.3.
- `app/controllers/routes/index.py` and `app/controllers/schema/index.py`: POST `/index` with request/response per §4.3; validate embedding_ids, tenant_id, index_name, and indexing_strategy.
- No embedding generation or chunking logic; no changes to MongoDB embeddings schema or to `/chunk` or `/embed`.

**Exit criterion:** Given embedding_ids and tenant_id for existing embeddings in MongoDB, POST `/index` with index_name and indexing strategy creates or updates the OpenSearch index and publishes the corresponding vectors and metadata; re-running with the same inputs is idempotent (update or skip), and the index can be rebuilt from MongoDB at any time.

---

**Phase 5: Production Readiness**

**Goal:** Harden the system for production: consistent error handling, validation, tenant isolation, observability, and tests so the service is deployable and operable.

**What will be implemented:**
- **Error handling:** Align all three endpoints with §9: per-item failure recording (status, error_message), partial success responses (success/partial/failed, counts, and error list per §9.4), and no silent swallowing of errors. Retry behavior only where explicitly designed (e.g. `app/utils/retry.py` for transient DB/OpenSearch/API failures), without changing idempotency semantics.
- **Validation and safety:** Input validation (Pydantic) for all request bodies; tenant_id required and validated on every request; document_id/chunk_id/embedding_id format and existence checks where applicable; request size or batch limits to avoid overload.
- **Tenant isolation:** Ensure every MongoDB and OpenSearch query in repositories and services is scoped by tenant_id; no cross-tenant reads or writes.
- **Observability:** Structured logging (request ids, tenant_id, stage, counts, latency) in controllers and critical service paths; optional telemetry hooks in `app/utils/telemetry.py` for metrics; health/ready endpoints that reflect MongoDB and OpenSearch availability.
- **Testing:** Unit tests for chunking strategies, embedding strategies, and indexing strategies; repository tests (or integrated tests) for idempotency and partial failure behavior; API tests for `/chunk`, `/embed`, and `/index` covering success, partial failure, and validation failure cases.
- **Operational concerns:** Document or codify shutdown behavior (drain in-flight requests, close DB/OpenSearch pools); align with performance targets in §12.1 where feasible (batch sizes, timeouts); secure handling of API keys and secrets (e.g. embedding config) via config/settings only, never in logs or responses.

**Exit criterion:** The service passes the success criteria in §14: all three stages work independently and idempotently, partial failures are handled and reported, strategies are pluggable, MongoDB is the source of truth and OpenSearch the materialized index, with coherent error handling, tests, and tenant isolation in place.

---

## 12. Non-Functional Requirements

### 12.1 Performance

- Chunking: Process 1000 documents/minute
- Embedding: Process 100 chunks/minute (API rate limits considered)
- Indexing: Index 1000 vectors/minute
- API response time: < 2 seconds for single document operations

### 12.2 Scalability

- Horizontal scaling support
- Stateless API design
- Batch processing support
- Async operations where possible

### 12.3 Reliability

- Idempotent operations
- Partial failure handling
- Data consistency (MongoDB as source of truth)
- Error recovery mechanisms

### 12.4 Security

- Tenant isolation (tenant_id in all operations)
- API key management for OpenAI
- Input validation
- Rate limiting

### 12.5 Observability

- Structured logging
- Error tracking
- Performance metrics
- Health check endpoints

---

## 13. Future Considerations

### 13.1 Potential Enhancements

- Additional embedding models (Cohere, HuggingFace, etc.)
- Custom embedding models
- Advanced chunking strategies (semantic chunking)
- Batch processing endpoints
- Scheduled re-processing
- Webhook notifications
- Multi-tenant optimization
- Caching layer
- GraphQL API option

### 13.2 Scalability Improvements

- Message queue for async processing
- Distributed processing
- Vector compression
- Incremental indexing
- Index versioning

---

## 14. Success Criteria

### 14.1 Functional Requirements

- ✅ All three stages work independently
- ✅ Idempotent operations across all stages
- ✅ Partial failure handling
- ✅ Multiple strategies per stage
- ✅ MongoDB as source of truth
- ✅ OpenSearch as materialized index

### 14.2 Quality Requirements

- ✅ Comprehensive error handling
- ✅ Full test coverage
- ✅ API documentation
- ✅ Code maintainability
- ✅ Performance benchmarks met

---

## 15. Glossary

- **RAG:** Retrieval-Augmented Generation
- **Chunking:** Process of splitting documents into smaller pieces
- **Embedding:** Vector representation of text
- **Indexing:** Storing vectors in a searchable format
- **Idempotent:** Operation that produces the same result when applied multiple times
- **HNSW:** Hierarchical Navigable Small World (graph-based approximate nearest neighbor search)
- **Tenant:** Logical isolation unit (multi-tenant support)


---

**End of PRD**
