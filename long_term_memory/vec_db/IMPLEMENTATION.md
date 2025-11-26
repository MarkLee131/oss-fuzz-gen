## Vector Database Implementation

This document summarizes how the vector database for long‑term driver code examples is implemented. It is intentionally brief; see the code in this directory for full details.

### Storage layout

- **Backend**: Chroma local vector store.
- **Location**: configurable, default `./chroma_db/`.
- **Collection**: `driver_code` (configurable).

Each record stores:
- **id** – unique identifier derived from the driver file path.
- **embedding** – 3072‑dimensional vector from OpenAI `text-embedding-3-large`.
- **document** – searchable text that combines metadata and a truncated code snippet.
- **metadata**, including:
  - `file_path`: driver file path.
  - `project`: project name.
  - `api_name`: API function name.
  - `api_type`: inferred API/archetype.
  - `code_content`: truncated code (up to ~50 KB).
  - `code_length`: full code length.

### Embedding generation

Model: **OpenAI `text-embedding-3-large`**.

High‑level flow:
1. Read the driver source file.
2. Extract metadata (`project`, `api_name`, `api_type`).
3. Build an embedding payload such as:

   ```text
   Project: {project}
   API: {api_name}
   API Type: {api_type}

   Code:
   {code_content[:8000]}
   ```

4. Call the OpenAI API to create the embedding and store it in Chroma.

Reference implementation: `driver_indexer.py::_get_embedding`.

### Similarity search

- **Metric**: cosine similarity, implemented as `1 - cosine_distance`.
- **Engine**: Chroma’s approximate nearest‑neighbour (HNSW).
- **Flow**:
  1. Embed the query text.
  2. Call `collection.query(...)` with optional metadata filters (e.g., `project`, `api_type`).
  3. Sort by similarity and apply a configurable threshold.
  4. Return the top‑`n` results.

Main entry point: `driver_indexer.py::search_similar`.

### API type inference

API “type” (archetype) is inferred heuristically via regular expressions over the driver source code. Supported categories include:
- `simple_function_call`
- `object_lifecycle` (init/create → use → destroy/free)
- `streaming_api` (loop‑based streaming)
- `callback_api`
- `file_path_api`
- `multi_parameter_api`
- `exception_handling_api`

The implementation counts matches for each pattern family and selects the best‑scoring type. See `driver_indexer.py::_infer_api_type`.

### Retrieval interface

High‑level access is provided by `DriverCodeRetriever`:
- `search_by_description(...)` – natural‑language queries.
- `search_by_code_snippet(...)` – code‑snippet similarity search.
- `search_by_api_name(...)` – look up by API function name.
- `get_examples_by_type(...)` – examples for a given `api_type`.
- `get_examples_by_project(...)` – examples for a given project.

Implementation: `driver_retriever.py`.

### Usage examples

Index all drivers:

```python
from long_term_memory.vec_db.driver_indexer import DriverCodeIndexer

indexer = DriverCodeIndexer(
    drivers_dir="extracted_fuzz_drivers",
    persist_directory="./chroma_db",
    collection_name="driver_code",
)
indexer.index_all_drivers()
```

Search for similar code:

```python
from long_term_memory.vec_db.driver_retriever import DriverCodeRetriever

retriever = DriverCodeRetriever(
    persist_directory="./chroma_db",
    collection_name="driver_code",
)

results = retriever.search_by_description(
    "streaming API with loop and iteration limit",
    api_type="streaming_api",
    n=5,
    threshold=0.7,
)
```

### Files and dependencies

Layout:

```text
long_term_memory/vec_db/
├── driver_indexer.py      # indexing: build embeddings and write to Chroma
├── driver_retriever.py    # retrieval: high‑level search APIs
└── IMPLEMENTATION.md      # this document
```

Core dependencies:

```text
chromadb        # vector database (>= 0.4.0)
openai          # embedding generation
tqdm            # progress bars
scipy           # cosine distance
```


