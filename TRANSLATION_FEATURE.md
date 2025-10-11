# Translation Feature Documentation

## Overview

This document describes the automatic translation feature implemented in the RAG (Retrieval-Augmented Generation) pipeline. The feature ensures that all document searches are performed in English, regardless of the user's query language, while responses are generated in the user's preferred language.

## Key Features

1. **Automatic Translation to English for Retrieval**: Non-English user queries are automatically translated to English before performing semantic search in the vector database
2. **Language Preference Management**: User language preferences are stored in the database and automatically applied
3. **Comprehensive Logging**: All translation activities are logged with before/after states for analytics and debugging
4. **Bilingual Response Generation**: Responses are generated in the user's preferred language

## Architecture

### Components Modified

#### 1. RAG Service (`services/rag_service.py`)

**State Structure Updates:**
```python
class State(TypedDict):
    question: str                    # Current working question
    original_question: str           # Original question before translation
    context: List[Document]          # Retrieved documents
    answer: str                      # Generated response
    retrieval_latency_ms: Optional[int]
    generation_latency_ms: Optional[int]
    retrieved_docs_info: List[dict]
    workspace_id: Optional[int]
    language: str                    # User's preferred language for response
    source_language: str             # Detected/configured source language
    was_translated: bool             # Translation occurrence flag
```

**Key Methods:**

##### `ask_question()`
- Fetches user's language preference from `UserPreference` table
- Maps language codes (e.g., 'fr', 'en', 'ar') to full names
- Passes language information to the RAG graph
- Returns metrics including translation details

##### `_retrieve()`
- Translates non-English questions to English using `translator.translate_text()`
- Performs semantic search with the English translation
- Logs translation process
- Falls back to original question if translation fails

**Translation Logic:**
```python
# Only translate if source language is not English
if source_lang != "en" and source_lang.lower() != "english":
    try:
        logger.info(f"Translating question from {source_lang} to English...")
        search_question = translate_text(
            state["question"], 
            source=source_lang, 
            target="en"
        )
        logger.info(f"Translated question: {search_question[:50]}...")
    except Exception as e:
        logger.error(f"Translation failed, using original question: {e}")
        search_question = state["question"]
```

#### 2. RAG Logger (`services/rag_logger.py`)

**Enhanced Log Entry:**
```python
@dataclass
class RAGLogEntry:
    # ... existing fields ...
    
    # Translation tracking fields
    source_language: Optional[str]      # Language of input (e.g., 'fr', 'en')
    response_language: Optional[str]    # Language for response (e.g., 'French')
    was_translated: Optional[bool]      # Whether translation occurred
    original_question: Optional[str]    # Question before translation
    translated_question: Optional[str]  # Question after translation (for search)
```

**Updated Method:**
- `log_interaction()` now accepts and logs all translation-related parameters
- Provides full visibility into the translation process
- Enables analysis of translation accuracy and performance

#### 3. Chat Router (`routers/chat_router.py`)

**Updates:**
- Passes translation metrics from RAG service to logger
- Ensures all translation data flows through the logging pipeline

```python
rag_logger.log_interaction(
    # ... existing parameters ...
    source_language=rag_metrics.get("source_language"),
    response_language=rag_metrics.get("response_language"),
    was_translated=rag_metrics.get("was_translated"),
    original_question=rag_metrics.get("original_question"),
    translated_question=rag_metrics.get("translated_question")
)
```

## Database Schema

### UserPreference Table

The `UserPreference` table stores user language settings:

```python
class UserPreference(SQLModel, table=True):
    id: Optional[int]
    user_id: int                    # Foreign key to User
    preference: str                 # 'language'
    value: str                      # Language code ('en', 'fr', 'ar', etc.)
    created_at: datetime
    updated_at: datetime
```

**Example Records:**
```sql
INSERT INTO userpreference (user_id, preference, value) 
VALUES (1, 'language', 'fr');

INSERT INTO userpreference (user_id, preference, value) 
VALUES (2, 'language', 'ar');

INSERT INTO userpreference (user_id, preference, value) 
VALUES (3, 'language', 'en');
```

## Language Code Mapping

The system uses ISO 639-1 language codes internally:

| Code | Full Name | Response Language |
| ---- | --------- | ----------------- |
| `en` | English   | English           |
| `fr` | French    | French            |
| `ar` | Arabic    | Arabic            |

## Translation Flow

### Step-by-Step Process

1. **User Query Received**
   - User asks a question in their preferred language
   - Example: "Comment puis-je changer le superviseur d'une zone?"

2. **Language Preference Lookup**
   - System queries `UserPreference` table for user's language
   - Retrieves language code (e.g., 'fr')
   - Maps to both code format ('fr') and full name ('French')

3. **Translation Decision**
   ```python
   if source_language != "en":
       # Translate to English for search
       translated_question = translate_text(question, source='fr', target='en')
   else:
       # Use original question
       translated_question = question
   ```

4. **Document Retrieval**
   - Semantic search performed using English translation
   - Ensures consistent search results across all languages
   - Example translated query: "How can I change the supervisor of a zone?"

5. **Response Generation**
   - LLM generates response in user's preferred language
   - Prompt template includes language specification
   - Example response generated in French

6. **Logging**
   - All details logged to `logs/rag_interactions.jsonl`
   - Includes original question, translated question, and language metadata

## Log File Format

Each interaction is logged as a JSON object in `logs/rag_interactions.jsonl`:

```json
{
  "timestamp": "2025-10-11T14:30:45.123456Z",
  "session_id": "uuid-here",
  "user_id": "1",
  "user_query": "Comment puis-je changer le superviseur?",
  "original_question": "Comment puis-je changer le superviseur?",
  "translated_question": "How can I change the supervisor?",
  "source_language": "fr",
  "response_language": "French",
  "was_translated": true,
  "retrieved_docs": [...],
  "response": "Pour changer le superviseur...",
  "latency_ms": 1250,
  "retrieval_latency_ms": 450,
  "generation_latency_ms": 800,
  "model_name": "gemini-1.5-flash",
  "num_retrieved": 3
}
```

## Benefits

### 1. **Improved Search Accuracy**
- Consistent English-based semantic search
- Better retrieval quality across languages
- Unified vector space

### 2. **User Experience**
- Seamless multilingual support
- Users can ask questions in their native language
- Responses in preferred language

### 3. **Analytics & Debugging**
- Complete visibility into translation process
- Track translation performance
- Analyze language-specific patterns
- Debug retrieval issues by comparing original and translated queries

### 4. **Scalability**
- Easy to add new languages
- Centralized translation logic
- Consistent approach across all endpoints

## Error Handling

### Translation Failures
```python
try:
    search_question = translate_text(state["question"], source=source_lang, target="en")
except Exception as e:
    logger.error(f"Translation failed, using original question: {e}")
    search_question = state["question"]  # Fallback to original
```

### Missing Language Preference
- System defaults to English if no preference found
- Logged for monitoring: `"No language preference found for user {user_id}, using default: English"`

### Database Errors
- Gracefully handles DB connection issues
- Falls back to default language
- Logs errors for investigation

## Usage Examples

### Setting User Language Preference

```python
from models import UserPreference
from db import get_session

session = next(get_session())

# Set French as user's language
pref = UserPreference(
    user_id=1,
    preference="language",
    value="fr"
)
session.add(pref)
session.commit()
```

### Querying with Translation

```python
from services.rag_service import get_rag_service

rag_service = get_rag_service()

# User asks in French
answer, metrics = rag_service.ask_question(
    question="Où puis-je trouver le rapport de statistiques?",
    workspace_id=2,
    user_id=1
)

# Check translation details
print(f"Was translated: {metrics['was_translated']}")
print(f"Original: {metrics['original_question']}")
print(f"Translated: {metrics['translated_question']}")
print(f"Source language: {metrics['source_language']}")
```

### Analyzing Translation Logs

```python
import json

# Read translation logs
with open('logs/rag_interactions.jsonl', 'r') as f:
    for line in f:
        log = json.loads(line)
        if log.get('was_translated'):
            print(f"Original: {log['original_question']}")
            print(f"Translated: {log['translated_question']}")
            print(f"Language: {log['source_language']}")
            print("---")
```

## Configuration

### Supported Languages

Currently configured languages in the translator module:
- English (en)
- French (fr)
- Arabic (ar)

### Adding New Languages

1. **Install Language Package** (in `translator.py`):
```python
from_code = "es"  # Spanish
to_code = "en"
# Install package...
```

2. **Update Language Map** (in `rag_service.py`):
```python
language_map = {
    "en": "English",
    "fr": "French",
    "ar": "Arabic",
    "es": "Spanish",  # Add new language
}
```

3. **Update User Preference**:
```sql
INSERT INTO userpreference (user_id, preference, value) 
VALUES (user_id, 'language', 'es');
```

## Performance Considerations

### Translation Latency
- Translation adds ~100-300ms to retrieval time
- Logged separately in `retrieval_latency_ms`
- Acceptable trade-off for improved accuracy

### Caching Opportunities
- Consider caching frequently translated queries
- Implement translation cache with TTL
- Reduce redundant translation API calls

## Testing

### Test Cases

1. **English Query (No Translation)**
   - Input: "How do I change the supervisor?"
   - Expected: No translation, direct search
   - Verify: `was_translated = False`

2. **French Query (With Translation)**
   - Input: "Comment changer le superviseur?"
   - Expected: Translates to English, searches, responds in French
   - Verify: `was_translated = True`, translation logged

3. **Missing Language Preference**
   - Input: User with no preference
   - Expected: Defaults to English
   - Verify: Logs default language usage

4. **Translation Failure**
   - Simulate translation error
   - Expected: Falls back to original query
   - Verify: Error logged, search continues

## Monitoring

### Key Metrics to Track

1. **Translation Rate**: Percentage of queries requiring translation
2. **Translation Latency**: Average time for translation
3. **Translation Errors**: Failed translations
4. **Language Distribution**: Most common query languages
5. **Search Quality**: Compare retrieval quality with/without translation

### Log Analysis Queries

```python
# Count translations by language
translations = {}
with open('logs/rag_interactions.jsonl', 'r') as f:
    for line in f:
        log = json.loads(line)
        if log.get('was_translated'):
            lang = log.get('source_language', 'unknown')
            translations[lang] = translations.get(lang, 0) + 1

print("Translations by language:", translations)
```

## Troubleshooting

### Issue: Translation Not Working

**Check:**
1. Is `translator` module installed and configured?
2. Is language preference set in database?
3. Check logs for translation errors
4. Verify language code is supported

### Issue: Wrong Language in Response

**Check:**
1. Verify `response_language` in logs
2. Check prompt template language parameter
3. Ensure LLM supports target language

### Issue: Poor Search Results

**Check:**
1. Compare `original_question` vs `translated_question` in logs
2. Verify translation quality
3. Test English query directly
4. Check vector embeddings

## Future Enhancements

1. **Automatic Language Detection**: Detect language without user preference
2. **Translation Quality Scoring**: Rate translation accuracy
3. **Multi-language Document Search**: Support documents in multiple languages
4. **Translation Cache**: Cache common translations
5. **Fallback Languages**: Support multiple preference languages
6. **Real-time Translation Metrics**: Dashboard for translation analytics

## Conclusion

The translation feature provides seamless multilingual support while maintaining search quality through English-based retrieval. Comprehensive logging enables monitoring and continuous improvement of the translation pipeline.

---

**Last Updated**: October 11, 2025  
**Version**: 1.0  
**Author**: Development Team
