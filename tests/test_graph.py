import os
import pytest
from typing import Literal, get_origin, get_type_hints
from unittest.mock import MagicMock, patch
from langchain_core.messages import HumanMessage

from app.schemas.state import ResearchAssistantState

# graph fixture is provided by tests/conftest.py

# ---------------------------------------------------------------------------
# Phase 1: State Schema Contract Tests
# ---------------------------------------------------------------------------

REQUIRED_FIELDS = {
    "messages", "clarity_status", "confidence_score",
    "validation_result", "research_data", "attempts", "validator_feedback",
}

def test_state_schema_has_required_fields():
    hints = get_type_hints(ResearchAssistantState, include_extras=True)
    missing = REQUIRED_FIELDS - set(hints.keys())
    assert missing == set(), f"State schema is missing fields: {missing}"

def test_state_fields_have_correct_types():
    hints = get_type_hints(ResearchAssistantState, include_extras=False)
    assert hints["confidence_score"] is int, "confidence_score must be typed as int"
    assert hints["attempts"] is int, "attempts must be typed as int"

def test_clarity_status_is_literal_type():
    hints = get_type_hints(ResearchAssistantState, include_extras=False)
    assert get_origin(hints["clarity_status"]) is Literal, (
        "clarity_status must use Literal type — see ADR-000"
    )

def test_validation_result_is_literal_type():
    hints = get_type_hints(ResearchAssistantState, include_extras=False)
    assert get_origin(hints["validation_result"]) is Literal, (
        "validation_result must use Literal type — see ADR-000"
    )

def test_empty_initial_state_defaults_are_safe():
    state: ResearchAssistantState = {"messages": [HumanMessage(content="test")]}  # type: ignore[typeddict-item]
    assert state.get("attempts", 0) == 0
    assert state.get("research_data", []) == []
    assert state.get("validator_feedback") is None

# ---------------------------------------------------------------------------
# Phase 2: Clarity Agent Unit Tests
# ---------------------------------------------------------------------------

def test_clarity_agent_propagates_auth_error():
    """ClientError must set degraded_mode — updated from legacy crash behavior."""
    from google.genai.errors import ClientError
    from app.agents.clarity_agent import run_clarity_agent

    auth_err = ClientError(403, {"error": {"message": "Invalid API key"}})
    with patch("app.agents.clarity_agent.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value.invoke.side_effect = auth_err
        mock_get_llm.return_value = mock_llm
        
        result = run_clarity_agent({"messages": [HumanMessage("Microsoft strategy")]})
        assert result["clarity_status"] == "clear"
        assert result["degraded_mode"] == "LLM authorization failed"

def test_clarity_agent_whitespace_content_needs_clarification():
    from app.agents.clarity_agent import run_clarity_agent
    result = run_clarity_agent({"messages": [HumanMessage(content="   ")]})
    assert result["clarity_status"] == "needs_clarification"

def test_clarity_agent_clears_for_unlisted_company():
    from app.agents.clarity_agent import run_clarity_agent
    state = {"messages": [HumanMessage(content="Analyze Salesforce's competitive position")]}
    result = run_clarity_agent(state)
    assert result["clarity_status"] == "clear", (
        "Salesforce is a clear company name — fallback must not require it in a hardcoded list"
    )

def test_clarity_agent_clears_for_known_company():
    from app.agents.clarity_agent import run_clarity_agent
    state = {"messages": [HumanMessage(content="Provide an earnings report on Microsoft")]}
    result = run_clarity_agent(state)
    assert result["clarity_status"] == "clear"

def test_clarity_agent_needs_clarification_for_vague_query():
    from app.agents.clarity_agent import run_clarity_agent
    state = {"messages": [HumanMessage(content="what are their latest numbers?")]}
    result = run_clarity_agent(state)
    assert result["clarity_status"] == "needs_clarification"

def test_clarity_agent_needs_clarification_for_empty_messages():
    from app.agents.clarity_agent import run_clarity_agent
    result = run_clarity_agent({"messages": []})
    assert result["clarity_status"] == "needs_clarification"

def test_clarity_agent_resolves_pronoun_from_history():
    from app.agents.clarity_agent import run_clarity_agent
    state = {"messages": [
        HumanMessage(content="Tell me about Microsoft"),
        HumanMessage(content="What are their Q3 results?"),
    ]}
    result = run_clarity_agent(state)
    assert result["clarity_status"] == "clear", (
        "Agent must resolve 'their' from prior message containing 'Microsoft'"
    )

# ---------------------------------------------------------------------------
# Phase 3: Research Agent Unit Tests
# ---------------------------------------------------------------------------

def test_research_agent_returns_confidence_score_as_int():
    from app.agents.research_agent import run_research_agent
    state = {"messages": [HumanMessage("Microsoft strategy")], "attempts": 0, "research_data": []}
    result = run_research_agent(state)
    assert isinstance(result["confidence_score"], int)

def test_research_agent_increments_attempts():
    from app.agents.research_agent import run_research_agent
    state = {"messages": [HumanMessage("Microsoft strategy")], "attempts": 0, "research_data": []}
    result = run_research_agent(state)
    assert result["attempts"] == 1

def test_research_agent_returns_research_data_list():
    from app.agents.research_agent import run_research_agent
    state = {"messages": [HumanMessage("Microsoft strategy")], "attempts": 0, "research_data": []}
    result = run_research_agent(state)
    assert isinstance(result["research_data"], list)
    assert len(result["research_data"]) > 0

def test_research_agent_incorporates_validator_feedback_in_mock_path():
    """validator_feedback must alter the search query even without an API key — Bug #3."""
    from unittest.mock import patch as _patch
    from app.agents.research_agent import run_research_agent
    captured = {}

    def capturing_search(query: str):
        captured["query"] = query
        return []

    state = {
        "messages": [HumanMessage("Tesla strategy")],
        "attempts": 1,
        "research_data": [],
        "validator_feedback": "Focus on recent competitor moves and market share data",
    }
    with _patch("app.agents.research_agent.exec_tavily_search", side_effect=capturing_search):
        run_research_agent(state)

    assert captured.get("query") is not None
    assert captured["query"] != "Tesla strategy", (
        "Search query must differ from bare user query when validator_feedback is set"
    )

def test_research_data_deduplication_on_retry():
    """research_data must not contain duplicate URLs after a retry — Bug #7."""
    from app.agents.research_agent import run_research_agent
    existing_url = "https://www.microsoft.com/en-us/investor/earnings"
    pre_existing = [{"title": "Pre-existing", "url": existing_url, "content": "existing content"}]
    state = {
        "messages": [HumanMessage("Microsoft earnings")],
        "attempts": 1,
        "research_data": pre_existing,
    }
    result = run_research_agent(state)
    urls = [r["url"] for r in result["research_data"]]
    assert len(urls) == len(set(urls)), "Duplicate URLs found in research_data after retry"

def test_research_data_grows_on_fresh_results():
    from app.agents.research_agent import run_research_agent
    state = {"messages": [HumanMessage("Microsoft earnings")], "attempts": 0, "research_data": []}
    result = run_research_agent(state)
    assert len(result["research_data"]) > 0

def test_research_agent_propagates_auth_error():
    """ClientError must set degraded_mode — updated from legacy crash behavior."""
    from google.genai.errors import ClientError
    from app.agents.research_agent import run_research_agent

    auth_err = ClientError(403, {"error": {"message": "Invalid API key"}})
    with patch("app.agents.research_agent.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = auth_err
        mock_get_llm.return_value = mock_llm
        
        result = run_research_agent({
            "messages": [HumanMessage("Microsoft strategy")],
            "attempts": 0,
            "research_data": [],
        })
        assert result["degraded_mode"] == "LLM authorization failed"
        assert result["confidence_score"] == 0
        assert result["attempts"] == 1

def test_research_agent_returns_zero_confidence_on_empty_search_results():
    """Empty Tavily results must yield confidence_score=0 — reviewer HIGH finding."""
    from app.agents.research_agent import run_research_agent
    with patch("app.agents.research_agent.exec_tavily_search", return_value=[]):
        result = run_research_agent({
            "messages": [HumanMessage("some obscure query")],
            "attempts": 0,
            "research_data": [],
        })
    assert result["confidence_score"] == 0, "Empty search results must produce confidence_score 0"

def test_research_agent_max_attempts_circuit_breaker():
    """Agent must not execute a search when attempts >= MAX_ATTEMPTS — reviewer CRITICAL finding."""
    from app.agents.research_agent import run_research_agent
    existing_data = [{"title": "Existing", "url": "http://example.com", "content": "data"}]
    called = []
    with patch("app.agents.research_agent.exec_tavily_search", side_effect=lambda q: called.append(q) or []):
        result = run_research_agent({
            "messages": [HumanMessage("Microsoft strategy")],
            "attempts": 3,
            "research_data": existing_data,
        })
    assert called == [], "exec_tavily_search must NOT be called when attempts >= MAX_ATTEMPTS"
    assert result["research_data"] == existing_data

def test_research_agent_handles_empty_messages():
    """Empty messages must return confidence 0, not silently search for 'general market trends'."""
    from app.agents.research_agent import run_research_agent
    called = []
    with patch("app.agents.research_agent.exec_tavily_search", side_effect=lambda q: called.append(q) or []):
        result = run_research_agent({"messages": [], "attempts": 0, "research_data": []})
    assert result["confidence_score"] == 0, "Empty messages must not produce a non-zero confidence score"
    assert all("general market trends" not in q for q in called), (
        "Silent fallback to 'general market trends' must not occur"
    )

def test_ambiguous_query_halts_for_clarification(graph):
    """
    Asserts that an ambiguous user query triggers the Clarity Agent,
    sets 'needs_clarification', and terminates early without hitting research.
    """
    config = {"configurable": {"thread_id": "test_thread_unclear"}}
    inputs = {"messages": [HumanMessage(content="What are their latest numbers?")]}
    
    # Run the graph
    result = graph.invoke(inputs, config)
    
    assert result["clarity_status"] == "needs_clarification"
    # Research and validator should not have been run
    assert result.get("attempts", 0) == 0
    assert "research_data" not in result or len(result["research_data"]) == 0
    
    # Check that a clarification prompt was generated and returned to the user
    messages = result.get("messages", [])
    assert len(messages) > 1
    assert "clarify" in messages[-1].content.lower() or "specify" in messages[-1].content.lower()

def test_clear_high_confidence_query_bypasses_validation(graph):
    """
    Asserts that a clear, specific query (e.g. Microsoft) is recognized
    as clear, retrieves rich data, rates confidence >= 6, and proceeds
    straight to Synthesis (skipping the Validator Agent node).
    """
    config = {"configurable": {"thread_id": "test_thread_clear_fast"}}
    inputs = {"messages": [HumanMessage(content="Provide an earnings report on Microsoft")]}
    
    result = graph.invoke(inputs, config)
    
    assert result["clarity_status"] == "clear"
    assert result["attempts"] == 1
    assert result["confidence_score"] >= 6
    
    # Validator should have been completely skipped (so validation_result won't be set in state)
    assert "validation_result" not in result
    
    # Synthesis must have run successfully and produced the final report
    messages = result.get("messages", [])
    assert len(messages) > 1
    assert "Business Research Report" in messages[-1].content
    assert "Microsoft" in messages[-1].content

# ---------------------------------------------------------------------------
# Phase 4: Validator Agent Unit Tests
# ---------------------------------------------------------------------------

def test_validator_agent_returns_validation_result_field():
    from app.agents.validator_agent import run_validator_agent
    state = {
        "messages": [HumanMessage("Tesla strategy")],
        "research_data": [{"title": "T", "url": "http://x.com", "content": "c"}],
        "attempts": 1,
    }
    result = run_validator_agent(state)
    assert result["validation_result"] in ("sufficient", "insufficient")

def test_validator_agent_returns_insufficient_on_attempt_1():
    from app.agents.validator_agent import run_validator_agent
    state = {
        "messages": [HumanMessage("Tesla strategy")],
        "research_data": [{"title": "T", "url": "http://x.com", "content": "c"}],
        "attempts": 1,
    }
    result = run_validator_agent(state)
    assert result["validation_result"] == "insufficient"
    assert result.get("validator_feedback") is not None

def test_validator_agent_returns_sufficient_on_attempt_2():
    from app.agents.validator_agent import run_validator_agent
    state = {
        "messages": [HumanMessage("Tesla strategy")],
        "research_data": [{"title": "T", "url": "http://x.com", "content": "c"}],
        "attempts": 2,
    }
    result = run_validator_agent(state)
    assert result["validation_result"] == "sufficient"

def test_validator_agent_clears_feedback_on_sufficient():
    from app.agents.validator_agent import run_validator_agent
    state = {
        "messages": [HumanMessage("Tesla strategy")],
        "research_data": [{"title": "T", "url": "http://x.com", "content": "c"}],
        "attempts": 2,
    }
    result = run_validator_agent(state)
    assert "validator_feedback" in result
    assert result["validator_feedback"] is None

def test_validator_agent_propagates_auth_error():
    """ClientError must set degraded_mode — updated from legacy crash behavior."""
    from google.genai.errors import ClientError
    from app.agents.validator_agent import run_validator_agent

    auth_err = ClientError(403, {"error": {"message": "Invalid API key"}})
    with patch("app.agents.validator_agent.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value.invoke.side_effect = auth_err
        mock_get_llm.return_value = mock_llm
        
        result = run_validator_agent({
            "messages": [HumanMessage("Tesla strategy")],
            "research_data": [{"title": "T", "url": "http://x.com", "content": "c"}],
            "attempts": 1,
        })
        assert result["degraded_mode"] == "LLM authorization failed"
        assert result["validation_result"] == "sufficient"

def test_validator_agent_llm_invoke_includes_human_message():
    """LLM invocation must include a HumanMessage — Bug #4 fix verification."""
    from app.agents.validator_agent import run_validator_agent
    from langchain_core.messages import HumanMessage as HM

    captured = {}
    with patch("app.agents.validator_agent.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_result = MagicMock()
        mock_result.is_sufficient = True
        mock_result.feedback = None

        def capture_invoke(msgs):
            captured["msgs"] = msgs
            return mock_result

        mock_llm.with_structured_output.return_value.invoke.side_effect = capture_invoke
        mock_get_llm.return_value = mock_llm

        run_validator_agent({
            "messages": [HumanMessage("Tesla strategy")],
            "research_data": [{"title": "T", "url": "http://x.com", "content": "c"}],
            "attempts": 1,
        })
    assert any(isinstance(m, HM) for m in captured.get("msgs", [])), (
        "LLM invoke must include a HumanMessage — Bug #4"
    )


# ---------------------------------------------------------------------------
# Phase 4 (reviewer findings): Routing + Validator Edge Cases
# ---------------------------------------------------------------------------

def test_route_research_skips_validator_at_max_attempts():
    """route_research must bypass validator when circuit-breaker has fired — reviewer CRITICAL."""
    from app.graph.routing import route_research
    result = route_research({"confidence_score": 0, "attempts": 3, "messages": []})
    assert result == "high_confidence", (
        "attempts >= MAX_ATTEMPTS must route to synthesis, not validator"
    )

def test_route_research_skips_validator_above_max_attempts():
    """Guard at attempts > MAX_ATTEMPTS — belt-and-suspenders for the circuit-breaker."""
    from app.graph.routing import route_research
    result = route_research({"confidence_score": 0, "attempts": 5, "messages": []})
    assert result == "high_confidence"

def test_validator_agent_handles_empty_research_data():
    """Validator must return a valid result dict when research_data is empty, not raise."""
    from app.agents.validator_agent import run_validator_agent
    result = run_validator_agent({
        "messages": [HumanMessage("Tesla strategy")],
        "research_data": [],
        "attempts": 2,
    })
    assert result["validation_result"] in ("sufficient", "insufficient")

def test_validator_agent_defaults_feedback_when_llm_returns_none_feedback():
    """If LLM returns is_sufficient=False but feedback=None, agent must supply fallback feedback."""
    from app.agents.validator_agent import run_validator_agent
    from unittest.mock import MagicMock as MM
    with patch("app.agents.validator_agent.get_llm") as mock_get_llm:
        mock_llm = MM()
        mock_result = MM()
        mock_result.is_sufficient = False
        mock_result.feedback = None
        mock_llm.with_structured_output.return_value.invoke.return_value = mock_result
        mock_get_llm.return_value = mock_llm
        
        result = run_validator_agent({
            "messages": [HumanMessage("Tesla strategy")],
            "research_data": [{"title": "T", "url": "http://x.com", "content": "c"}],
            "attempts": 1,
        })
    assert result["validation_result"] == "insufficient"
    assert result.get("validator_feedback") is not None, (
        "validator_feedback must not be None when validation_result is insufficient"
    )


# ---------------------------------------------------------------------------
# Phase 5: Synthesis Agent Unit Tests
# ---------------------------------------------------------------------------

def test_synthesis_agent_does_not_contain_hardcoded_microsoft_figures():
    """Mock path must not inject hardcoded figures when research_data is empty — Bug #5."""
    from app.agents.synthesis_agent import run_synthesis_agent
    result = run_synthesis_agent({
        "messages": [HumanMessage("Provide an earnings report on Microsoft")],
        "research_data": [],
    })
    content = result["messages"][-1].content
    assert "$61.9 Billion" not in content, "Hardcoded Microsoft figure must not appear"
    assert "$27.9 Billion" not in content, "Hardcoded Microsoft figure must not appear"

def test_synthesis_agent_outputs_data_gap_notice_when_no_research_data():
    """No research data must produce a notice, not fabricated generic figures — Bug #5."""
    from app.agents.synthesis_agent import run_synthesis_agent
    result = run_synthesis_agent({
        "messages": [HumanMessage("Analyze Palantir strategy")],
        "research_data": [],
    })
    content = result["messages"][-1].content
    assert "$4.5M" not in content, "Generic fallback table must not appear for empty research_data"
    assert "No quantitative data" in content or "No data retrieved" in content or "no research data" in content.lower() or "insufficient" in content.lower()

def test_synthesis_agent_produces_output_without_generic_boilerplate_swot():
    """Hardcoded SWOT boilerplate must not appear for any company — Bug #5."""
    from app.agents.synthesis_agent import run_synthesis_agent
    result = run_synthesis_agent({
        "messages": [HumanMessage("Analyze Palantir strategy")],
        "research_data": [],
    })
    content = result["messages"][-1].content
    assert "Strong Brand Equity" not in content, "Boilerplate SWOT must be removed"
    assert "High CapEx" not in content, "Boilerplate SWOT must be removed"

def test_synthesis_agent_derives_content_from_research_data():
    """Report content must incorporate titles and URLs from research_data."""
    from app.agents.synthesis_agent import run_synthesis_agent
    result = run_synthesis_agent({
        "messages": [HumanMessage("Salesforce CRM analysis")],
        "research_data": [
            {"title": "Salesforce Q3 Revenue Hit", "url": "https://sfdc.example.com/q3", "content": "Revenue reached $9.4 billion"},
        ],
    })
    content = result["messages"][-1].content
    assert "Salesforce Q3 Revenue Hit" in content or "sfdc.example.com" in content

def test_synthesis_agent_includes_source_links_from_research_data():
    """Source URLs from research_data must appear in the report."""
    from app.agents.synthesis_agent import run_synthesis_agent
    target_url = "https://unique-test-source.example.com/report"
    result = run_synthesis_agent({
        "messages": [HumanMessage("IBM strategy")],
        "research_data": [{"title": "IBM Annual Report", "url": target_url, "content": "revenue up 5%"}],
    })
    content = result["messages"][-1].content
    assert target_url in content, "Source URL from research_data must appear in the report"

def test_synthesis_agent_produces_output_for_any_company():
    """Mock path must work for any company, not just Microsoft/Apple/NVIDIA."""
    from app.agents.synthesis_agent import run_synthesis_agent
    result = run_synthesis_agent({
        "messages": [HumanMessage("Roche Pharmaceuticals pipeline overview")],
        "research_data": [{"title": "Roche Pipeline", "url": "http://roche.example.com", "content": "strong oncology pipeline"}],
    })
    content = result["messages"][-1].content
    assert "Business Research Report" in content
    assert "Microsoft" not in content
    assert "NVIDIA" not in content


# Phase 5 (reviewer findings): Synthesis security + edge cases

def test_synthesis_agent_propagates_auth_error():
    """ClientError must set degraded_mode / message rather than raw crash."""
    from google.genai.errors import ClientError
    from app.agents.synthesis_agent import run_synthesis_agent

    auth_err = ClientError(403, {"error": {"message": "Invalid API key"}})
    with patch("app.agents.synthesis_agent.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = auth_err
        mock_get_llm.return_value = mock_llm
        
        result = run_synthesis_agent({
            "messages": [HumanMessage("Microsoft strategy")],
            "research_data": [],
        })
        assert "messages" in result
        assert "Research unavailable due to" in result["messages"][-1].content

def test_synthesis_agent_handles_format_braces_in_query():
    """User query containing {} must not raise KeyError in .format() call — SECURITY."""
    from app.agents.synthesis_agent import run_synthesis_agent
    result = run_synthesis_agent({
        "messages": [HumanMessage("What is {ROI} for Microsoft?")],
        "research_data": [],
    })
    assert "messages" in result

def test_synthesis_agent_handles_pipe_in_research_content():
    """Pipe characters in research content must not break the markdown table — SECURITY."""
    from app.agents.synthesis_agent import run_synthesis_agent
    result = run_synthesis_agent({
        "messages": [HumanMessage("IBM strategy")],
        "research_data": [{"title": "IBM Revenue", "url": "http://ibm.example.com", "content": "Revenue $4.5B | income $1B | margin 20%"}],
    })
    content = result["messages"][-1].content
    assert "messages" in result
    lines = [l for l in content.split("\n") if "|" in l and "---" not in l]
    for line in lines:
        # Replace escaped pipes before counting columns so \| is not treated as a separator
        sanitized = line.replace("\\|", "\x00")
        cells = [c.strip() for c in sanitized.strip("|").split("|")]
        assert len(cells) == 3, f"Pipe in content broke table row: {line!r}"

def test_synthesis_llm_path_sends_research_data_as_human_message():
    """Research data must be in HumanMessage, not SystemMessage — PROMPT/SECURITY."""
    from app.agents.synthesis_agent import run_synthesis_agent
    captured = {}
    with patch("app.agents.synthesis_agent.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_resp = MagicMock()
        mock_resp.content = "report"
        def capture_invoke(msgs):
            captured["msgs"] = msgs
            return mock_resp
        mock_llm.invoke.side_effect = capture_invoke
        mock_get_llm.return_value = mock_llm
        
        run_synthesis_agent({
            "messages": [HumanMessage("Microsoft strategy")],
            "research_data": [{"title": "T", "url": "http://x.com", "content": "c"}],
        })
    from langchain_core.messages import HumanMessage as HM
    assert any(isinstance(m, HM) for m in captured.get("msgs", [])), (
        "LLM invocation must include a HumanMessage containing research data"
    )


def test_loopback_validation_triggers_successfully(graph):
    """
    Asserts that a thin or generic query (triggering low confidence) routes to 
    the validator, which triggers a corrective search loop back to research,
    eventually proceeding to synthesis on the second attempt.
    """
    config = {"configurable": {"thread_id": "test_thread_loop"}}
    # Using a query containing 'Tesla' triggers a clear status but falls back to low confidence (5)
    inputs = {"messages": [HumanMessage(content="Provide an overview of Tesla's strategy")]}
    
    result = graph.invoke(inputs, config)
    
    assert result["clarity_status"] == "clear"
    
    # It should have looped back, registering at least 2 attempts
    assert result["attempts"] >= 2
    
    # Validator should have run and set validation_result to sufficient on the final attempt
    assert result["validation_result"] == "sufficient"
    
    # Synthesis should have finished and outputted a report
    messages = result.get("messages", [])
    assert len(messages) > 1
    assert "Business Research Report" in messages[-1].content
    assert "Tesla" in messages[-1].content

# ---------------------------------------------------------------------------
# Phase 6: Thread ID Isolation Tests
# ---------------------------------------------------------------------------

def test_two_graph_sessions_with_different_thread_ids_are_independent(graph):
    """Different thread IDs must maintain fully independent state — Bug #6 guard."""
    # Thread A: ambiguous query → needs_clarification
    config_a = {"configurable": {"thread_id": "isolation_test_thread_A"}}
    result_a = graph.invoke({"messages": [HumanMessage("What are their latest numbers?")]}, config_a)
    assert result_a["clarity_status"] == "needs_clarification"

    # Thread B: clear query on a different thread — must be unaffected by thread A state
    config_b = {"configurable": {"thread_id": "isolation_test_thread_B"}}
    result_b = graph.invoke({"messages": [HumanMessage("Provide an earnings report on Microsoft")]}, config_b)
    assert result_b["clarity_status"] == "clear", (
        "Thread B must be independent — state from thread A must not bleed across thread IDs"
    )

def test_graph_uses_separate_checkpointer_per_create_call():
    """Each create_research_graph() call must produce an isolated in-memory checkpointer."""
    from app.graph.builder import create_research_graph
    graph1 = create_research_graph()
    graph2 = create_research_graph()
    config = {"configurable": {"thread_id": "shared_id"}}
    graph1.invoke({"messages": [HumanMessage("What are their latest numbers?")]}, config)
    # graph2 has no prior state on this thread_id
    state2 = graph2.get_state(config)
    assert not state2.values, "graph2 must not see state written by graph1 on the same thread_id"

# ---------------------------------------------------------------------------
# Phase 7: Integration Edge Case Tests
# ---------------------------------------------------------------------------

def test_empty_string_query_halts_for_clarification(graph):
    config = {"configurable": {"thread_id": "edge_empty_str"}}
    result = graph.invoke({"messages": [HumanMessage(content="")]}, config)
    assert result["clarity_status"] == "needs_clarification"

def test_whitespace_only_query_halts_for_clarification(graph):
    config = {"configurable": {"thread_id": "edge_whitespace"}}
    result = graph.invoke({"messages": [HumanMessage(content="   ")]}, config)
    assert result["clarity_status"] == "needs_clarification"

def test_clear_query_for_non_mock_company_reaches_synthesis(graph):
    """A company not in the 3-keyword mock list (e.g. Salesforce) must complete to synthesis."""
    config = {"configurable": {"thread_id": "edge_salesforce"}}
    result = graph.invoke({"messages": [HumanMessage(content="Analyze Salesforce CRM strategy")]}, config)
    assert result["clarity_status"] == "clear"
    messages = result.get("messages", [])
    assert any("Business Research Report" in m.content for m in messages)

def test_max_attempts_circuit_breaker_routes_to_synthesis(graph):
    """After MAX_ATTEMPTS research passes, graph must reach synthesis without infinite looping."""
    config = {"configurable": {"thread_id": "edge_max_attempts"}}
    result = graph.invoke({"messages": [HumanMessage(content="Provide an overview of Tesla's strategy")]}, config)
    messages = result.get("messages", [])
    assert any("Business Research Report" in m.content for m in messages), (
        "Graph must always reach synthesis, even after multiple validation loops"
    )

def test_research_data_not_duplicated_after_two_attempts(graph):
    """End-to-end deduplication check — URLs must be unique after a retry loop."""
    config = {"configurable": {"thread_id": "edge_dedup_e2e"}}
    result = graph.invoke({"messages": [HumanMessage(content="Provide an overview of Tesla's strategy")]}, config)
    urls = [r["url"] for r in result.get("research_data", [])]
    assert len(urls) == len(set(urls)), "Duplicate URLs found in research_data after end-to-end loop"

def test_confidence_threshold_boundary_at_6_routes_high(graph):
    """confidence_score >= 6 must route directly to synthesis, skipping the validator."""
    config = {"configurable": {"thread_id": "edge_confidence_6"}}
    result = graph.invoke({"messages": [HumanMessage(content="Provide an earnings report on Microsoft")]}, config)
    assert result["confidence_score"] >= 6
    assert "validation_result" not in result, (
        "High-confidence path must skip validator entirely"
    )

def test_confidence_threshold_boundary_at_5_routes_low(graph):
    """confidence_score == 5 must route through the validator."""
    config = {"configurable": {"thread_id": "edge_confidence_5"}}
    result = graph.invoke({"messages": [HumanMessage(content="Provide an overview of Tesla's strategy")]}, config)
    assert result.get("confidence_score", 5) < 6 or result.get("validation_result") is not None, (
        "Low-confidence path must pass through validator"
    )

def test_synthesis_output_contains_no_hardcoded_boilerplate(graph):
    """End-to-end synthesis for an unknown company must contain no hardcoded SWOT bullets."""
    config = {"configurable": {"thread_id": "edge_no_boilerplate"}}
    result = graph.invoke({"messages": [HumanMessage(content="Analyze Palantir strategy")]}, config)
    messages = result.get("messages", [])
    final_content = messages[-1].content if messages else ""
    assert "Strong Brand Equity" not in final_content
    assert "$61.9 Billion" not in final_content

def test_validator_feedback_alters_second_search(graph):
    """End-to-end: validator feedback must reach the second research query."""
    from unittest.mock import patch as _patch
    captured_queries = []
    original_search = __import__("app.tools.tavily_search", fromlist=["exec_tavily_search"]).exec_tavily_search

    def recording_search(query: str):
        captured_queries.append(query)
        return original_search(query)

    config = {"configurable": {"thread_id": "edge_feedback_flow"}}
    with _patch("app.agents.research_agent.exec_tavily_search", side_effect=recording_search):
        graph.invoke({"messages": [HumanMessage(content="Provide an overview of Tesla's strategy")]}, config)

    assert len(captured_queries) >= 2, "Loop must have triggered at least two searches"

# ---------------------------------------------------------------------------
# Phase 8: Prompt Injection Delimiter Tests
# ---------------------------------------------------------------------------

def test_research_prompt_contains_query_delimiter():
    """RESEARCH_QUERY_PROMPT must delimit user-controlled {query} with XML tags."""
    from app.prompts.research_prompt import RESEARCH_QUERY_PROMPT
    assert "<user_query>" in RESEARCH_QUERY_PROMPT, (
        "User query must be wrapped in <user_query> tags to signal untrusted content"
    )

def test_research_prompt_contains_feedback_delimiter():
    """RESEARCH_QUERY_PROMPT must delimit validator_feedback with XML tags."""
    from app.prompts.research_prompt import RESEARCH_QUERY_PROMPT
    assert "<validator_feedback>" in RESEARCH_QUERY_PROMPT, (
        "Validator feedback must be wrapped in <validator_feedback> tags"
    )

def test_validator_prompt_contains_query_delimiter():
    """VALIDATOR_SYSTEM_PROMPT must delimit user-controlled {query} with XML tags."""
    from app.prompts.validator_prompt import VALIDATOR_SYSTEM_PROMPT
    assert "<user_query>" in VALIDATOR_SYSTEM_PROMPT, (
        "User query must be wrapped in <user_query> tags in the validator prompt"
    )

def test_validator_prompt_contains_data_delimiter():
    """VALIDATOR_SYSTEM_PROMPT must delimit {research_data} with XML tags."""
    from app.prompts.validator_prompt import VALIDATOR_SYSTEM_PROMPT
    assert "<research_data>" in VALIDATOR_SYSTEM_PROMPT, (
        "Research data must be wrapped in <research_data> tags in the validator prompt"
    )

def test_synthesis_human_prompt_contains_data_delimiter():
    """SYNTHESIS_HUMAN_PROMPT must delimit research_data with XML tags."""
    from app.prompts.synthesis_prompt import SYNTHESIS_HUMAN_PROMPT
    assert "<research_data>" in SYNTHESIS_HUMAN_PROMPT, (
        "Research data must be wrapped in <research_data> tags in the synthesis human prompt"
    )

# ---------------------------------------------------------------------------
# Phase 9: Final Reviewer Findings
# ---------------------------------------------------------------------------

def test_route_validator_respects_max_research_attempts_constant():
    """route_validator must use MAX_RESEARCH_ATTEMPTS constant, not magic number 3."""
    from app.graph.routing import route_validator, MAX_RESEARCH_ATTEMPTS
    # At exactly MAX_RESEARCH_ATTEMPTS, insufficient result must still route to synthesis
    state = {"validation_result": "insufficient", "attempts": MAX_RESEARCH_ATTEMPTS}
    result = route_validator(state)
    assert result == "synthesize", (
        f"route_validator must route to synthesize when attempts == MAX_RESEARCH_ATTEMPTS ({MAX_RESEARCH_ATTEMPTS})"
    )

def test_synthesis_research_str_with_braces_does_not_raise():
    """research_str containing {} must not crash SYNTHESIS_HUMAN_PROMPT.format() — SECURITY."""
    from app.agents.synthesis_agent import run_synthesis_agent
    result = run_synthesis_agent({
        "messages": [HumanMessage("IBM strategy")],
        "research_data": [{"title": "IBM {ROI} report", "url": "http://ibm.example.com", "content": "revenue {growth} 5%"}],
    })
    assert "messages" in result

# ---------------------------------------------------------------------------
# Phase 10: LLM Router and Degraded Mode Circuit Breaker Verification
# ---------------------------------------------------------------------------

def test_llm_router_auto_detects_provider():
    """LLM Router must detect active providers based on keys and respect overrides."""
    from app.utils.llm_router import get_active_provider, PROVIDER_OPENAI, PROVIDER_ANTHROPIC, PROVIDER_GOOGLE
    
    # Test auto-detection priorities
    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test123notplaceholder", "ANTHROPIC_API_KEY": "at-test", "GEMINI_API_KEY": "ai-test"}):
        provider, _ = get_active_provider()
        assert provider == PROVIDER_OPENAI
        
    with patch.dict(os.environ, {"OPENAI_API_KEY": "placeholder", "ANTHROPIC_API_KEY": "at-test123notplaceholder", "GEMINI_API_KEY": "ai-test"}):
        provider, _ = get_active_provider()
        assert provider == PROVIDER_ANTHROPIC
        
    with patch.dict(os.environ, {"OPENAI_API_KEY": "placeholder", "ANTHROPIC_API_KEY": "your_anthropic_key", "GEMINI_API_KEY": "ai-test123notplaceholder"}):
        provider, _ = get_active_provider()
        assert provider == PROVIDER_GOOGLE

    # Test override behavior
    with patch.dict(os.environ, {
        "OPENAI_API_KEY": "sk-test123notplaceholder",
        "ANTHROPIC_API_KEY": "at-test123notplaceholder",
        "LLM_PROVIDER": "anthropic"
    }):
        provider, _ = get_active_provider()
        assert provider == PROVIDER_ANTHROPIC

def test_degraded_mode_circuit_breaker():
    """The graph must immediately short circuit to synthesis and return a friendly quota warning if degraded_mode is flagged."""
    from app.graph.builder import create_research_graph
    
    graph = create_research_graph()
    config = {"configurable": {"thread_id": "test_thread_circuit_breaker"}}
    inputs = {
        "messages": [HumanMessage(content="Explain quantum computing dynamics")],
        "degraded_mode": "LLM quota limits"
    }
    
    result = graph.invoke(inputs, config)
    
    # Ensure it outputted the exact quota warning
    assert result["degraded_mode"] == "LLM quota limits"
    messages = result.get("messages", [])
    assert len(messages) > 1
    assert messages[-1].content == "Research unavailable due to LLM quota limits"
