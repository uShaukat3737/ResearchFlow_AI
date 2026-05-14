from langchain_core.messages import AIMessage, HumanMessage

from app.utils.ui_helpers import (
    build_initial_inputs,
    extract_final_report,
    get_confidence_label,
)


def test_extract_final_report_returns_last_ai_message():
    messages = [HumanMessage(content="query"), AIMessage(content="Report here.")]
    assert extract_final_report(messages) == "Report here."


def test_extract_final_report_returns_last_when_multiple_ai_messages():
    messages = [
        HumanMessage(content="q"),
        AIMessage(content="First."),
        HumanMessage(content="clarify"),
        AIMessage(content="Final report."),
    ]
    assert extract_final_report(messages) == "Final report."


def test_extract_final_report_returns_none_when_no_ai_message():
    messages = [HumanMessage(content="query")]
    assert extract_final_report(messages) is None


def test_extract_final_report_returns_none_on_empty_list():
    assert extract_final_report([]) is None


def test_get_confidence_label_high():
    label, emoji = get_confidence_label(8)
    assert "High" in label
    assert emoji


def test_get_confidence_label_medium():
    label, emoji = get_confidence_label(5)
    assert "Medium" in label
    assert emoji


def test_get_confidence_label_low():
    label, emoji = get_confidence_label(2)
    assert "Low" in label
    assert emoji


def test_get_confidence_label_boundary_six_is_high():
    label, _ = get_confidence_label(6)
    assert "High" in label


def test_get_confidence_label_boundary_four_is_medium():
    label, _ = get_confidence_label(4)
    assert "Medium" in label


def test_get_confidence_label_boundary_three_is_low():
    label, _ = get_confidence_label(3)
    assert "Low" in label


def test_build_initial_inputs_new_query_resets_state():
    inputs = build_initial_inputs("What is OpenAI?", is_clarification=False)
    assert inputs["messages"][0].content == "What is OpenAI?"
    assert inputs["attempts"] == 0
    assert inputs["research_data"] == []
    assert inputs["confidence_score"] == 0
    assert inputs["validation_result"] is None
    assert inputs["validator_feedback"] is None
    assert inputs["degraded_mode"] is None


def test_build_initial_inputs_clarification_preserves_state():
    inputs = build_initial_inputs("I meant Apple Corp", is_clarification=True)
    assert inputs["messages"][0].content == "I meant Apple Corp"
    assert "attempts" not in inputs
    assert "research_data" not in inputs
    assert "confidence_score" not in inputs
