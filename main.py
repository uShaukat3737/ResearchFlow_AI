import os
import sys
import uuid
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage

# Add the project root to sys.path to ensure correct imports
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.graph.builder import create_research_graph

def print_banner():
    print("=" * 65)
    print("      🔍  RESEARCHFLOW AI: MULTI-AGENT BUSINESS RESEARCHER  🔍      ")
    print("=" * 65)
    print("  Coordinated Agents: Clarity ➡️ Research ➡️ Validator ➡️ Synthesis")
    print("  Memory Checkpointer: Persistent Multi-turn thread")
    print("  Human-in-the-Loop: Active Gatekeeping")
    print("=" * 65)
    print()

def main():
    # Load .env file
    load_dotenv()
    
    print_banner()
    
    # Initialize the compiled LangGraph workflow
    graph = create_research_graph()
    
    # Session thread ID — unique per process start to prevent state bleed (ADR-005)
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    print(f"🟢 Session started. Memory thread ID: '{thread_id}'")
    print("Type 'exit' or 'quit' to end.")
    print()
    
    # Start loop
    while True:
        try:
            # Check if there's any active clarification needed from the last graph run
            state = graph.get_state(config)
            
            # If state has clarity_status == "needs_clarification", prompt for clarification
            if state.values and state.values.get("clarity_status") == "needs_clarification":
                user_prompt = "📝 Clarification Response: "
            else:
                user_prompt = "👤 User Query: "
                
            user_input = input(user_prompt)
            if user_input.strip().lower() in ["exit", "quit"]:
                print("\n👋 Thank you for using ResearchFlow AI!")
                break
                
            if not user_input.strip():
                continue
                
            print("\n🚀 Starting Multi-Agent Coordination Flow...")
            
            # Send message to graph
            # LangGraph checkpointer will append the message to history on this thread_id
            inputs = {"messages": [HumanMessage(content=user_input)]}
            
            # Stream the execution steps so we see node changes
            for event in graph.stream(inputs, config, stream_mode="updates"):
                for node_name, state_update in event.items():
                    print(f"\n⚙️  Completed Node: [{node_name.upper()}]")
                    
                    # Log state field updates specifically
                    if "clarity_status" in state_update:
                        print(f"   ↳ clarity_status: '{state_update['clarity_status']}'")
                    if "attempts" in state_update:
                        print(f"   ↳ research_attempts: {state_update['attempts']}")
                    if "confidence_score" in state_update:
                        print(f"   ↳ research_confidence_score: {state_update['confidence_score']}/10")
                    if "validation_result" in state_update:
                        print(f"   ↳ validation_result: '{state_update['validation_result']}'")
                    if "validator_feedback" in state_update and state_update["validator_feedback"]:
                        print(f"   ↳ validator_feedback: \"{state_update['validator_feedback']}\"")
                        
            # Get final state to print output
            final_state = graph.get_state(config)
            messages = final_state.values.get("messages", [])
            
            if messages:
                latest_msg = messages[-1]
                if isinstance(latest_msg, AIMessage):
                    print("\n" + "="*40 + " OUTPUT MESSAGE " + "="*40)
                    print(latest_msg.content)
                    print("=" * 96 + "\n")
                    
        except KeyboardInterrupt:
            print("\n👋 Session aborted.")
            break
        except Exception as e:
            print(f"\n❌ Error during graph run: {e}", file=sys.stderr)
            print()

if __name__ == "__main__":
    main()
