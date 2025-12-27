"""
Tests for router_v1.py - intelligent question routing logic
"""
import pytest
from app.policy.router_v1 import route_question
from app.schemas.router import Route


class TestSQLIntent:
    """Test SQL intent detection"""

    def test_sql_not_ready_expense_status(self):
        """Questions about personal expense status should route to SQL"""
        d = route_question("What is my expense status for report 123?")
        assert d.route == Route.SQL_NOT_READY

    def test_sql_not_ready_my_expenses(self):
        """Questions about 'my expenses' should route to SQL"""
        d = route_question("Show me my expenses from last month")
        assert d.route == Route.SQL_NOT_READY

    def test_sql_not_ready_reimbursement_status(self):
        """Questions about reimbursement status should route to SQL"""
        d = route_question("What is the status of my reimbursement?")
        assert d.route == Route.SQL_NOT_READY

    def test_sql_not_ready_total_spend(self):
        """Questions about total spend should route to SQL"""
        d = route_question("How much did I spend on travel last quarter?")
        assert d.route == Route.SQL_NOT_READY


class TestFilteredRouting:
    """Test RAG_FILTERED routing when org is specified"""

    def test_filtered_org_explicit(self):
        """Explicit org parameter should route to RAG_FILTERED"""
        d = route_question("Is business class allowed?", org="Stanford")
        assert d.route == Route.RAG_FILTERED
        assert d.filters.org == "Stanford"

    def test_filtered_org_in_question(self):
        """Org mentioned in question should route to RAG_FILTERED"""
        d = route_question("For Stanford, is business class allowed?")
        assert d.route == Route.RAG_FILTERED
        assert d.filters.org == "Stanford"

    def test_filtered_org_asu(self):
        """ASU mentioned in question should be extracted"""
        d = route_question("What is ASU's meal per diem policy?")
        assert d.route == Route.RAG_FILTERED
        assert d.filters.org == "ASU"

    def test_filtered_org_alias(self):
        """Org aliases should be normalized to canonical names"""
        d = route_question("What is Arizona State's travel policy?")
        assert d.route == Route.RAG_FILTERED
        assert d.filters.org == "ASU"

    def test_filtered_with_policy_type(self):
        """Should infer policy type when present"""
        d = route_question("What is Yale's procurement policy for vendors?")
        assert d.route == Route.RAG_FILTERED
        assert d.filters.org == "Yale"
        assert d.filters.policy_type == "procurement"


class TestMultiOrgComparison:
    """Test RAG_ALL routing for multi-org comparisons"""

    def test_multi_org_compare(self):
        """'Compare' keyword with multiple orgs should route to RAG_ALL"""
        d = route_question("Compare ASU vs Yale meal per diem")
        assert d.route == Route.RAG_ALL
        # No org filter when comparing multiple orgs
        assert d.filters.org is None

    def test_multi_org_difference(self):
        """'Difference' keyword with multiple orgs should route to RAG_ALL"""
        d = route_question("What's the difference between Stanford and Princeton travel policies?")
        assert d.route == Route.RAG_ALL
        assert d.filters.org is None

    def test_multi_org_vs(self):
        """'vs' keyword with multiple orgs should route to RAG_ALL"""
        d = route_question("Columbia vs NYU lodging limits")
        assert d.route == Route.RAG_ALL
        assert d.filters.org is None


class TestClarifyRouting:
    """Test CLARIFY routing when org is needed but not specified"""

    def test_clarify_single_policy_question(self):
        """Single policy question without org should ask for clarification"""
        d = route_question("Is business class allowed?")
        assert d.route == Route.CLARIFY
        assert d.clarify_question is not None
        assert "university" in d.clarify_question.lower()

    def test_clarify_reimbursable(self):
        """'Reimbursable' questions should clarify org"""
        d = route_question("Is rental car insurance reimbursable?")
        assert d.route == Route.CLARIFY
        assert d.clarify_question is not None

    def test_clarify_allowed(self):
        """'Allowed' questions should clarify org"""
        d = route_question("Is alcohol allowed on business meals?")
        assert d.route == Route.CLARIFY
        assert d.clarify_question is not None


class TestRAGAllRouting:
    """Test RAG_ALL routing for broad questions"""

    def test_rag_all_general_question(self):
        """General questions without specific org should route to RAG_ALL"""
        d = route_question("What are common meal per diem rates?")
        # Should be RAG_ALL (not CLARIFY) because it's not expecting a single answer
        assert d.route == Route.RAG_ALL
        assert d.filters.org is None

    def test_rag_all_best_practices(self):
        """Best practices questions should route to RAG_ALL"""
        d = route_question("What are best practices for travel expense documentation?")
        assert d.route == Route.RAG_ALL


class TestPolicyTypeInference:
    """Test policy type inference from keywords"""

    def test_policy_type_travel(self):
        """Should infer travel policy type"""
        d = route_question("For Michigan, what are the flight booking policies?")
        assert d.filters.policy_type == "travel"

    def test_policy_type_procurement(self):
        """Should infer procurement policy type"""
        d = route_question("What is Rutgers' p-card policy?")
        assert d.filters.policy_type == "procurement"

    def test_policy_type_explicit_param(self):
        """Explicit policy_type param should override inference"""
        d = route_question("What is the flight policy?", policy_type="general")
        assert d.filters.policy_type == "general"


class TestEdgeCases:
    """Test edge cases and corner scenarios"""

    def test_empty_question(self):
        """Empty question should still return a decision"""
        d = route_question("")
        # Should route somewhere (likely RAG_ALL or CLARIFY)
        assert d.route in {Route.RAG_ALL, Route.CLARIFY}

    def test_explicit_params_override_inference(self):
        """Explicit parameters should always win over inference"""
        d = route_question(
            "Compare ASU vs Stanford",
            org="Yale",
            policy_type="procurement"
        )
        assert d.route == Route.RAG_FILTERED
        assert d.filters.org == "Yale"
        assert d.filters.policy_type == "procurement"

    def test_doc_name_filter(self):
        """doc_name parameter should be preserved"""
        d = route_question(
            "What is the travel policy?",
            org="Princeton",
            doc_name="travel_policy.pdf"
        )
        assert d.route == Route.RAG_FILTERED
        assert d.filters.doc_name == "travel_policy.pdf"
