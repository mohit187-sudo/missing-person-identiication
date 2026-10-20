# Optional pgvector setup (PostgreSQL)

The application stores face embeddings as portable `float32` blobs (`face_embeddings.embedding`)
and compares them with **cosine similarity** in application code. This works on both SQLite and
PostgreSQL with zero extra dependencies.

For large galleries (tens of thousands of embeddings) you can enable **pgvector** approximate
nearest-neighbour search:

## 1. Database

`docker-compose.yml` already uses the `pgvector/pgvector:pg16` image. Enable the extension:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

## 2. Mirror column

```sql
ALTER TABLE face_embeddings ADD COLUMN embedding_vector vector(128);

UPDATE face_embeddings
SET embedding_vector = embedding::vector;  -- after converting bytes to a float list, e.g. via app script

CREATE INDEX ON face_embeddings
  USING ivfflat (embedding_vector vector_cosine_ops)
  WITH (lists = 100);
```

> The blob → vector conversion is a one-off script (unpack 128 little-endian float32 values and
> format as `[x,y,...]`). The application continues to read the blob column so SQLite development
> keeps working unchanged.

## 3. Query example

```sql
SELECT case_id, 1 - (embedding_vector <=> $query) AS cosine_similarity
FROM face_embeddings
WHERE case_id IS NOT NULL
ORDER BY embedding_vector <=> $query
LIMIT 20;
```

## 4. Application integration point

`backend/app/ai/service.py::FaceMatchingService.rank_candidates` is the single comparison
gateway — swap its in-memory loop for the SQL above when `USE_PGVECTOR=true` and the deployment
runs on PostgreSQL. Threshold semantics are unchanged: higher cosine similarity = closer
embeddings, and **the score still is not an identity probability**.
