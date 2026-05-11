from langgraph.graph import StateGraph, START, END
from app.schemas.state import ResearchAssistantState
from app.memory.checkpoint import get_in_memory_checkpointer

# Import agents
from app.agents.clarity_agent import run_clarity_agent
from app.agents.research_agent import run_research_agent
from app.agents.validator_agent import run_validator_agent
from app.agents.synthesis_agent import run_synthesis_agent

# Import routers
from app.graph.routing import route_clarity, route_research, route_validator

def create_research_graph():
    """
    Assembles, connects, and compiles the multi-agent state graph workflow.
    """
    # 1. Initialize State Graph with our State schema
    workflow = StateGraph(ResearchAssistantState)
    
    # 2. Add computation nodes
    workflow.add_node("clarity_agent", run_clarity_agent)
    workflow.add_node("research_agent", run_research_agent)
    workflow.add_node("validator_agent", run_validator_agent)
    workflow.add_node("synthesis_agent", run_synthesis_agent)
    
    # 3. Add edges and entry transitions
    workflow.add_edge(START, "clarity_agent")
    
    # 4. Add conditional routing edges
    workflow.add_conditional_edges(
        "clarity_agent",
        route_clarity,
        {
            "needs_clarification": END,   # Stops to let user answer clarification
            "clear": "research_agent"
        }
    )
    
    workflow.add_conditional_edges(
        "research_agent",
        route_research,
        {
            "high_confidence": "synthesis_agent",  # Proceed straight to synthesis
            "low_confidence": "validator_agent"     # Requires Quality Control audit
        }
    )
    
    workflow.add_conditional_edges(
        "validator_agent",
        route_validator,
        {
            "loop_back": "research_agent",          # Search loop retry
            "synthesize": "synthesis_agent"         # Sufficient data or max attempts hit
        }
    )
    
    # 5. Direct exit edge from synthesis
    workflow.add_edge("synthesis_agent", END)
    
    # 6. Compile with checkpointer persistence for context retention
    checkpointer = get_in_memory_checkpointer()
    return workflow.compile(checkpointer=checkpointer)
