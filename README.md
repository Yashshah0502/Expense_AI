# Expense AI Copilot

A Hybrid Search  SQL + RAG-powered (Retrieval-Augmented Generation) assistant for navigating expense policies and automating expense reporting. This project uses a hybrid search approach (SQL + Vector Search) to find relevant policy information.

## Features

- **Two-Stage Retrieval**: Implements a "Retrieve-then-Rerank" pipeline. Candidates are first fetched via hybrid search (keyword + vector) and then re-scored using a Cross-Encoder reranker (`BAAI/bge-reranker-v2-m3`).
- **Robust Chunking**: Uses `RecursiveCharacterTextSplitter` with metadata enrichment (Doc Name, Page Number) for high-precision retrieval.
- **Offline Evaluation**: Quantitative metrics (**Recall@K**, **MRR**) to measure search performance against a "gold set" of ground-truth questions.
- **FastAPI Backend**: Modular and scalable API service.
- **Dockerized Database**: PostgreSQL with `pgvector` and HNSW indexing.

## Project Structure

```
Expense_AI/
├── backend/
│   ├── main.py                 # FastAPI application and matching logic
│   ├── rag/                    # RAG logic package
│   │   ├── embeddings.py       # Embedding model (BGE-M3) management
│   │   ├── rerank.py           # Cross-Encoder (BGE-Reranker-v2-m3) logic
│   │   └── policy_search.py    # Hybrid search + Reranking pipeline
│   ├── eval/                   # Evaluation Suite
│   │   ├── gold.jsonl          # Ground-truth queries and relevant chunks
│   │   └── run_eval.py         # Metrics (Recall@K / MRR) calculator
│   ├── scripts/
│   │   └── ingest_policies.py  # Script for chunking and ingestion
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
This script uses a `RecursiveCharacterTextSplitter` (1024 chars, 200 overlap) and prepends metadata to each chunk for better reranking context.

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
The API will be available at `http://localhost:8000`.

### API Endpoints

- **Health Checks**:
  - `GET /health`: API status.
  - `GET /db-health`: Database connectivity status.

- **Policy Search (Retrieve + Rerank)**:
  - `GET /policy/search?q=query_text&top_k=5`
  - Fetches 30 candidates and returns top 5 reranked results with `rerank_score`.

## Technology Stack
- **Language**: Python 3.11
- **Framework**: FastAPI
- **Database**: PostgreSQL + pgvector
- **Embeddings**: BAAI/bge-m3
- **Reranker**: BAAI/bge-reranker-v2-m3
- **Orchestration**: Docker Compose
