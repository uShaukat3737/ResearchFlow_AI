from typing import Optional
from langchain_core.messages import AIMessage, BaseMessage


def extract_final_report(messages: list[BaseMessage]) -> Optional[str]:
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            return msg.content
    return None


def get_confidence_label(score: int) -> tuple[str, str]:
    if score >= 6:
        return "High Confidence", "✅"
    elif score >= 4:
        return "Medium Confidence", "⚠️"
    return "Low Confidence", "❌"


def build_initial_inputs(query: str, is_clarification: bool) -> dict:
    from langchain_core.messages import HumanMessage

    inputs: dict = {"messages": [HumanMessage(content=query)]}
    if not is_clarification:
        inputs.update(
            {
                "attempts": 0,
                "research_data": [],
                "confidence_score": 0,
                "validation_result": None,
                "validator_feedback": None,
                "degraded_mode": None,
            }
        )
    return inputs
