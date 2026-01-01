# Expense AI

An intelligent expense policy assistant powered by hybrid search and retrieval-augmented generation (RAG). Query university expense policies and get instant, accurate answers with citations.

## Overview

Expense AI combines semantic search, keyword matching, and LLM-based answer generation to help users navigate complex university expense policies. The system intelligently routes questions to the appropriate data source and provides contextual answers with source citations.

### Key Features

- **Intelligent Question Routing** - Automatically determines whether to use policy documents or expense data
- **Multi-Organization Support** - Compare policies across multiple universities in a single query
- **Hybrid Search** - Combines vector embeddings (BGE-M3) and BM25 keyword search for optimal retrieval
- **Cross-Encoder Reranking** - Uses BGE-Reranker-v2-m3 for improved result quality
- **Web Interface** - Modern Next.js frontend for easy interaction
- **REST API** - FastAPI backend with comprehensive endpoints

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.11+
- Node.js 18+ (for frontend)
- OpenAI API key

### 1. Start the Database

```bash
docker-compose up -d
sleep 5
cat db_schema.sql | docker exec -i expense_ai-db-1 psql -U app -d expense_copilot
```

### 2. Setup Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create `backend/.env`:
```env
DATABASE_URL=postgresql://app:app@localhost:5433/expense_copilot
OPENAI_API_KEY=your_openai_key_here
```

### 3. Ingest Policy Documents

Place PDF files in `data/RAG_Data/_staging/` and run:

```bash
python scripts/ingest_policies.py
```

### 4. Start the Backend

```bash
uvicorn main:app --reload --port 8001
```

### 5. Setup Frontend

```bash
cd ../frontend
npm install
```

Create `frontend/.env.local`:
```env
NEXT_PUBLIC_API_URL=http://localhost:8001
```

### 6. Start the Frontend

```bash
npm run dev
```

Visit http://localhost:3000 to use the application.

## Project Structure

```
Expense_AI/
├── backend/                 # FastAPI application
│   ├── main.py             # API endpoints and routing
│   ├── app/                # Application logic
│   ├── rag/                # Retrieval and generation
│   ├── scripts/            # Ingestion and utilities
│   └── tests/              # Test suite
├── frontend/               # Next.js web application
│   ├── app/               # Next.js pages
│   ├── components/        # React components
│   ├── lib/               # API client
│   └── types/             # TypeScript definitions
├── data/                  # Policy documents and data
├── database/              # Database migrations
└── docker-compose.yml     # PostgreSQL with pgvector
```

## API Endpoints

### Health Check
```bash
curl http://localhost:8001/health
```

### Search Policies
```bash
curl "http://localhost:8001/policy/search?q=travel+reimbursement&org=Stanford&top_k=5"
```

### Answer Questions
```bash
curl -X POST "http://localhost:8001/policy/answer?q=What+is+Stanford's+travel+policy?"
```

### Copilot (Unified)
```bash
curl -X POST "http://localhost:8001/copilot/answer?q=Show+my+expense+report&employee_id=12345"
```

## Question Routing

The system automatically routes questions based on content:

- **SQL Route** - Personal expense queries ("my expenses", "status")
- **Clarify Route** - Ambiguous questions requiring org specification
- **RAG Filtered** - University-specific policy questions
- **RAG All** - Cross-university comparisons

## Technology Stack

**Backend:**
- FastAPI (Python)
- PostgreSQL + pgvector
- OpenAI GPT-4o-mini
- BAAI/BGE-M3 embeddings
- BAAI/BGE-Reranker-v2-m3

**Frontend:**
- Next.js 14
- React 18
- TypeScript
- Tailwind CSS

## Testing

Run backend tests:
```bash
cd backend
pytest tests/ -v
```

Run evaluation metrics:
```bash
python eval/run_eval.py
```

## Configuration

### Backend Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `OPENAI_API_KEY` | OpenAI API key | Yes |
| `LANGSMITH_TRACING` | Enable LangSmith tracing | No |
| `LANGSMITH_API_KEY` | LangSmith API key | No |

### Frontend Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `NEXT_PUBLIC_API_URL` | Backend API URL | Yes |

## Performance

- **Recall@5**: 1.00 (with reranking)
- **MRR**: 1.00 (with reranking)
- **Route Accuracy**: 100% on test set
- **Response Time**: < 2s average

## Deployment

### Frontend (Vercel)

1. Push to GitHub
2. Import repository on Vercel
3. Set root directory to `frontend`
4. Add `NEXT_PUBLIC_API_URL` environment variable
5. Deploy

### Backend Options

- Railway (recommended for simplicity)
- Render
- AWS/GCP
- Fly.io

## License

MIT License

## Support

For questions or issues, please open a GitHub issue.
