from langgraph.graph import END
from app.schemas.state import ResearchAssistantState

def route_clarity(state: ResearchAssistantState) -> str:
    """
    Decides whether to pause (end) for clarification or proceed to research.
    """
    if state.get("clarity_status") == "needs_clarification":
        # Returns "__end__" to yield control back to the client/user
        return "needs_clarification"
    return "clear"

MAX_RESEARCH_ATTEMPTS = 3

def route_research(state: ResearchAssistantState) -> str:
    """
    Decides whether research is high quality (confidence >= 6) and can skip
    validation, or if we must run it through the Validator Agent.
    When the circuit-breaker has fired (attempts >= MAX_RESEARCH_ATTEMPTS), bypass
    the validator entirely and proceed directly to synthesis.
    """
    score = state.get("confidence_score", 0)
    attempts = state.get("attempts", 0)
    if attempts >= MAX_RESEARCH_ATTEMPTS or score >= 6:
        return "high_confidence"
    return "low_confidence"

def route_validator(state: ResearchAssistantState) -> str:
    """
    Evaluates validator results and search attempts.
    Loops back to research if insufficient and attempts < 3,
    otherwise proceeds to synthesis.
    """
    result = state.get("validation_result", "insufficient")
    attempts = state.get("attempts", 0)
    
    if result == "insufficient" and attempts < MAX_RESEARCH_ATTEMPTS:
        return "loop_back"
    return "synthesize"
