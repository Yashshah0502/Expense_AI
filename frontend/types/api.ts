// TypeScript types for backend API

export interface PolicySource {
  doc_name: string;
  org: string;
  policy_type?: string;
  page?: number;
  chunk_index?: number;
  score?: number;
  snippet?: string;
  content?: string;
}

export interface SQLExpense {
  expense_id: number;
  employee_id: string;
  expense_date: string;
  amount: string | number;
  currency: string;
  category: string;
  merchant: string;
  receipt_id?: string;
  report_id?: string;
  description?: string;
}

export interface SQLTotal {
  group: string;
  currency: string;
  total: number;
  count: number;
}

export interface SQLEvent {
  event_id: number;
  case_id: string;
  event_index: number;
  activity: string;
  event_time: string;
  attributes?: Record<string, any>;
}

export interface SQLDuplicate {
  receipt_id?: string;
  count: number;
  total: number;
  first_date: string;
  last_date: string;
  duplicate_type: string;
}

export interface SQLResults {
  totals?: SQLTotal[] | null;
  samples?: SQLExpense[] | null;
  timeline?: SQLEvent[] | null;
  duplicates?: SQLDuplicate[] | null;
}

export interface Routing {
  used_policy?: boolean;
  used_sql?: boolean;
  tools_called?: string[];
}

export interface CopilotResponse {
  answer: string;
  routing?: Routing;
  policy_sources?: PolicySource[];
  sql_results?: SQLResults;
  follow_up?: string | null;
  warnings?: string[];
}

export interface PolicySearchResult {
  doc_name: string;
  chunk_index: number;
  content: string;
  snippet: string;
  page?: number;
  org?: string;
  score?: number;
}

export interface PolicySearchResponse {
  results: PolicySearchResult[];
  warning?: string | null;
}

export interface Source {
  doc_name: string;
  org: string;
  page?: number;
  text_snippet: string;
  score?: number;
}

export interface AnswerResponse {
  status: 'ok' | 'needs_clarification' | 'needs_sql' | 'no_results';
  query: string;
  route?: string;
  filters?: {
    org?: string | null;
    policy_type?: string | null;
    doc_name?: string | null;
  };
  answer?: string;
  sources?: Source[];
  clarify_question?: string | null;
  warning?: string | null;
}

export interface DebugSQLResponse {
  ok: boolean;
  data: SQLTotal[] | SQLExpense[] | SQLEvent[] | SQLDuplicate[];
  warning?: string | null;
}

export type SQLMode = 'expenses_totals' | 'expenses_sample' | 'events_timeline' | 'duplicates';

export type GroupBy = 'category' | 'merchant' | 'currency' | 'employee_id' | 'report_id';

export type PolicyType = 'travel' | 'procurement' | 'general';

export const ORGANIZATIONS = [
  'ASU',
  'STANFORD',
  'YALE',
  'COLUMBIA',
  'MICHIGAN',
  'PRINCETON',
  'NYU',
  'RUTGERS',
] as const;

export type Organization = typeof ORGANIZATIONS[number];
