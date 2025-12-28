-- Migration 003: Create expense tables with proper idempotency support
-- This migration alters the existing expenses and expense_events tables to support robust ingestion

-- Drop existing tables if they exist (for clean migration)
DROP TABLE IF EXISTS expenses CASCADE;
DROP TABLE IF EXISTS expense_events CASCADE;

-- Table: expenses
-- Stores structured expense data from XLSX files
CREATE TABLE expenses (
  expense_id BIGSERIAL PRIMARY KEY,
  org TEXT NOT NULL,
  source_file TEXT NOT NULL,
  source_row INT NOT NULL,
  employee_id TEXT,
  report_id TEXT,
  expense_date DATE,
  category TEXT,
  merchant TEXT,
  description TEXT,
  amount NUMERIC(12,2),
  currency TEXT NOT NULL DEFAULT 'USD',
  receipt_id TEXT,
  row_hash TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

  -- Ensure uniqueness per source
  CONSTRAINT expenses_org_source_row_uniq UNIQUE (org, source_file, source_row)
);

-- Indexes for common query patterns
CREATE INDEX idx_expenses_org_date ON expenses(org, expense_date);
CREATE INDEX idx_expenses_employee_date ON expenses(employee_id, expense_date);
CREATE INDEX idx_expenses_report ON expenses(report_id);
CREATE INDEX idx_expenses_row_hash ON expenses(row_hash);

-- Table: expense_events
-- Stores process mining events from XES files
CREATE TABLE expense_events (
  event_id BIGSERIAL PRIMARY KEY,
  org TEXT NOT NULL,
  source_file TEXT NOT NULL,
  case_id TEXT NOT NULL,
  event_index INT NOT NULL,
  activity TEXT NOT NULL,
  event_time TIMESTAMPTZ,
  attributes JSONB,
  event_hash TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

  -- Ensure uniqueness per event in trace
  CONSTRAINT expense_events_org_source_case_index_uniq UNIQUE (org, source_file, case_id, event_index)
);

-- Indexes for process mining queries
CREATE INDEX idx_expense_events_case_time ON expense_events(case_id, event_time);
CREATE INDEX idx_expense_events_activity ON expense_events(activity);
CREATE INDEX idx_expense_events_event_hash ON expense_events(event_hash);
CREATE INDEX idx_expense_events_org ON expense_events(org);
