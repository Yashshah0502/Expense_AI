# Expense AI Copilot

A Hybrid Search SQL + RAG-powered (Retrieval-Augmented Generation) assistant for navigating expense policies and automating expense reporting. This project uses intelligent question routing to provide context-aware answers from university policy documents.

## Features

### Core Capabilities
- **Intelligent Question Routing**: Automatically routes questions to appropriate handlers (SQL, RAG, or clarification)
- **Two-Stage Retrieval**: Implements a "Retrieve-then-Rerank" pipeline with hybrid search (keyword + vector) and Cross-Encoder reranking (`BAAI/bge-reranker-v2-m3`)
- **Multi-Organization Support**: Handles queries across multiple universities with automatic grouping
- **Policy Type Inference**: Detects travel vs procurement questions automatically
- **Robust Chunking**: Uses `RecursiveCharacterTextSplitter` with metadata enrichment (Doc Name, Page Number)
- **Offline Evaluation**: Quantitative metrics (**Recall@K**, **MRR**) to measure search performance
- **FastAPI Backend**: Modular and scalable API service with structured response schemas
- **Dockerized Database**: PostgreSQL with `pgvector` and HNSW indexing

### Intelligent Routing System
The system intelligently routes questions to the appropriate handler:

1. **SQL_NOT_READY**: Personal expense queries (status, reports, reimbursements)
2. **CLARIFY**: Ambiguous questions requiring university specification
3. **RAG_FILTERED**: University-specific policy queries
4. **RAG_ALL**: Cross-university comparisons and general policy questions

## Project Structure

```
Expense_AI/
├── backend/
│   ├── main.py                         # FastAPI application with router integration
│   ├── app/
│   │   ├── policy/
│   │   │   └── router_v1.py            # Intelligent question routing logic
│   │   └── schemas/
│   │       └── router.py               # Pydantic models for routing & responses
│   ├── rag/                            # RAG logic package
│   │   ├── embeddings.py               # Embedding model (BGE-M3) management
│   │   ├── rerank.py                   # Cross-Encoder (BGE-Reranker-v2-m3) logic
│   │   ├── policy_search.py            # Hybrid search + Reranking pipeline
│   │   └── answer_gen.py               # LLM-based answer generation
│   ├── eval/                           # Evaluation Suite
│   │   ├── gold.jsonl                  # Ground-truth queries and relevant chunks
│   │   └── run_eval.py                 # Metrics (Recall@K / MRR) calculator
│   ├── scripts/
│   │   └── ingest_policies.py          # Script for chunking and ingestion
│   ├── tests/
│   │   ├── test_router_v1.py           # Router unit tests (23 tests)
│   │   ├── manual_router_test.py       # Integration test demo
│   │   └── test_endpoint_integration.py # Endpoint integration tests
│   ├── test_api.py                     # Automated API test script
│   ├── check_openapi_schema.py         # OpenAPI schema verification
│   └── requirements.txt                # Python dependencies
├── data/
│   └── RAG_Data/                       # Directory for policy PDFs
├── db_schema.sql                       # Database schema definitions
└── docker-compose.yml                  # Docker Compose for PostgreSQL
```

## Setup & Installation

### 1. Prerequisites
- Docker & Docker Compose
- Python 3.11+
- OpenAI API key (for answer generation)

### 2. Database Setup
Start the PostgreSQL database with pgvector:
```bash
docker-compose up -d
```

Wait for the database to be ready:
```bash
sleep 5
```

Apply the database schema (tables, indexes, extensions):
```bash
# From the project root
cat db_schema.sql | docker exec -i expense_ai-db-1 psql -U app -d expense_copilot
```

### 3. Backend Setup
Navigate to the backend directory and set up the Python environment:
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file in `backend/` with your configuration:
```bash
# Database connection
DATABASE_URL=postgresql://app:app@localhost:5433/expense_copilot

# OpenAI API key for answer generation
OPENAI_API_KEY=your_openai_api_key_here

# Optional: LangSmith tracing
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your_langsmith_key_here
LANGSMITH_PROJECT=your_project_name
```

## Usage

### Ingesting Policies
Place your PDF policies in `data/RAG_Data/_staging/`. Then run the ingestion script:

```bash
# From backend/ directory with venv activated
python scripts/ingest_policies.py
```

This script:
- Uses `RecursiveCharacterTextSplitter` (1024 chars, 200 overlap)
- Prepends metadata to each chunk for better reranking context
- Generates embeddings using BGE-M3
- Stores vectors in PostgreSQL with pgvector

### Running Evaluation
To verify search quality (Recall and MRR):

```bash
# From backend/ directory
python eval/run_eval.py
```
*Note: The first run downloads the ~2.2GB reranker model.*

### Running the API
Start the FastAPI server:

```bash
# From backend/ directory
uvicorn main:app --reload --port 8000
```

The API will be available at:
- **API**: http://localhost:8000
- **Swagger UI (Interactive Docs)**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## API Endpoints

### Health Checks
- **`GET /health`**: API status
  ```json
  {"status": "ok"}
  ```

- **`GET /db-health`**: Database connectivity status
  ```json
  {"status": "ok", "db": 1}
  ```

### Policy Search
- **`GET /policy/search`**: Retrieve and rerank policy chunks
  ```bash
  curl "http://localhost:8000/policy/search?q=business%20class&org=Stanford&top_k=5"
  ```

  **Query Parameters**:
  - `q` (required): Search query
  - `org` (optional): Filter by university (ASU, Stanford, Yale, etc.)
  - `policy_type` (optional): Filter by type (travel, procurement)
  - `doc_name` (optional): Filter by specific document
  - `top_k` (default: 5): Number of results to return
  - `candidate_k` (default: 30): Number of candidates to retrieve before reranking
  - `debug` (default: false): Include debug information

### Policy Answer (Intelligent Routing)
- **`POST /policy/answer`**: Answer policy questions with intelligent routing

  **Example Requests**:

  **1. SQL Intent Detection**
  ```bash
  curl -X POST "http://localhost:8000/policy/answer?q=What%20is%20my%20expense%20status?"
  ```
  Response:
  ```json
  {
    "status": "needs_sql",
    "route": "SQL_NOT_READY",
    "warning": "This question needs expense/fact data (SQL)...",
    "sources": []
  }
  ```

  **2. Clarification Request**
  ```bash
  curl -X POST "http://localhost:8000/policy/answer?q=Is%20business%20class%20allowed?"
  ```
  Response:
  ```json
  {
    "status": "needs_clarification",
    "route": "CLARIFY",
    "clarify_question": "Which university policy should I use? (ASU, Columbia, ...)"
  }
  ```

  **3. University-Specific Query**
  ```bash
  curl -X POST "http://localhost:8000/policy/answer?q=For%20Stanford%2C%20is%20business%20class%20allowed?"
  ```
  Response:
  ```json
  {
    "status": "ok",
    "route": "RAG_FILTERED",
    "filters": {"org": "Stanford", "policy_type": null, "doc_name": null},
    "answer": "According to Stanford's policy...",
    "sources": [
      {
        "doc_name": "stanford_travel.pdf",
        "org": "Stanford",
        "page": 5,
        "text_snippet": "Business class is allowed...",
        "score": 0.95
      }
    ]
  }
  ```

  **4. Multi-University Comparison**
  ```bash
  curl -X POST "http://localhost:8000/policy/answer?q=Compare%20ASU%20vs%20Yale%20meal%20per%20diem"
  ```
  Response:
  ```json
  {
    "status": "ok",
    "route": "RAG_ALL",
    "filters": {"org": null, "policy_type": "travel", "doc_name": null},
    "answer": "ASU: Meal per diem is $75/day...\n\nYale: Meal per diem is $85/day...",
    "sources": [
      {"org": "ASU", ...},
      {"org": "Yale", ...}
    ]
  }
  ```

  **Query Parameters**:
  - `q` (required): User question
  - `org` (optional): Explicit university filter (overrides inference)
  - `policy_type` (optional): Explicit policy type (travel/procurement)
  - `doc_name` (optional): Specific document filter
  - `candidate_k` (default: 30): Number of candidates to retrieve
  - `final_k` (default: 5): Number of sources to use for answer

### Response Schema

All `/policy/answer` responses follow this structure:

```typescript
{
  status: "ok" | "needs_clarification" | "needs_sql" | "no_results",
  query: string,
  route: "RAG_FILTERED" | "RAG_ALL" | "CLARIFY" | "SQL_NOT_READY",
  filters: {
    org: string | null,
    policy_type: string | null,
    doc_name: string | null
  },
  answer?: string,              // LLM-generated answer (for status="ok")
  sources?: [                   // Source documents
    {
      doc_name: string,
      org: string,
      page: number | string,
      text_snippet: string,
      score: number | null
    }
  ],
  clarify_question?: string,    // For status="needs_clarification"
  warning?: string              // For errors or warnings
}
```

## Routing Logic

### How Questions Are Routed

The system uses a multi-step decision process:

```
User Question
     ↓
1. SQL Intent Check
   ├─ HAS: "my expense", "status", "report" → SQL_NOT_READY
   └─ NO SQL INTENT → Continue
     ↓
2. Extract Organizations
   ├─ Found 2+ orgs (e.g., "ASU vs Yale") → RAG_ALL
   ├─ Found 1 org (e.g., "For Stanford") → RAG_FILTERED
   └─ Found 0 orgs → Continue
     ↓
3. Check Explicit Parameters
   ├─ org parameter provided → RAG_FILTERED
   └─ No explicit org → Continue
     ↓
4. Single Answer Expected?
   ├─ YES: "is allowed", "can I" → CLARIFY
   └─ NO → RAG_ALL (answer across all universities)
```

### Supported Universities

The router recognizes these universities and their aliases:

- **ASU**: "ASU", "Arizona State", "Arizona State University"
- **Columbia**: "Columbia", "Columbia University"
- **Michigan**: "Michigan", "University of Michigan", "UMich"
- **Yale**: "Yale", "Yale University"
- **Princeton**: "Princeton", "Princeton University"
- **NYU**: "NYU", "New York University"
- **Stanford**: "Stanford", "Stanford University"
- **Rutgers**: "Rutgers", "Rutgers University"

### Policy Type Detection

Automatically infers policy type from keywords:

- **Travel**: flight, hotel, lodging, rental car, mileage, per diem, airfare
- **Procurement**: procurement, p-card, purchase, vendor, invoice

## Testing

### Quick Test via Swagger UI
1. Start the server: `uvicorn main:app --reload`
2. Visit: http://localhost:8000/docs
3. Try these test questions:
   - SQL Intent: `"What is my expense status for report 123?"`
   - Clarify: `"Is business class allowed?"`
   - Filtered: `"For Stanford, is business class allowed?"`
   - Multi-org: `"Compare ASU vs Yale meal per diem"`

### Automated Test Suite

**Run Unit Tests** (23 tests for router logic):
```bash
cd backend
pytest tests/test_router_v1.py -v
```

**Run Integration Tests**:
```bash
cd backend/tests
python manual_router_test.py
```

**Run Full API Tests** (requires running server):
```bash
# Terminal 1: Start server
uvicorn main:app --reload

# Terminal 2: Run tests
python test_api.py
```

Expected output:
```
🧪 TESTING /policy/answer ENDPOINT WITH ROUTER INTEGRATION
======================================================================
✓ Server is healthy

TEST 1: SQL Intent Detection (Route: SQL_NOT_READY)
✅ PASS: SQL intent correctly detected

TEST 2: Clarification Request (Route: CLARIFY)
✅ PASS: Clarification correctly requested

...

📊 TEST SUMMARY
Tests Run: 9
Tests Passed: 9
Success Rate: 100.0%
🎉 ALL TESTS PASSED!
```

### Verify OpenAPI Schema

Check that the Swagger UI shows proper source structure:
```bash
python check_openapi_schema.py
```

Should show proper fields instead of generic `additionalProp1: {}`

## Example Test Questions

### By Route Type

**SQL Intent (Personal Queries)**:
- "What is my expense status for report 123?"
- "Show me my submitted expenses"
- "How much did I spend last month?"

**Clarification Needed**:
- "Is business class allowed?"
- "Can I get reimbursed for rental car insurance?"
- "What is the meal per diem?"

**University-Specific**:
- "For Stanford, is business class allowed?"
- "What is ASU's meal per diem policy?"
- "Does Yale allow alcohol on business meals?"
- "What are Michigan's lodging limits?"

**Multi-University Comparison**:
- "Compare ASU vs Yale meal per diem"
- "What's the difference between Stanford and Princeton travel policies?"
- "Columbia vs NYU lodging limits"

### By Policy Type

**Travel Policies**:
- "What are the flight booking policies for Michigan?"
- "Can I book a rental car for Stanford?"
- "Yale hotel lodging limits"

**Procurement Policies**:
- "What is Rutgers' p-card policy?"
- "How do I submit a vendor invoice for Princeton?"
- "Columbia procurement approval process"

## Technology Stack

### Backend
- **Language**: Python 3.11
- **Framework**: FastAPI (with Pydantic v2)
- **Database**: PostgreSQL 16 + pgvector
- **Embeddings**: BAAI/bge-m3
- **Reranker**: BAAI/bge-reranker-v2-m3
- **LLM**: OpenAI GPT-4o-mini
- **Orchestration**: Docker Compose

### Key Features
- **Structured Responses**: Pydantic models with full OpenAPI schema
- **Intelligent Routing**: Rule-based + pattern matching for question classification
- **Multi-Org Grouping**: LLM automatically groups answers by university when comparing policies
- **Type Safety**: Full type hints and validation throughout

## Architecture

### Request Flow

```
User Question
     ↓
FastAPI Endpoint (/policy/answer)
     ↓
route_question() → RouterDecision
     ↓
    ┌────────────┬──────────────┬────────────┐
    │            │              │            │
SQL_NOT_READY  CLARIFY    RAG_FILTERED  RAG_ALL
    │            │              │            │
Return         Return      generate_answer() │
needs_sql      needs_       ↓                │
               clarify   hybrid_search()     │
                         ↓                   │
                      rerank()               │
                         ↓                   │
                      LLM (GPT-4o-mini)      │
                         ↓                   │
                      Return answer          │
                      + sources              │
                         ←───────────────────┘
```

### Data Flow

```
PDF Documents
     ↓
ingest_policies.py
     ├─ RecursiveCharacterTextSplitter
     ├─ Metadata Extraction (doc_name, page, org)
     ├─ BGE-M3 Embeddings
     └─ PostgreSQL + pgvector (HNSW index)
     ↓
hybrid_search() (BM25 + Vector Search)
     ↓
BGE-Reranker-v2-m3 (Cross-Encoder)
     ↓
Top-K Results → LLM Context
     ↓
GPT-4o-mini Answer Generation
     ↓
Structured Response (AnswerResponse model)
```

## Performance Metrics

### Retrieval Quality (from offline evaluation)

| Metric | Before Reranking | After Reranking |
|--------|------------------|-----------------|
| Recall@5 | 0.70 | 1.00 |
| MRR | 0.525 | 1.00 |

### Router Accuracy

- 23/23 unit tests passing
- 100% route classification accuracy on test set
- Handles 8 universities with alias recognition
- Detects 2 policy types (travel, procurement)

## Troubleshooting

### Database Not Running
```bash
# Check if database is running
docker ps | grep expense_ai-db

# If not running, start it
docker-compose up -d

# Wait and verify
sleep 3
docker ps | grep expense_ai-db
```

### Server Won't Start
```bash
# Check if port 8000 is in use
lsof -i :8000

# Kill process if needed
kill -9 <PID>

# Or use different port
uvicorn main:app --reload --port 8001
```

### OpenAI API Errors
- Ensure `OPENAI_API_KEY` is set in `.env`
- Check API credits at https://platform.openai.com/usage
- RAG routes require LLM calls (SQL/CLARIFY routes don't)

### No Sources Returned
- Verify database has ingested documents
- Check org name matches database values (case-sensitive)
- Try broader queries without filters

### Import Errors
```bash
# Make sure you're in the virtual environment
source .venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

## Project Highlights

### OpenAPI Schema Fix
**Before**: Swagger UI showed generic `additionalProp1: {}` for sources
**After**: Proper schema with field names, types, descriptions, and examples

This was achieved by creating a dedicated `Source` Pydantic model instead of using `List[Dict[str, Any]]`.

### Intelligent Routing
The router handles complex scenarios:
- ✅ Detects personal vs policy queries
- ✅ Extracts university names from natural language
- ✅ Recognizes university aliases
- ✅ Infers policy types from keywords
- ✅ Handles multi-university comparisons
- ✅ Explicit parameters override inference
- ✅ Asks for clarification when needed

### Multi-Org Grouping
When comparing universities, the LLM automatically:
- Groups answers by organization
- Shows each university's policy separately
- Provides unified answer if policies are the same
- Includes citations from all relevant sources

## Future Enhancements

1. **SQL Integration**: Implement actual SQL query handling for `Route.SQL_NOT_READY`
2. **Caching**: Add response caching for common queries
3. **Logging**: Structured logging for route decisions and debugging
4. **Enhanced Grouping**: Side-by-side comparison formatting for multi-org responses
5. **More Universities**: Expand to additional institutions
6. **Advanced Filters**: Support for date ranges, budget thresholds, etc.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `pytest tests/ -v`
5. Submit a pull request

## License

MIT License - see LICENSE file for details

## Support

For issues, questions, or contributions, please open an issue on GitHub.

---

**Built with ❤️ using FastAPI, PostgreSQL, and OpenAI**
