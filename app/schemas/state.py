from typing import Annotated, Dict, Any, List, Literal, Optional
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class ResearchAssistantState(TypedDict):
    """
    Central state schema for the LangGraph Research Assistant.
    """
    # Cumulatively appends new messages using LangGraph's add_messages reducer
    messages: Annotated[List[BaseMessage], add_messages]

    # Routing signals — must use Literal to catch typos at type-check time (ADR-000)
    clarity_status: Literal["clear", "needs_clarification"]
    confidence_score: int           # 0–10 scale; enforcement in research_agent
    validation_result: Literal["sufficient", "insufficient"]
    
    # Storage for fetched research data from web search
    research_data: List[Dict[str, Any]]
    
    # Count of research queries conducted
    attempts: int
    
    # Specific instructions from the validator agent on gaps to fill
    validator_feedback: Optional[str]

    # Circuit-breaker state indicator when live LLM API returns quota or billing blocks
    degraded_mode: Optional[str]

