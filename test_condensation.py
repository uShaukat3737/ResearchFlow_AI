import dotenv
dotenv.load_dotenv()
from app.utils.llm_router import get_llm
from langchain_core.messages import HumanMessage, AIMessage

def mock_resolve_query_context(messages: list) -> str:
    from langchain_core.messages import HumanMessage, AIMessage
    
    transcript = []
    for m in messages:
        if isinstance(m, HumanMessage):
            transcript.append(f"User: {m.content}")
        elif isinstance(m, AIMessage):
            content = m.content
            if len(content) > 500:
                content = content[:400] + "... [truncated report] ..."
            transcript.append(f"Assistant: {content}")
            
    if not transcript:
        return "General Business Research"
        
    user_inputs = [m.content for m in messages if isinstance(m, HumanMessage)]
    if len(user_inputs) == 1:
        return user_inputs[0]
        
    prompt = f"""You are a query optimizer for a multi-agent business research system.
Analyze the conversation transcript below, identify the user's LATEST research intent/question, and rephrase it into a single, self-contained, and highly descriptive research topic.

For example:
- If history is:
  User: who is their cto?
  Assistant: Which company?
  User: Spotify
  Rephrased: Spotify CTO and technology leadership
  
- If history is:
  User: what is their stock price?
  Assistant: Which company?
  User: Apple
  Assistant: [Apple stock price report]
  User: i need the name of the company's CEO
  Rephrased: Apple Inc. current CEO name

Conversation Transcript:
---
{"\n".join(transcript)}
---

Output ONLY the final, self-contained rephrased query with no quotes, preamble, or explanation.
"""
    llm = get_llm(temperature=0.0, is_synthesis=False)
    if llm is not None:
        try:
            response = llm.invoke([HumanMessage(content=prompt)])
            condensed = response.content.strip().strip('"').strip("'")
            if condensed:
                return condensed
        except Exception as e:
            print("Error in LLM invocation:", e)
            
    return f"for company/subject '{user_inputs[-1]}': {user_inputs[0]}"


# Test Case 1: Clarification Flow
messages1 = [
    HumanMessage(content="who is their cto?"),
    AIMessage(content="Could you specify which company you are interested in?"),
    HumanMessage(content="spotify")
]
print("Test Case 1 (Clarification):")
print("Resolved:", mock_resolve_query_context(messages1))
print()

# Test Case 2: Follow-up Flow
messages2 = [
    HumanMessage(content="what is their stock price?"),
    AIMessage(content="Apple has a stock price of $293..."),
    HumanMessage(content="i need the name of the company's CEO")
]
print("Test Case 2 (Follow-up):")
print("Resolved:", mock_resolve_query_context(messages2))
print()

# Test Case 3: Random/Resets
messages3 = [
    HumanMessage(content="what is Apple's stock price?"),
    AIMessage(content="Apple has a stock price of $293..."),
    HumanMessage(content="clear")
]
print("Test Case 3 (Conversational Command):")
print("Resolved:", mock_resolve_query_context(messages3))
print()
