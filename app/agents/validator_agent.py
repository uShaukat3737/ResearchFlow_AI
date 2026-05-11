import os
import logging
from typing import Optional
from openai import AuthenticationError, RateLimitError
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from app.schemas.state import ResearchAssistantState
from app.prompts.validator_prompt import VALIDATOR_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

class ValidationAnalysis(BaseModel):
    is_sufficient: bool = Field(description="True if the retrieved research sufficiently answers the user prompt.")
    feedback: Optional[str] = Field(description="Detailed search feedback/instructions on what specific data is missing and needs to be fetched next.")
    reasoning: str = Field(description="Rationale for sufficiency check.")

def run_validator_agent(state: ResearchAssistantState) -> dict:
    """
    Validator Agent node. Checks gathered data sufficiency and suggests improvements.
    """
    messages = state.get("messages", [])
    latest_query = messages[-1].content if messages else "general market trends"
    research_data = state.get("research_data") or []
    attempts = state.get("attempts", 0)
    
    api_key = os.getenv("OPENAI_API_KEY", "")
    
    # Format current research data as a clean string for analysis
    research_str = "\n\n".join([
        f"Title: {r.get('title', 'No Title')}\nContent: {r.get('content', '')}"
        for r in research_data
    ])
    
    # Try LLM structured output
    if api_key and "your_" not in api_key and api_key != "placeholder":
        try:
            llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=api_key)
            structured_llm = llm.with_structured_output(ValidationAnalysis)
            
            system_msg = SystemMessage(content=VALIDATOR_SYSTEM_PROMPT.format(
                query=latest_query,
                research_data=research_str
            ))
            
            human_msg = HumanMessage(content="Analyze the research data and provide your validation assessment.")
            result = structured_llm.invoke([system_msg, human_msg])

            validation_res = "sufficient" if result.is_sufficient else "insufficient"
            feedback = None
            if not result.is_sufficient:
                feedback = result.feedback or "Research is incomplete. Search for more specific and recent information."
            return {
                "validation_result": validation_res,
                "validator_feedback": feedback,
            }
        except (AuthenticationError, RateLimitError):
            logger.error("Validator Agent: unrecoverable OpenAI error", exc_info=True)
            raise
        except Exception as e:
            logger.warning(f"Validator Agent LLM call failed, using mock loop fallback: {e}")
            
    # Mock fallback logic
    # To demonstrate looping capability beautifully, we mock "insufficient" on attempt 1,
    # and "sufficient" on attempt 2 or later.
    if attempts <= 1:
        feedback = "The initial search is good but lacks recent market challenges and specific competitor moves. Please search for competitor reactions and product challenges."
        logger.info(f"Validator Agent: Flagging research as insufficient (Attempt {attempts}). Triggering retry loop.")
        return {
            "validation_result": "insufficient",
            "validator_feedback": feedback
        }
    else:
        logger.info("Validator Agent: Research is sufficient. Proceeding to synthesis.")
        return {
            "validation_result": "sufficient",
            "validator_feedback": None
        }
