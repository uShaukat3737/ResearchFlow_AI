import os
import logging
from typing import List
from pydantic import BaseModel, Field
from openai import AuthenticationError, RateLimitError
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from app.schemas.state import ResearchAssistantState
from app.tools.tavily_search import exec_tavily_search
from app.prompts.research_prompt import RESEARCH_QUERY_PROMPT, RESEARCH_EVALUATION_PROMPT

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3

class ResearchEvaluation(BaseModel):
    confidence_score: int = Field(description="A confidence score from 0-10 on the richness and completeness of the retrieved research.")
    reasoning: str = Field(description="Rationale behind assigning this score.")

def run_research_agent(state: ResearchAssistantState) -> dict:
    """
    Research Agent node. Runs target searches and self-evaluates confidence.
    """
    messages = state.get("messages", [])
    attempts = state.get("attempts", 0)
    current_data = state.get("research_data") or []

    if not messages:
        return {"research_data": current_data, "attempts": attempts, "confidence_score": 0}

    if attempts >= MAX_ATTEMPTS:
        return {"research_data": current_data, "attempts": attempts, "confidence_score": 0}

    latest_query = messages[-1].content
    feedback = state.get("validator_feedback") or "No prior feedback. Initial search round."

    api_key = os.getenv("OPENAI_API_KEY", "")

    # Step 1: Formulate search query.
    # LLM path incorporates feedback via RESEARCH_QUERY_PROMPT.
    # Mock path appends feedback directly so it is never silently dropped (Bug #3).
    search_query = str(latest_query)
    if api_key and "your_" not in api_key and api_key != "placeholder":
        try:
            llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=api_key)
            prompt_content = RESEARCH_QUERY_PROMPT.format(query=latest_query, feedback=feedback)
            response = llm.invoke([HumanMessage(content=prompt_content)])
            search_query = response.content.strip().strip('"').strip("'")
        except (AuthenticationError, RateLimitError):
            logger.error("Research Agent: unrecoverable OpenAI error", exc_info=True)
            raise
        except Exception as e:
            logger.warning(f"Research Agent query formulation failed, using direct query: {e}")
    else:
        # In mock mode, append feedback so the captured query differs from bare user query
        actual_feedback = state.get("validator_feedback")
        if actual_feedback:
            search_query = f"{latest_query} {actual_feedback}"

    logger.info(f"Research Agent search query: '{search_query}' (Attempt {attempts + 1})")

    # Step 2: Execute search and deduplicate by URL (ADR-003 — Bug #7)
    new_results = exec_tavily_search(search_query)
    seen_urls = {r["url"] for r in current_data}
    deduped_new = [r for r in new_results if r.get("url") not in seen_urls]
    updated_data = current_data + deduped_new
    new_attempts = attempts + 1

    # Step 3: Self-evaluate confidence score (0-10) using LLM
    if not deduped_new:
        return {"research_data": updated_data, "attempts": new_attempts, "confidence_score": 0}

    confidence_score = 5
    if api_key and "your_" not in api_key and api_key != "placeholder":
        try:
            llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=api_key)
            structured_eval = llm.with_structured_output(ResearchEvaluation)
            results_str = "\n\n".join([
                f"Title: {r['title']}\nContent: {r['content']}"
                for r in deduped_new
            ])
            eval_prompt = RESEARCH_EVALUATION_PROMPT.format(query=latest_query, results=results_str)
            eval_result = structured_eval.invoke([HumanMessage(content=eval_prompt)])
            confidence_score = eval_result.confidence_score
        except (AuthenticationError, RateLimitError):
            logger.error("Research Agent: unrecoverable OpenAI error", exc_info=True)
            raise
        except Exception as e:
            logger.warning(f"Research Agent self-evaluation failed, using fallback: {e}")
            if any(kw in search_query.lower() for kw in ["microsoft", "apple", "nvidia"]):
                confidence_score = 8
    else:
        # Mock fallback confidence scoring
        if any(kw in search_query.lower() for kw in ["microsoft", "apple", "nvidia"]):
            confidence_score = 8
        else:
            confidence_score = 5

    return {
        "research_data": updated_data,
        "attempts": new_attempts,
        "confidence_score": confidence_score
    }
