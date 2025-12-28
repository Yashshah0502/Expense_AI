"""
Integration tests for /policy/answer endpoint with router
Tests the endpoint behavior without requiring database or external services
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from main import app
from app.schemas.router import Route


client = TestClient(app)


class TestPolicyAnswerEndpoint:
    """Test /policy/answer endpoint integration with router"""

    def test_health_endpoint(self):
        """Sanity check that the app is working"""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    @patch("main.generate_answer")
    def test_sql_intent_returns_needs_sql(self, mock_generate):
        """Questions with SQL intent should return needs_sql status"""
        response = client.post("/policy/answer?q=What is my expense status for report 123?")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "needs_sql"
        assert data["route"] == Route.SQL_NOT_READY
        assert "SQL" in data["warning"]
        # generate_answer should NOT be called for SQL intent
        mock_generate.assert_not_called()

    @patch("main.generate_answer")
    def test_clarify_returns_clarification(self, mock_generate):
        """Questions needing clarification should return needs_clarification status"""
        response = client.post("/policy/answer?q=Is business class allowed?")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "needs_clarification"
        assert data["route"] == Route.CLARIFY
        assert data["clarify_question"] is not None
        assert "university" in data["clarify_question"].lower()
        # generate_answer should NOT be called for clarification
        mock_generate.assert_not_called()

    @patch("main.generate_answer")
    def test_filtered_org_calls_generate_answer(self, mock_generate):
        """Questions with org filter should call generate_answer with correct params"""
        mock_generate.return_value = {
            "answer": "Stanford allows business class for international flights over 8 hours.",
            "sources": [
                {"doc_name": "stanford_travel.pdf", "org": "Stanford", "page": 5, "text_snippet": "...", "score": 0.95}
            ],
            "query": "For Stanford, is business class allowed?",
            "filters": {"org": "STANFORD"},
            "warning": None
        }

        response = client.post("/policy/answer?q=For Stanford, is business class allowed?")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["route"] == Route.RAG_FILTERED
        assert data["filters"]["org"] == "Stanford"
        assert data["answer"] == "Stanford allows business class for international flights over 8 hours."
        assert len(data["sources"]) == 1

        # Verify generate_answer was called with correct params
        mock_generate.assert_called_once()
        call_kwargs = mock_generate.call_args.kwargs
        assert call_kwargs["query"] == "For Stanford, is business class allowed?"
        assert call_kwargs["filters"]["org"] == "STANFORD"
        assert call_kwargs["group_by_org"] is False  # RAG_FILTERED should not group

    @patch("main.generate_answer")
    def test_multi_org_comparison_groups_by_org(self, mock_generate):
        """Multi-org comparisons should set group_by_org=True"""
        mock_generate.return_value = {
            "answer": "ASU: $75/day. Yale: $85/day.",
            "sources": [
                {"doc_name": "asu_travel.pdf", "org": "ASU", "page": 3, "text_snippet": "...", "score": 0.92},
                {"doc_name": "yale_travel.pdf", "org": "Yale", "page": 4, "text_snippet": "...", "score": 0.90}
            ],
            "query": "Compare ASU vs Yale meal per diem",
            "filters": {},
            "warning": None
        }

        response = client.post("/policy/answer?q=Compare ASU vs Yale meal per diem")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["route"] == Route.RAG_ALL
        assert data["filters"]["org"] is None  # No org filter for comparisons

        # Verify group_by_org was set to True
        mock_generate.assert_called_once()
        call_kwargs = mock_generate.call_args.kwargs
        assert call_kwargs["group_by_org"] is True  # RAG_ALL should group

    @patch("main.generate_answer")
    def test_no_results_returns_no_results_status(self, mock_generate):
        """When no sources are found, should return no_results status"""
        mock_generate.return_value = {
            "answer": "",
            "sources": [],
            "query": "What is the policy for XYZ?",
            "filters": {},
            "warning": "No relevant policy content found"
        }

        response = client.post("/policy/answer?q=What is the policy for XYZ?")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "no_results"
        assert data["warning"] is not None
        assert "No relevant policy chunks found" in data["warning"]

    @patch("main.generate_answer")
    def test_explicit_params_override_inference(self, mock_generate):
        """Explicit query params should override router inference"""
        mock_generate.return_value = {
            "answer": "Princeton procurement policy...",
            "sources": [{"doc_name": "princeton_procurement.pdf", "org": "Princeton", "page": 2, "text_snippet": "...", "score": 0.88}],
            "query": "Compare ASU vs Stanford",
            "filters": {"org": "PRINCETON", "policy_type": "procurement"},
            "warning": None
        }

        # Even though query mentions comparison, explicit org should win
        response = client.post(
            "/policy/answer?q=Compare ASU vs Stanford&org=Princeton&policy_type=procurement"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["route"] == Route.RAG_FILTERED  # Should use filtered, not RAG_ALL
        assert data["filters"]["org"] == "Princeton"
        assert data["filters"]["policy_type"] == "procurement"

        # Verify filters were passed correctly
        call_kwargs = mock_generate.call_args.kwargs
        assert call_kwargs["filters"]["org"] == "PRINCETON"
        assert call_kwargs["filters"]["policy_type"] == "procurement"

    @patch("main.generate_answer")
    def test_candidate_k_and_final_k_params(self, mock_generate):
        """Should pass candidate_k and final_k params to generate_answer"""
        mock_generate.return_value = {
            "answer": "Policy answer...",
            "sources": [{"doc_name": "test.pdf", "org": "Yale", "page": 1, "text_snippet": "...", "score": 0.9}],
            "query": "Test query",
            "filters": {"org": "YALE"},
            "warning": None
        }

        response = client.post(
            "/policy/answer?q=What is Yale's policy?&candidate_k=50&final_k=10"
        )

        assert response.status_code == 200

        # Verify params were passed through
        call_kwargs = mock_generate.call_args.kwargs
        assert call_kwargs["candidate_k"] == 50
        assert call_kwargs["final_k"] == 10
