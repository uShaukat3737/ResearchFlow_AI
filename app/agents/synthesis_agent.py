import os
import logging
import re
from openai import AuthenticationError, RateLimitError
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, AIMessage, HumanMessage
from app.schemas.state import ResearchAssistantState
from app.prompts.synthesis_prompt import SYNTHESIS_SYSTEM_PROMPT, SYNTHESIS_HUMAN_PROMPT

logger = logging.getLogger(__name__)

def run_synthesis_agent(state: ResearchAssistantState) -> dict:
    """
    Synthesis Agent node. Creates a business research report from retrieved data.
    FALLBACK: when no API key is present, builds a data-driven report from research_data
    without injecting any hardcoded facts or boilerplate.
    """
    messages = state.get("messages", [])
    latest_query = messages[-1].content if messages else "General Business Research"
    research_data = state.get("research_data") or []

    api_key = os.getenv("OPENAI_API_KEY", "")

    research_str = ""
    for idx, r in enumerate(research_data, 1):
        research_str += f"[{idx}] Source: {r.get('title', 'Untitled')}\n"
        research_str += f"    URL: {r.get('url', '')}\n"
        research_str += f"    Content: {r.get('content', '')}\n\n"

    if api_key and "your_" not in api_key and api_key != "placeholder":
        try:
            llm = ChatOpenAI(model="gpt-4o", temperature=0.3, api_key=api_key)
            # Escape user-supplied {} to prevent .format() injection
            safe_query = latest_query.replace("{", "{{").replace("}", "}}")
            system_msg = SystemMessage(content=SYNTHESIS_SYSTEM_PROMPT.format(query=safe_query))
            # Research data goes in HumanMessage — user-level authority, not system-level (ADR-006)
            # Escape braces so Tavily content with {} tokens doesn't corrupt .format()
            safe_research = research_str.replace("{", "{{").replace("}", "}}")
            human_msg = HumanMessage(content=SYNTHESIS_HUMAN_PROMPT.format(research_data=safe_research))
            response = llm.invoke([system_msg, human_msg])
            return {"messages": [AIMessage(content=response.content)]}
        except (AuthenticationError, RateLimitError):
            logger.error("Synthesis Agent: unrecoverable OpenAI error", exc_info=True)
            raise
        except Exception as e:
            logger.warning(f"Synthesis Agent LLM call failed, using mock fallback: {e}")

    # Data-driven mock fallback — ADR-004
    subject = str(latest_query).strip()
    subject_title = " ".join(w.capitalize() for w in subject.split())

    findings = ""
    for idx, r in enumerate(research_data, 1):
        findings += f"- **{r.get('title', 'Untitled')}**\n"
        findings += f"  *Summary*: {r.get('content', '')}\n"
        findings += f"  *Source*: [{r.get('title', 'Link')}]({r.get('url', '')})\n\n"

    quant_lines = _extract_quantitative_lines(research_data)
    if quant_lines:
        table_section = "### Quantitative Data from Sources\n\n"
        table_section += "| # | Data Point | Source |\n|---|---|---|\n"
        for item in quant_lines:
            table_section += f"| {item['idx']} | {item['text']} | {item['source']} |\n"
    else:
        table_section = "### Financial & Quantitative Data\n\nNo quantitative data retrieved from search results."

    if not research_data:
        findings = "_No research data was retrieved. Try a more specific query._\n"

    report_content = f"""# Business Research Report: {subject_title}

## 1. Executive Summary
This report presents findings on **{subject_title}** based on web research retrieved by the ResearchFlow AI pipeline.

## 2. Key Findings

{findings}

## 3. Data Points

{table_section}

## 4. Sources
{_format_sources(research_data)}

---
*Report synthesized by **ResearchFlow AI Multi-Agent Network**.*"""

    return {"messages": [AIMessage(content=report_content.strip())]}


def _extract_quantitative_lines(research_data: list) -> list:
    """Return rows of quantitative facts (lines containing $, %, billion, million)."""
    pattern = re.compile(r'(\$[\d.,]+[BMK]?|\d+[\.,]?\d*\s*%|[\d.,]+\s*(?:billion|million|trillion))', re.IGNORECASE)
    rows = []
    for r in research_data:
        content = r.get("content", "")
        source = r.get("title", "Unknown")
        for sentence in re.split(r'[.!?]', content):
            if pattern.search(sentence):
                text = sentence.strip()
                if text:
                    safe_text = text[:120].replace("|", "\\|")
                    safe_source = source.replace("|", "\\|")
                    rows.append({"idx": len(rows) + 1, "text": safe_text, "source": safe_source})
                if len(rows) >= 10:
                    return rows
    return rows


def _format_sources(research_data: list) -> str:
    if not research_data:
        return "_No sources retrieved._"
    lines = []
    for idx, r in enumerate(research_data, 1):
        lines.append(f"{idx}. [{r.get('title', 'Untitled')}]({r.get('url', '')})")
    return "\n".join(lines)
