# Expense AI Copilot

A Hybrid Search  SQL + RAG-powered (Retrieval-Augmented Generation) assistant for navigating expense policies and automating expense reporting. This project uses a hybrid search approach (SQL + Vector Search) to find relevant policy information.

## Features

- **Hybrid Search**: Combines PostgreSQL full-text search and `pgvector` similarity search for accurate policy retrieval.
- **RAG Pipeline**: PDF ingestion, chunking, and embedding using `BAAI/bge-m3` (1024 dimensions).
- **FastAPI Backend**: Modular and scalable API service.
- **Dockerized Database**: PostgreSQL with `pgvector` extension enabled.

## Project Structure

```
Expense_AI/
├── backend/
│   ├── main.py                 # FastAPI application and matching logic
│   ├── rag/                    # RAG logic package
│   │   ├── embeddings.py       # Embedding model management
│   │   └── policy_search.py    # Keyword, Vector, and Hybrid search implementation
│   ├── scripts/
│   │   └── ingest_policies.py  # Script to ingest PDFs into the DB
│   └── requirements.txt        # Python dependencies
├── data/
│   └── RAG_Data/               # Directory for policy PDFs
├── db_schema.sql               # Database schema definitions
└── docker-compose.yml          # Docker Compose for PostgreSQL
```

## Setup & Installation

### 1. Prerequisites
- Docker & Docker Compose
- Python 3.11+

### 2. Database Setup
Start the PostgreSQL database:
```bash
docker compose up -d
```

Apply the database schema (tables, indexes, extensions):
```bash
# From the project root
cat db_schema.sql | docker compose exec -T db psql -U app -d expense_copilot
```

### 3. Backend Setup
Navigate to the backend directory and set up the Python environment:
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file in `backend/` with your database connection string:
```bash
echo "DATABASE_URL=postgresql://app:expense_secret@localhost:5432/expense_copilot" > .env
```

## Usage

### Ingesting Policies
Place your PDF policies in `data/RAG_Data/_staging/`. Then run the ingestion script:

```bash
# From backend/ directory with venv activated
python scripts/ingest_policies.py
```
This will parse the PDFs, chunk text, generate embeddings, and store them in the database.

### Running the API
Start the FastAPI server:

```bash
# From backend/ directory
uvicorn main:app --reload --port 8000
```
The API will be available at `http://localhost:8000`.

### API Endpoints

- **Health Checks**:
  - `GET /health`: API status.
  - `GET /db-health`: Database connectivity status.

- **Policy Search**:
  - `GET /policy/search?q=query_text&top_k=5`
  - Returns a ranked list of policy chunks matching the query using hybrid search.

## Technology Stack
- **Language**: Python 3.11
- **Framework**: FastAPI
- **Database**: PostgreSQL + pgvector
- **Embeddings**: BAAI/bge-m3 (via sentence-transformers)
- **Orchestration**: Docker Compose
