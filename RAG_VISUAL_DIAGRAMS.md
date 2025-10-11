# RAG System Visual Diagrams

## 🎨 Quick Visual Reference

### Component Diagram
```
┌─────────────────────────────────────────────────────────────────────┐
│                          RAG SYSTEM                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                      CHAT ROUTER                             │   │
│  │  • Receives HTTP requests                                    │   │
│  │  • Authenticates users                                       │   │
│  │  • Saves to database                                         │   │
│  └──────────────────────┬──────────────────────────────────────┘   │
│                         │                                            │
│                         ▼                                            │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                      RAG SERVICE                             │   │
│  │  ┌──────────────────────────────────────────────────────┐   │   │
│  │  │         ask_question() ← YOU ARE HERE!               │   │   │
│  │  │  • Fetches language preference                       │   │   │
│  │  │  • Invokes LangGraph pipeline                        │   │   │
│  │  │  • Collects metrics                                  │   │   │
│  │  └──────────────────────────────────────────────────────┘   │   │
│  │                         │                                    │   │
│  │                         ▼                                    │   │
│  │  ┌──────────────────────────────────────────────────────┐   │   │
│  │  │              LANGGRAPH PIPELINE                      │   │   │
│  │  │                                                      │   │   │
│  │  │  START → _retrieve() → _generate() → END           │   │   │
│  │  │           │              │                          │   │   │
│  │  │           ▼              ▼                          │   │   │
│  │  │       [Translate]    [Use LLM]                     │   │   │
│  │  │       [Search DB]    [Format]                      │   │   │
│  │  └──────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────┘   │
│           │                │                │                        │
│           ▼                ▼                ▼                        │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐               │
│  │  TRANSLATOR  │ │ VECTOR STORE │ │     LLM      │               │
│  │   (Argos)    │ │   (Qdrant)   │ │(Gemini/Ollama)│              │
│  └──────────────┘ └──────────────┘ └──────────────┘               │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                      RAG LOGGER                              │   │
│  │  • Logs to JSONL                                             │   │
│  │  • Captures translation details                              │   │
│  │  • Records metrics                                           │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Request Flow (Detailed)

```
┌─────────┐
│  USER   │ "Comment ça marche?"
└────┬────┘
     │
     │ POST /chat/
     ▼
┌─────────────────────────────────────┐
│  CHAT ROUTER                        │
│  ✓ Authenticate                     │
│  ✓ Extract question                 │
│  ✓ Get user workspace               │
└────┬────────────────────────────────┘
     │
     │ ask_question(q, workspace_id, user_id)
     ▼
┌─────────────────────────────────────┐
│  RAG SERVICE: ask_question()        │
│  Step 1: Fetch language pref        │
│    ↓                                │
│    SELECT * FROM userpreference     │
│    WHERE user_id=1                  │
│    Result: 'fr' → 'French'          │
│                                     │
│  Step 2: Invoke LangGraph           │
│    ↓                                │
│    State = {                        │
│      question: "Comment..."         │
│      workspace_id: 2                │
│      source_language: "fr"          │
│      language: "French"             │
│    }                                │
└────┬────────────────────────────────┘
     │
     │ rag_graph.invoke(state)
     ▼
┌─────────────────────────────────────┐
│  LANGGRAPH: _retrieve()             │
│                                     │
│  Step 1: Check static responses     │
│    ↓ (none found)                   │
│                                     │
│  Step 2: Translate                  │
│    ↓                                │
│    translate_text(                  │
│      "Comment ça marche?",          │
│      source="fr",                   │
│      target="en"                    │
│    )                                │
│    → "How does it work?"            │
│                                     │
│  Step 3: Search vector DB           │
│    ↓                                │
│    similarity_search(               │
│      query="How does it work?",     │
│      filter=workspace_id=2,         │
│      k=3                            │
│    )                                │
│    → [doc1, doc2, doc3]             │
│                                     │
│  Step 4: Return                     │
│    ↓                                │
│    {                                │
│      context: [docs],               │
│      translated_question: "How...", │
│      retrieval_latency_ms: 450      │
│    }                                │
└────┬────────────────────────────────┘
     │
     │ State updated with docs
     ▼
┌─────────────────────────────────────┐
│  LANGGRAPH: _generate()             │
│                                     │
│  Step 1: Format context             │
│    ↓                                │
│    context = """                    │
│      Here's what I know:            │
│      [doc1.content]                 │
│      [doc2.content]                 │
│    """                              │
│                                     │
│  Step 2: Create prompt              │
│    ↓                                │
│    prompt = f"""                    │
│      You are Aidly...               │
│      Context: {context}             │
│      Question: {question}           │
│      Reply in: French               │
│    """                              │
│                                     │
│  Step 3: Call LLM                   │
│    ↓                                │
│    llm.invoke(prompt)               │
│    → "Ça marche comme ça..."        │
│                                     │
│  Step 4: Return                     │
│    ↓                                │
│    {                                │
│      answer: "Ça marche...",        │
│      generation_latency_ms: 800     │
│    }                                │
└────┬────────────────────────────────┘
     │
     │ Return to ask_question()
     ▼
┌─────────────────────────────────────┐
│  RAG SERVICE: Collect Metrics       │
│                                     │
│  metrics = {                        │
│    original_question: "Comment...", │
│    translated_question: "How...",   │
│    source_language: "fr",           │
│    response_language: "French",     │
│    was_translated: true,            │
│    retrieval_latency_ms: 450,       │
│    generation_latency_ms: 800,      │
│    ...                              │
│  }                                  │
│                                     │
│  return (answer, metrics)           │
└────┬────────────────────────────────┘
     │
     │ Return to router
     ▼
┌─────────────────────────────────────┐
│  CHAT ROUTER: Save & Log            │
│                                     │
│  Step 1: Save to DB                 │
│    ↓                                │
│    INSERT INTO message (...)        │
│                                     │
│  Step 2: Log to JSONL               │
│    ↓                                │
│    rag_logger.log_interaction(      │
│      original_question="Comment...", │
│      translated_question="How...",  │
│      ...                            │
│    )                                │
│                                     │
│  Step 3: Return response            │
│    ↓                                │
│    {                                │
│      "answer": "Ça marche...",      │
│      "latency_ms": 1250,            │
│      "message_id": 156              │
│    }                                │
└────┬────────────────────────────────┘
     │
     │ HTTP Response
     ▼
┌─────────┐
│  USER   │ Receives answer in French
└─────────┘
```

---

## 🧩 LangGraph State Flow

```
Initial State:
┌────────────────────────────────────┐
│ question: "Comment ça marche?"     │
│ original_question: "Comment..."    │
│ workspace_id: 2                    │
│ source_language: "fr"              │
│ language: "French"                 │
│ was_translated: true               │
│ translated_question: None          │ ← Not set yet
│ context: []                        │ ← Empty
│ answer: ""                         │ ← Empty
└────────────────────────────────────┘
           ↓
    _retrieve() runs
           ↓
After _retrieve():
┌────────────────────────────────────┐
│ question: "Comment ça marche?"     │
│ original_question: "Comment..."    │
│ workspace_id: 2                    │
│ source_language: "fr"              │
│ language: "French"                 │
│ was_translated: true               │
│ translated_question: "How..."      │ ← NOW SET! (Bug fix)
│ context: [doc1, doc2, doc3]        │ ← Documents added
│ retrieval_latency_ms: 450          │ ← Added
│ answer: ""                         │
└────────────────────────────────────┘
           ↓
    _generate() runs
           ↓
Final State:
┌────────────────────────────────────┐
│ question: "Comment ça marche?"     │
│ original_question: "Comment..."    │
│ workspace_id: 2                    │
│ source_language: "fr"              │
│ language: "French"                 │
│ was_translated: true               │
│ translated_question: "How..."      │
│ context: [doc1, doc2, doc3]        │
│ retrieval_latency_ms: 450          │
│ generation_latency_ms: 800         │ ← Added
│ answer: "Ça marche comme ça..."    │ ← Answer generated!
└────────────────────────────────────┘
```

---

## 🐛 The Bug (Before and After)

### BEFORE (Bug):
```
_retrieve() {
    search_question = translate("Comment...", "fr", "en")
    // search_question = "How does it work?"
    
    docs = search_vector_db(search_question)
    
    return {
        "context": docs,
        "retrieval_latency_ms": 450
        // ❌ NOT RETURNING translated_question!
    }
}

ask_question() {
    result = rag_graph.invoke(...)
    
    metrics = {
        "translated_question": result.get("translated_question")
        // Returns None! 😭
    }
}

LOGS:
{
    "original_question": "Comment...",
    "translated_question": "Comment..."  ← SAME! (Bug)
}
```

### AFTER (Fixed):
```
_retrieve() {
    search_question = translate("Comment...", "fr", "en")
    // search_question = "How does it work?"
    
    docs = search_vector_db(search_question)
    
    return {
        "context": docs,
        "retrieval_latency_ms": 450,
        "translated_question": search_question  // ✅ NOW RETURNED!
    }
}

ask_question() {
    result = rag_graph.invoke(...)
    
    metrics = {
        "translated_question": result.get("translated_question")
        // Returns "How does it work?" ✅
    }
}

LOGS:
{
    "original_question": "Comment...",
    "translated_question": "How does it work?"  ← DIFFERENT! ✅
}
```

---

## 📊 Translation Flow

```
User Question
     │
     │ "Comment changer le superviseur?"
     ▼
┌─────────────────────┐
│  Language Check     │
│  source_lang = "fr" │
└──────┬──────────────┘
       │
       │ Is it English?
       ▼
    ┌──NO─┐
    │     │
    ▼     ▼
┌──────────────────┐    ┌──────────────────┐
│   TRANSLATE      │    │   NO TRANSLATE   │
│                  │    │                  │
│ translate_text(  │    │ search_question  │
│   text="Comment",│    │   = question     │
│   source="fr",   │    │                  │
│   target="en"    │    └──────────────────┘
│ )                │
│                  │
│ → "How to        │
│    change the    │
│    supervisor?"  │
└──────────────────┘
       │
       │ Both paths merge
       ▼
┌──────────────────┐
│  SEARCH          │
│  Vector DB       │
│  (in English)    │
└──────────────────┘
       │
       ▼
┌──────────────────┐
│  GENERATE        │
│  (in user's      │
│   language)      │
└──────────────────┘
```

---

## 🗄️ Data Storage

```
┌────────────────────────────────────────────────────────────┐
│                     DATABASE (SQLite)                       │
├────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────┐      ┌──────────────────┐           │
│  │ UserPreference   │      │ User             │           │
│  ├──────────────────┤      ├──────────────────┤           │
│  │ id               │      │ id               │           │
│  │ user_id          │◄─────│ username         │           │
│  │ preference='lang'│      │ email            │           │
│  │ value='fr'       │      │ workspace_id     │           │
│  └──────────────────┘      └──────────────────┘           │
│                                     │                       │
│                                     │                       │
│  ┌──────────────────┐              │                       │
│  │ Conversation     │              │                       │
│  ├──────────────────┤              │                       │
│  │ id               │              │                       │
│  │ title            │              │                       │
│  │ user_id          │◄─────────────┘                       │
│  │ created_at       │                                      │
│  └────────┬─────────┘                                      │
│           │                                                 │
│           │                                                 │
│  ┌────────▼─────────┐                                      │
│  │ Message          │                                      │
│  ├──────────────────┤                                      │
│  │ id               │                                      │
│  │ question         │  ← Original question (any language) │
│  │ answer           │  ← Answer in user's language        │
│  │ latency_ms       │                                      │
│  │ conversation_id  │                                      │
│  │ user_id          │                                      │
│  └──────────────────┘                                      │
└────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────┐
│                 VECTOR STORE (Qdrant)                       │
├────────────────────────────────────────────────────────────┤
│                                                             │
│  Document Embeddings (in English)                          │
│                                                             │
│  [0.12, 0.45, -0.33, ...] ← "How to change supervisor"    │
│  [0.33, 0.21, -0.11, ...] ← "Zone configuration guide"    │
│  [0.44, 0.09, 0.22, ...]  ← "User management docs"        │
│                                                             │
│  + Metadata:                                               │
│    - workspace_id                                          │
│    - source file                                           │
│    - doc_id                                                │
└────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────┐
│                  LOG FILES (JSONL)                          │
├────────────────────────────────────────────────────────────┤
│                                                             │
│  logs/rag_interactions.jsonl                               │
│                                                             │
│  Line 1: {"timestamp": "...", "original_question": "..."}  │
│  Line 2: {"timestamp": "...", "original_question": "..."}  │
│  Line 3: {"timestamp": "...", "original_question": "..."}  │
│  ...                                                        │
│                                                             │
│  Each line = Complete interaction with:                    │
│  - Original question                                       │
│  - Translated question  ← NOW WORKING!                     │
│  - Retrieved docs                                          │
│  - Answer                                                  │
│  - All metrics                                             │
└────────────────────────────────────────────────────────────┘
```

---

## 🎯 Key Takeaways

### 1. Entry Point
```
ask_question() ← START HERE
```

### 2. The Pipeline
```
Language Detection → Translation → Search → Generation → Logging
```

### 3. The Bug Fix
```
_retrieve() now returns translated_question ✅
```

### 4. Data Flow
```
User Input → Database → Translator → Vector DB → LLM → Logger → Response
```

### 5. What Gets Logged
```
✅ Original question (any language)
✅ Translated question (English)  ← Bug fix!
✅ Source language code
✅ Response language name
✅ Retrieved documents
✅ Latencies
✅ Everything else
```

---

**Last Updated**: October 11, 2025  
**Purpose**: Visual reference for RAG system architecture  
**Status**: Bug Fixed! ✅
