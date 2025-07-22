# 📚 Vector Store Management Tutorial

Welcome to your **persistent FAISS vector store**! This guide explains how to monitor, maintain, and troubleshoot your vector store now that it is saved to disk.

---
## 1. File Locations

| File | Purpose |
|------|---------|
| `vector_store.faiss` | The raw FAISS index containing all vectors (embeddings). |
| `docstore.pkl` | Pickled `InMemoryDocstore` that holds the original documents. |
| `index_mapping.pkl` | Mapping between FAISS internal IDs and docstore IDs. |

All three files live in the project root (you can move them elsewhere—just update the paths in `VectorStoreService`).

---
## 2. Quick Status Check

The easiest way to see what’s inside the vector store is via the helper method `get_vector_store_info()`:

```python
from services.vector_service import get_vector_service

vs = get_vector_service()
print(vs.get_vector_store_info())
```

Typical output:

```python
{
    'status': 'initialized',
    'doc_count': 1287,          # 🔢 Total vectors stored
    'embedding_dimension': 768, # Size of each vector
    'persistent_storage': True, # All persistence files found
    'index_file_exists': True,
    'docstore_file_exists': True,
    'mapping_file_exists': True
}
```

---
## 3. Counting Documents Only

If you just need the count:

```python
vs = get_vector_service()
print(vs.vector_store.index.ntotal)  # prints: 1287
```

---
## 4. Adding New Content

There are two high-level convenience methods:

1. **Embed an entire datasource (file / URL):**
   ```python
   from models import DataSource  # Example model instance

   new_source = DataSource(
       reference="my_notes.txt",
       source_type="file",
       path="/absolute/path/to/my_notes.txt",
       is_synced=True,
   )
   get_vector_service().embed_datasource(new_source)
   ```

2. **Embed an ad-hoc content string:**
   ```python
   get_vector_service().embed_content_string("Here is some text…", "manual_input")
   ```

Both methods automatically **save** the vector store after successful insertion, so nothing extra is required.

---
## 5. Deleting / Resetting the Store

### 5.1 Full Reset (Delete Everything)

```python
vs = get_vector_service()
vs.reset_vector_store()  # ⚠️ This wipes disk files AND memory
```

*What it does*
1. Removes `vector_store.faiss`, `docstore.pkl`, and `index_mapping.pkl`
2. Re-initializes an **empty** FAISS index.

### 5.2 Selective Deletion (Advanced)

FAISS itself does **not** support removing arbitrary individual vectors in `IndexFlatL2`. If you require per-document deletion you have two options:

1. **Rebuild**: Filter out unwanted docs from your data sources, call `reset_vector_store()`, then re-embed.
2. **Upgrade**: Switch to a vector DB that supports deletions (e.g. **Qdrant**, **Weaviate**, **Milvus**).

---
## 6. Backing Up the Store

Because the store is just three files, backing up is trivial:

```bash
cp vector_store.faiss docstore.pkl index_mapping.pkl /path/to/backups/
```

Automate this with cron or any scheduled task runner.

---
## 7. Troubleshooting Tips

1. **Load Errors**
   * Ensure all three files exist and are from the same snapshot.
   * Mismatched versions of FAISS can break compatibility—stick to the version specified in `requirements.txt`.

2. **Unexpected Duplicate Inserts**
   * Confirm the store is loaded before running any bulk-embedding methods (`load_vector_store()` returns `True`).
   * Double-check that `load_documents_from_data_folder()` is not forced when the store already contains data.

3. **High Memory Usage**
   * Only the FAISS index is memory-heavy. Consider using **IndexIVF** or **HNSW** variants for large datasets.

---
## 8. Future Ideas

* **Model Caching** – Use `@lru_cache` or a singleton pattern so the embedding model is loaded only once.
* **Switch to a Vector DB** – For production features like per-vector delete, metadata filtering, distributed indexing.
* **Dashboards** – Expose `get_vector_store_info()` via an API endpoint for real-time monitoring.

---
### Happy Embedding! 🚀

Feel free to expand this tutorial as your workflow evolves. If you have any questions, just open an issue or ping the team. 