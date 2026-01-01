import axios, { AxiosInstance } from 'axios';
import type {
  CopilotResponse,
  PolicySearchResponse,
  AnswerResponse,
  DebugSQLResponse,
  SQLMode,
  GroupBy,
  PolicyType,
} from '@/types/api';

class ExpenseAIAPI {
  private client: AxiosInstance;

  constructor(baseURL: string = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000') {
    this.client = axios.create({
      baseURL,
      timeout: 60000, // 60 seconds for LLM responses
      headers: {
        'Content-Type': 'application/json',
      },
    });
  }

  // Health check endpoints
  async healthCheck(): Promise<{ status: string }> {
    const response = await this.client.get('/health');
    return response.data;
  }

  async dbHealthCheck(): Promise<{ status: string; database: string }> {
    const response = await this.client.get('/db-health');
    return response.data;
  }

  // Main copilot endpoint - Primary endpoint for answering questions
  async askCopilot(params: {
    q: string;
    org?: string;
    employee_id?: string;
    case_id?: string;
    policy_type?: PolicyType;
    debug?: boolean;
  }): Promise<CopilotResponse> {
    const response = await this.client.post('/copilot/answer', null, { params });
    return response.data;
  }

  // Policy search endpoint
  async searchPolicy(params: {
    q: string;
    org?: string;
    orgs?: string;
    policy_type?: PolicyType;
    doc_name?: string;
    candidate_k?: number;
    final_k?: number;
    top_k?: number;
    debug?: boolean;
  }): Promise<PolicySearchResponse> {
    const response = await this.client.get('/policy/search', { params });
    return response.data;
  }

  // Policy answer endpoint
  async answerPolicyQuestion(params: {
    q: string;
    org?: string;
    policy_type?: PolicyType;
    doc_name?: string;
    candidate_k?: number;
    final_k?: number;
  }): Promise<AnswerResponse> {
    const response = await this.client.post('/policy/answer', null, { params });
    return response.data;
  }

  // Debug SQL endpoint
  async debugSQL(params: {
    mode: SQLMode;
    org: string;
    employee_id?: string;
    case_id?: string;
    start_date?: string;
    end_date?: string;
    group_by?: GroupBy;
    limit?: number;
    window_days?: number;
  }): Promise<DebugSQLResponse> {
    const response = await this.client.get('/debug/sql', { params });
    return response.data;
  }
}

// Create singleton instance
const api = new ExpenseAIAPI();

export default api;
export { ExpenseAIAPI };
