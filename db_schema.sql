-- Optional but handy for UUIDs later (not required)
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 1) Policy chunks for RAG (stored as text + embedding)
CREATE TABLE IF NOT EXISTS policy_chunks (
  id            BIGSERIAL PRIMARY KEY,
  doc_name      TEXT NOT NULL,
  section       TEXT,
  chunk_index   INT NOT NULL,
  content       TEXT NOT NULL,
  content_tsv   tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
  content_hash  TEXT,
  embedding     vector(1024),
  metadata      JSONB,
  page          INT,
  org           TEXT,
  policy_type   TEXT,
  section_title TEXT,
  created_at    TIMESTAMPTZ DEFAULT NOW(),
  
  -- Ensure unique citation (doc + index)
  CONSTRAINT policy_chunks_docname_chunkindex_uniq UNIQUE (doc_name, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_policy_chunks_org ON policy_chunks(org);
CREATE INDEX IF NOT EXISTS idx_policy_chunks_policy_type ON policy_chunks(policy_type);
CREATE INDEX IF NOT EXISTS idx_policy_chunks_doc_page ON policy_chunks(doc_name, page);

-- 2) Expenses (your reimbursement rows from XLSX)
CREATE TABLE IF NOT EXISTS expenses (
  id              BIGSERIAL PRIMARY KEY,
  employee_id     TEXT,
  expense_date    DATE,
  category        TEXT,
  amount          NUMERIC(12,2),
  currency        TEXT DEFAULT 'USD',
  merchant        TEXT,
  business_purpose TEXT,
  status          TEXT DEFAULT 'draft',
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 3) Workflow/events from .xes (submitted/approved/paid etc.)
CREATE TABLE IF NOT EXISTS expense_events (
  id          BIGSERIAL PRIMARY KEY,
  case_id     TEXT NOT NULL,
  activity    TEXT NOT NULL,
  ts          TIMESTAMPTZ,
  actor       TEXT,
  payload     JSONB,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 4) Receipts (store file path + OCR text; NOT the image bytes)
CREATE TABLE IF NOT EXISTS receipts (
  id            BIGSERIAL PRIMARY KEY,
  image_path    TEXT NOT NULL,
  raw_ocr_text  TEXT,
  extracted     JSONB,
  expense_id    BIGINT REFERENCES expenses(id),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 5) Audit log (tracks approve/reject/save actions)
CREATE TABLE IF NOT EXISTS audit_log (
  id          BIGSERIAL PRIMARY KEY,
  entity_type TEXT NOT NULL,
  entity_id   TEXT NOT NULL,
  action      TEXT NOT NULL,
  actor       TEXT,
  details     JSONB,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Keyword search on policy text
CREATE INDEX IF NOT EXISTS idx_policy_chunks_tsv
  ON policy_chunks USING GIN (content_tsv);

-- Vector search index (cosine). This is the standard pgvector HNSW pattern.
CREATE INDEX IF NOT EXISTS idx_policy_chunks_embedding_hnsw
  ON policy_chunks USING hnsw (embedding vector_cosine_ops);

-- Common SQL filters
CREATE INDEX IF NOT EXISTS idx_expenses_employee_date
  ON expenses (employee_id, expense_date);

CREATE INDEX IF NOT EXISTS idx_expense_events_case
  ON expense_events (case_id);
