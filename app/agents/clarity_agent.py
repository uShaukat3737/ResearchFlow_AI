import os
import logging
from typing import Optional
from openai import AuthenticationError, RateLimitError
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, AIMessage
from app.schemas.state import ResearchAssistantState
from app.prompts.clarity_prompt import CLARITY_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

class ClarityAnalysis(BaseModel):
    is_clear: bool = Field(description="True if the subject and target company/topic are clearly identified.")
    clarification_message: Optional[str] = Field(description="A friendly prompt asking the user for specific missing details if is_clear is False.")
    reasoning: str = Field(description="Short rationale behind the clarity check.")

def run_clarity_agent(state: ResearchAssistantState) -> dict:
    """
    Clarity Agent node. Decides if the current request is clear or needs clarification.
    """
    messages = state.get("messages", [])
    if not messages:
        return {
            "clarity_status": "needs_clarification",
            "messages": [AIMessage(content="Hello! Please tell me what company or business topic you would like to research today.")]
        }
        
    api_key = os.getenv("OPENAI_API_KEY", "")
    
    # Check if we should use real LLM or mock fallback
    if api_key and "your_" not in api_key and api_key != "placeholder":
        try:
            llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=api_key)
            structured_llm = llm.with_structured_output(ClarityAnalysis)
            
            # Format inputs
            system_msg = SystemMessage(content=CLARITY_SYSTEM_PROMPT)
            all_messages = [system_msg] + messages
            
            result = structured_llm.invoke(all_messages)
            
            if result.is_clear:
                return {
                    "clarity_status": "clear"
                }
            else:
                # Append clarification message as AIMessage to state
                clarif_msg = result.clarification_message or "Could you please clarify which company or topic you are asking about?"
                return {
                    "clarity_status": "needs_clarification",
                    "messages": [AIMessage(content=clarif_msg)]
                }
        except (AuthenticationError, RateLimitError):
            logger.error("Clarity Agent: unrecoverable OpenAI error", exc_info=True)
            raise
        except Exception as e:
            logger.warning(f"Clarity Agent LLM call failed, using mock fallback: {e}")
            
    # Fallback/Mock analysis logic — see ADR-002
    has_subject = _has_named_subject(messages)

    if has_subject:
        return {"clarity_status": "clear"}

    clarif_msg = "Could you please specify which company or business topic you are interested in analyzing?"
    return {
        "clarity_status": "needs_clarification",
        "messages": [AIMessage(content=clarif_msg)],
    }


# Common sentence-opening words that are capitalised but do NOT indicate a named subject.
_SENTENCE_OPENERS = {
    "what", "how", "when", "where", "why", "who", "which",
    "tell", "show", "explain", "provide", "analyze", "give",
    "find", "can", "could", "is", "are", "do", "does", "did",
    "has", "have", "get", "please", "i", "the", "a", "an",
}


def _has_named_subject(messages: list) -> bool:
    """Return True if any message token looks like a proper-noun named subject.

    FALLBACK: used when OPENAI_API_KEY is absent or placeholder.
    Heuristic: any token that starts uppercase and is not a common sentence-opener
    is treated as a named subject (e.g. 'Salesforce', 'Microsoft', 'Tesla').
    """
    for msg in messages:
        content = str(msg.content).strip()
        if not content:
            continue
        for word in content.split():
            cleaned = word.strip("'s,;:.!?\"()")
            if cleaned and cleaned[0].isupper() and cleaned.lower() not in _SENTENCE_OPENERS:
                return True
    return False
