import os
import logging
from typing import Optional, Tuple
from google.genai.errors import ClientError

logger = logging.getLogger(__name__)

# Registered providers
PROVIDER_OPENAI = "openai"
PROVIDER_ANTHROPIC = "anthropic"
PROVIDER_GOOGLE = "google"
PROVIDER_OLLAMA = "ollama"
PROVIDER_GROQ = "groq"

def get_active_provider() -> Tuple[Optional[str], Optional[str]]:
    """
    Detects the active LLM provider based on environment variables and active keys.
    Returns:
        (provider_name, api_key_value)
    """
    # 1. Respect explicit provider overrides
    override = os.getenv("LLM_PROVIDER", "").strip().lower()
    
    # 2. Check for OpenAI credentials
    openai_key = os.getenv("OPENAI_API_KEY", "")
    has_openai = openai_key and "your_" not in openai_key and openai_key != "placeholder"
    
    # 3. Check for Anthropic credentials
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    has_anthropic = anthropic_key and "your_" not in anthropic_key and anthropic_key != "placeholder"
    
    # 4. Check for Google credentials
    google_key = os.getenv("GEMINI_API_KEY", "")
    has_google = google_key and "your_" not in google_key and google_key != "placeholder"
    
    # 5. Check for Groq credentials
    groq_key = os.getenv("GROQ_API_KEY", "")
    has_groq = groq_key and "your_" not in groq_key and groq_key != "placeholder"
    
    # Resolve override if specified
    if override == PROVIDER_OLLAMA:
        return PROVIDER_OLLAMA, "local"
    if override == PROVIDER_OPENAI and has_openai:
        return PROVIDER_OPENAI, openai_key
    elif override == PROVIDER_ANTHROPIC and has_anthropic:
        return PROVIDER_ANTHROPIC, anthropic_key
    elif override == PROVIDER_GOOGLE and has_google:
        return PROVIDER_GOOGLE, google_key
    elif override == PROVIDER_GROQ and has_groq:
        return PROVIDER_GROQ, groq_key
        
    # Auto-detection priorities
    if has_openai:
        return PROVIDER_OPENAI, openai_key
    elif has_anthropic:
        return PROVIDER_ANTHROPIC, anthropic_key
    elif has_google:
        return PROVIDER_GOOGLE, google_key
    elif has_groq:
        return PROVIDER_GROQ, groq_key
        
    return None, None

def get_llm(temperature: float = 0.0, is_synthesis: bool = False):
    """
    Dynamically resolves, configures, and instantiates the proper model.
    Falls back gracefully to None (mock mode) if no active keys are found.
    """
    provider, api_key = get_active_provider()
    
    if not provider:
        logger.info("LLM Router: No active API credentials found. Falling back to high-fidelity mock data.")
        return None
        
    if provider == PROVIDER_OLLAMA:
        try:
            from langchain_ollama import ChatOllama
            model_name = os.getenv("OLLAMA_MODEL", "llama3.1").strip()
            logger.info(f"LLM Router: Instantiating local ChatOllama model '{model_name}'")
            return ChatOllama(
                model=model_name,
                temperature=temperature,
            )
        except ImportError:
            logger.error("LLM Router: langchain-ollama package is not installed. Please run 'pip install langchain-ollama' to run local Ollama models.")
            return None
            
    elif provider == PROVIDER_OPENAI:
        from langchain_openai import ChatOpenAI
        model_name = "gpt-4o" if is_synthesis else "gpt-4o-mini"
        logger.info(f"LLM Router: Instantiating OpenAI ChatOpenAI model '{model_name}'")
        return ChatOpenAI(
            model=model_name,
            temperature=temperature,
            api_key=api_key
        )
        
    elif provider == PROVIDER_ANTHROPIC:
        from langchain_anthropic import ChatAnthropic
        model_name = "claude-3-5-sonnet-latest" if is_synthesis else "claude-3-5-haiku-latest"
        logger.info(f"LLM Router: Instantiating Anthropic ChatAnthropic model '{model_name}'")
        return ChatAnthropic(
            model=model_name,
            temperature=temperature,
            api_key=api_key
        )
        
    elif provider == PROVIDER_GOOGLE:
        from langchain_google_genai import ChatGoogleGenerativeAI
        model_name = "gemini-2.0-flash"
        logger.info(f"LLM Router: Instantiating Google ChatGoogleGenerativeAI model '{model_name}'")
        return ChatGoogleGenerativeAI(
            model=model_name,
            temperature=temperature,
            google_api_key=api_key
        )
        
    elif provider == PROVIDER_GROQ:
        from langchain_openai import ChatOpenAI
        model_name = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip()


        logger.info(f"LLM Router: Instantiating Groq model '{model_name}' via ChatOpenAI")
        llm = ChatOpenAI(
            model=model_name,
            temperature=temperature,
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1"
        )
        
        # Override with_structured_output to default to function_calling for Groq compatibility
        # (since Groq does not support the default openai json_schema format)
        original_with_structured = llm.with_structured_output
        def custom_with_structured_output(schema, **kwargs):
            if "method" not in kwargs:
                kwargs["method"] = "function_calling"
            return original_with_structured(schema, **kwargs)
            
        object.__setattr__(llm, "with_structured_output", custom_with_structured_output)
        return llm


        
    return None

def classify_llm_error(exc: Exception) -> Optional[str]:
    """
    Inspects exceptions thrown by LLM calls and classifies them.
    Returns:
        "LLM quota limits" or "LLM authorization failed" for unrecoverable errors.
        None for transient/unexpected exceptions (which trigger standard fallback mock generation).
    """
    exc_str = str(exc).lower()
    exc_name = exc.__class__.__name__
    
    # 1. Handle ClientError from google.genai
    if isinstance(exc, ClientError):
        code = getattr(exc, "code", 0)
        if code in (401, 403):
            return "LLM authorization failed"
        elif code == 429:
            return "LLM quota limits"
            
    # 2. Handle generic exception substrings and type checks
    # Quota/Billing limits
    if "quota" in exc_str or "limit" in exc_str or "billing" in exc_str or "429" in exc_str or exc_name == "RateLimitError":
        return "LLM quota limits"
        
    # Authentication/Authorization
    if "api key" in exc_str or "auth" in exc_str or "unauthorized" in exc_str or "401" in exc_str or "403" in exc_str or exc_name == "AuthenticationError":
        return "LLM authorization failed"
        
    return None

def resolve_query_context(messages: list) -> str:
    """
    Resolves the combined user query intent from a list of multi-turn messages.
    Uses the active LLM to condense and rephrase the entire conversation history
    into a single, self-contained, and highly descriptive research query.
    """
    from langchain_core.messages import HumanMessage, AIMessage
    
    user_inputs = [m.content for m in messages if isinstance(m, HumanMessage)]
    if not user_inputs:
        return "General Business Research"
        
    # If there is only one user input, return it directly to save an API call
    if len(user_inputs) == 1:
        return user_inputs[0]
        
    # Build a clean conversation transcript for the LLM
    transcript = []
    for m in messages:
        if isinstance(m, HumanMessage):
            transcript.append(f"User: {m.content}")
        elif isinstance(m, AIMessage):
            # Truncate long reports to save tokens and avoid LLM distraction
            content = m.content
            if len(content) > 500:
                content = content[:400] + "... [truncated report] ..."
            transcript.append(f"Assistant: {content}")
            
    prompt = f"""You are a query optimizer for a multi-agent business research system.
Your job is to analyze the history of a multi-turn conversation and output a single, self-contained, and highly descriptive research topic or question that represents the user's LATEST intent.

Rules:
1. Identify the primary company, subject, or topic being discussed in the conversation.
2. Resolve any pronouns (like "their", "it", "he", "she", "this company") based on the conversation history.
3. If the user's latest message is a clarification (e.g., specifying a company name), merge it with the original question.
4. If the user's latest message is a follow-up question (e.g., "who is their ceo?" after talking about Apple's stock price), resolve it to a standalone question about that specific company (e.g., "Apple Inc. current CEO name").
5. Do not include any quotes, preamble, or explanation. Output ONLY the self-contained rephrased query.

Examples:
- Transcript:
  User: who is their cto?
  Assistant: Could you specify which company?
  User: spotify
  Output: Spotify current CTO and technology leadership
  
- Transcript:
  User: what is their stock price right now?
  Assistant: Apple Inc. (AAPL) stock is $293.32...
  User: who is their ceo
  Output: Apple Inc. current CEO name

- Transcript:
  User: whats their stock price right now?
  Assistant: [Apple stock price report]
  User: i am asking about the ceo of apple company
  Output: Apple Inc. current CEO name

Conversation Transcript:
---
{"\n".join(transcript)}
---

Rephrased query:"""

    # Call active LLM to perform query condensation
    llm = get_llm(temperature=0.0, is_synthesis=False)
    if llm is not None:
        try:
            response = llm.invoke([HumanMessage(content=prompt)])
            condensed = response.content.strip().strip('"').strip("'")
            if condensed:
                logger.info(f"LLM Query Context Resolver: Resolved multi-turn history to '{condensed}'")
                return condensed
        except Exception as e:
            logger.warning(f"LLM query condensation failed, falling back to rule: {e}")
            
    # Heuristics-based fallback if LLM is unavailable
    orig_query = user_inputs[0]
    clarification = user_inputs[-1]
    return f"for company/subject '{clarification}': {orig_query}"


