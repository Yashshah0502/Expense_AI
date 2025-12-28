"""
Integration tests for /copilot/answer API endpoint.
Tests various question types and routing scenarios.
"""

import os
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from pathlib import Path
import psycopg


TEST_DB_URL = os.getenv('TEST_DATABASE_URL')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')


@pytest.fixture(scope='module')
def db_connection():
    """Provide database connection for setup."""
    if not TEST_DB_URL:
        pytest.skip("TEST_DATABASE_URL not set")

    conn = psycopg.connect(TEST_DB_URL)
    yield conn
    conn.close()


@pytest.fixture(scope='module')
def setup_test_data(db_connection):
    """Set up test tables and insert synthetic data."""
    # Ensure tables exist
    migration_sql = Path(__file__).parent.parent / 'migrations' / '003_create_expense_tables.sql'
    with open(migration_sql) as f:
        db_connection.execute(f.read())
    db_connection.commit()

    # Clean test data
    db_connection.execute("DELETE FROM expenses WHERE org = 'CopilotTest'")
    db_connection.execute("DELETE FROM expense_events WHERE org = 'CopilotTest'")
    db_connection.commit()

    # Insert synthetic expenses
    with db_connection.cursor() as cur:
        cur.execute("""
            INSERT INTO expenses (
                org, source_file, source_row, employee_id, expense_date,
                amount, currency, category, merchant, report_id, row_hash
            ) VALUES
                ('CopilotTest', 'test.xlsx', 1, 'EMP001', '2024-01-15', 100.00, 'USD', 'Travel', 'Delta', 'RPT001', 'hash1'),
                ('CopilotTest', 'test.xlsx', 2, 'EMP001', '2024-01-16', 50.00, 'USD', 'Meals', 'Chipotle', 'RPT001', 'hash2'),
                ('CopilotTest', 'test.xlsx', 3, 'EMP002', '2024-01-17', 200.00, 'USD', 'Travel', 'United', 'RPT002', 'hash3'),
                ('CopilotTest', 'test.xlsx', 4, 'EMP002', '2024-01-18', 75.00, 'USD', 'Meals', 'Subway', 'RPT002', 'hash4')
        """)

        # Insert synthetic events
        cur.execute("""
            INSERT INTO expense_events (
                org, source_file, case_id, event_index, activity, event_time, event_hash
            ) VALUES
                ('CopilotTest', 'test.xes', 'CASE001', 1, 'Submit', '2024-01-15 10:00:00', 'evhash1'),
                ('CopilotTest', 'test.xes', 'CASE001', 2, 'Review', '2024-01-16 14:00:00', 'evhash2'),
                ('CopilotTest', 'test.xes', 'CASE001', 3, 'Approve', '2024-01-17 09:00:00', 'evhash3')
        """)

    db_connection.commit()
    yield
    # Cleanup
    db_connection.execute("DELETE FROM expenses WHERE org = 'CopilotTest'")
    db_connection.execute("DELETE FROM expense_events WHERE org = 'CopilotTest'")
    db_connection.commit()


@pytest.fixture(scope='module')
def client(setup_test_data):
    """Provide FastAPI test client."""
    if not OPENAI_API_KEY:
        pytest.skip("OPENAI_API_KEY not set - cannot test copilot agent")

    from main import app
    return TestClient(app)


@pytest.mark.integration
@pytest.mark.skipif(not OPENAI_API_KEY, reason="OPENAI_API_KEY required for agent tests")
class TestCopilotAnswerEndpoint:
    """Test /copilot/answer endpoint with real LLM calls."""

    def test_policy_only_question(self, client):
        """Test a question that should only use policy tool."""
        response = client.post(
            "/copilot/answer",
            params={
                "q": "What is the mileage reimbursement rate for Stanford?",
                "org": "Stanford"
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert "answer" in data
        assert data["routing"]["used_policy"] is True
        # May or may not use SQL depending on agent's interpretation
        assert len(data["policy_sources"]) > 0

    def test_sql_only_question_with_employee_id(self, client):
        """Test a question requiring SQL with employee_id provided."""
        response = client.post(
            "/copilot/answer",
            params={
                "q": "How much did I spend on travel?",
                "org": "CopilotTest",
                "employee_id": "EMP001"
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert "answer" in data
        assert data["routing"]["used_sql"] is True
        # Should find $100 in travel expenses for EMP001
        assert "100" in data["answer"] or "$100" in data["answer"]

    def test_combined_question(self, client):
        """Test a question that might use both policy and SQL tools."""
        response = client.post(
            "/copilot/answer",
            params={
                "q": "Did my travel expense of $100 comply with the policy?",
                "org": "CopilotTest",
                "employee_id": "EMP001"
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert "answer" in data
        # Agent should use both tools (policy for rules, SQL for expense data)
        assert data["routing"]["used_policy"] is True or data["routing"]["used_sql"] is True

    def test_missing_employee_id_clarification(self, client):
        """Test that agent asks for clarification when employee_id is missing."""
        response = client.post(
            "/copilot/answer",
            params={
                "q": "How much did I spend this month?",
                "org": "CopilotTest"
                # Missing employee_id
            }
        )

        assert response.status_code == 200
        data = response.json()

        # Agent should ask for employee_id or provide general answer
        assert "answer" in data
        # May set follow_up if clarification needed
        if data.get("follow_up"):
            assert "employee" in data["follow_up"].lower() or "who" in data["follow_up"].lower()

    def test_case_timeline_question(self, client):
        """Test a question about case timeline."""
        response = client.post(
            "/copilot/answer",
            params={
                "q": "What happened in case CASE001?",
                "org": "CopilotTest",
                "case_id": "CASE001"
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert "answer" in data
        assert data["routing"]["used_sql"] is True
        # Should mention Submit, Review, Approve activities
        answer_lower = data["answer"].lower()
        assert "submit" in answer_lower or "review" in answer_lower or "approve" in answer_lower

    def test_response_structure(self, client):
        """Test that response has correct structure."""
        response = client.post(
            "/copilot/answer",
            params={
                "q": "What is the travel policy?",
                "org": "Stanford"
            }
        )

        assert response.status_code == 200
        data = response.json()

        # Verify all required fields
        assert "answer" in data
        assert "routing" in data
        assert "policy_sources" in data
        assert "sql_results" in data
        assert "warnings" in data

        # Verify routing structure
        assert "used_policy" in data["routing"]
        assert "used_sql" in data["routing"]
        assert "tools_called" in data["routing"]
        assert isinstance(data["routing"]["tools_called"], list)

        # Verify sql_results structure
        assert "totals" in data["sql_results"]
        assert "samples" in data["sql_results"]
        assert "timeline" in data["sql_results"]
        assert "duplicates" in data["sql_results"]

    def test_debug_mode(self, client):
        """Test that debug mode works."""
        response = client.post(
            "/copilot/answer",
            params={
                "q": "What are my expenses?",
                "org": "CopilotTest",
                "employee_id": "EMP001",
                "debug": True
            }
        )

        assert response.status_code == 200
        data = response.json()

        # Debug mode should include additional info
        assert "answer" in data
        assert "routing" in data

    def test_max_tool_calls_limit(self, client):
        """Test that agent respects MAX_TOOL_CALLS limit."""
        # This test is more for verification that the endpoint doesn't hang
        # Agent should stop after 6 tool calls
        response = client.post(
            "/copilot/answer",
            params={
                "q": "Tell me everything about expenses and policies",
                "org": "CopilotTest"
            }
        )

        assert response.status_code == 200
        data = response.json()

        # Should complete (not timeout)
        assert "answer" in data
        # Tool calls should not exceed MAX_TOOL_CALLS
        assert len(data["routing"]["tools_called"]) <= 6


@pytest.mark.unit
class TestCopilotMockedAgent:
    """Test copilot endpoint with mocked agent (no real LLM calls)."""

    @patch('graphs.copilot_agent.run_agent')
    def test_endpoint_calls_agent(self, mock_run_agent):
        """Test that endpoint calls run_agent correctly."""
        # Mock agent response
        mock_run_agent.return_value = {
            "answer": "Test answer",
            "tools_called": ["policy_tool"],
            "policy_sources": [],
            "sql_results": {
                "totals": None,
                "samples": None,
                "timeline": None,
                "duplicates": None
            },
            "warnings": []
        }

        from main import app
        client = TestClient(app)

        response = client.post(
            "/copilot/answer",
            params={
                "q": "Test question",
                "org": "TestOrg"
            }
        )

        assert response.status_code == 200
        # Verify run_agent was called
        mock_run_agent.assert_called_once()

        # Verify context passed to agent
        call_args = mock_run_agent.call_args
        assert call_args[0][0] == "Test question"  # question
        assert call_args[0][1]["org"] == "TestOrg"  # context

    @patch('graphs.copilot_agent.run_agent')
    def test_policy_type_filter(self, mock_run_agent):
        """Test that policy_type is passed to agent context."""
        mock_run_agent.return_value = {
            "answer": "Test",
            "tools_called": [],
            "policy_sources": [],
            "sql_results": {"totals": None, "samples": None, "timeline": None, "duplicates": None},
            "warnings": []
        }

        from main import app
        client = TestClient(app)

        response = client.post(
            "/copilot/answer",
            params={
                "q": "Test",
                "org": "TestOrg",
                "policy_type": "travel"
            }
        )

        assert response.status_code == 200

        # Verify policy_type in context
        call_args = mock_run_agent.call_args
        assert call_args[0][1]["policy_type"] == "travel"

    @patch('graphs.copilot_agent.run_agent')
    def test_follow_up_detection(self, mock_run_agent):
        """Test that follow_up questions are detected."""
        # Mock agent asking for clarification
        mock_run_agent.return_value = {
            "answer": "Which employee are you asking about?",
            "tools_called": [],
            "policy_sources": [],
            "sql_results": {"totals": None, "samples": None, "timeline": None, "duplicates": None},
            "warnings": []
        }

        from main import app
        client = TestClient(app)

        response = client.post(
            "/copilot/answer",
            params={
                "q": "How much did I spend?",
                "org": "TestOrg"
            }
        )

        assert response.status_code == 200
        data = response.json()

        # Should detect clarification question
        # (Implementation may vary - this is a placeholder test)
        assert "answer" in data

    def test_request_validation(self):
        """Test that invalid requests are rejected."""
        from main import app
        client = TestClient(app)

        # Missing required 'q' parameter
        response = client.post("/copilot/answer")

        assert response.status_code == 422  # Validation error

    def test_empty_question(self):
        """Test that empty question is rejected."""
        from main import app
        client = TestClient(app)

        response = client.post(
            "/copilot/answer",
            params={"q": ""}  # Empty question
        )

        assert response.status_code == 422  # Validation error


@pytest.mark.integration
@pytest.mark.skipif(not OPENAI_API_KEY, reason="OPENAI_API_KEY required")
class TestCopilotEdgeCases:
    """Test edge cases and error handling."""

    def test_nonexistent_org(self, client):
        """Test query for nonexistent organization."""
        response = client.post(
            "/copilot/answer",
            params={
                "q": "What is the policy?",
                "org": "NonexistentOrg"
            }
        )

        assert response.status_code == 200
        data = response.json()

        # Agent should handle gracefully
        assert "answer" in data
        # May include warning about no data found
        if data["warnings"]:
            assert any("no" in w.lower() or "not found" in w.lower() for w in data["warnings"])

    def test_very_long_question(self, client):
        """Test handling of very long question."""
        long_question = "What is the policy? " * 100  # Very long repetitive question

        response = client.post(
            "/copilot/answer",
            params={
                "q": long_question,
                "org": "CopilotTest"
            }
        )

        # Should either succeed or fail gracefully
        assert response.status_code in [200, 400, 413]

    def test_special_characters_in_question(self, client):
        """Test handling of special characters."""
        response = client.post(
            "/copilot/answer",
            params={
                "q": "What's the policy for <script>alert('test')</script>?",
                "org": "CopilotTest"
            }
        )

        assert response.status_code == 200
        data = response.json()

        # Should sanitize and handle safely
        assert "answer" in data
