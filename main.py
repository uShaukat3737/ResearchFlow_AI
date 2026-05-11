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
    print("        RESEARCHFLOW AI: MULTI-AGENT BUSINESS RESEARCHER        ")
    print("=" * 65)
    print("  Coordinated Agents: Clarity -> Research -> Validator -> Synthesis")
    print("  Memory Checkpointer: Persistent Multi-turn thread")
    print("  Human-in-the-Loop: Active Gatekeeping")
    print("=" * 65)
    print()

def select_llm_provider():
    print("Choose your LLM Execution Mode for this session:")
    print("   [1] Local (Ollama - phi3:mini)")
    print("   [2] Cloud API (Groq - llama-3.3-70b-versatile)")
    print()
    while True:
        choice = input("Enter choice (1 or 2) [default: 1]: ").strip()
        if not choice or choice == "1":
            os.environ["LLM_PROVIDER"] = "ollama"
            os.environ["OLLAMA_MODEL"] = "phi3:mini"
            print("\nSelected Execution: Local 'phi3:mini' (Ollama)\n")
            break
        elif choice == "2":
            os.environ["LLM_PROVIDER"] = "groq"
            print("\nSelected Execution: Cloud 'llama-3.3-70b-versatile' (Groq)\n")
            break
        else:
            print("Invalid choice. Please enter '1' or '2'.")


def main():
    # Load .env file
    load_dotenv()
    
    print_banner()
    select_llm_provider()
    
    # Initialize the compiled LangGraph workflow
    graph = create_research_graph()

    
    # Session thread ID — unique per process start to prevent state bleed (ADR-005)
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    print(f"Session started. Memory thread ID: '{thread_id}'")
    print("Type 'exit' or 'quit' to end.")
    print()
    
    # Start loop
    while True:
        try:
            # Check if there's any active clarification needed from the last graph run
            state = graph.get_state(config)
            
            # If state has clarity_status == "needs_clarification", prompt for clarification
            is_clarification = bool(state.values and state.values.get("clarity_status") == "needs_clarification")
            if is_clarification:
                user_prompt = "Clarification Response: "
            else:
                user_prompt = "User Query: "
                
            user_input = input(user_prompt)
            if user_input.strip().lower() in ["exit", "quit"]:
                print("\nThank you for using ResearchFlow AI!")
                break
                
            if not user_input.strip():
                continue
                
            print("\nStarting Multi-Agent Coordination Flow...")
            
            # Send message to graph
            # LangGraph checkpointer will append the message to history on this thread_id
            inputs = {"messages": [HumanMessage(content=user_input)]}
            
            # Reset query-specific state fields for a brand-new turn to prevent memory bleed
            if not is_clarification:
                inputs.update({
                    "attempts": 0,
                    "research_data": [],
                    "confidence_score": 0,
                    "validation_result": None,
                    "validator_feedback": None,
                    "degraded_mode": None
                })

            
            # Stream the execution steps so we see node changes
            for event in graph.stream(inputs, config, stream_mode="updates"):
                for node_name, state_update in event.items():
                    print(f"\nCompleted Node: [{node_name.upper()}]")
                    
                    # Log state field updates specifically
                    if state_update is not None:
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
            print("\nSession aborted.")
            break
        except Exception as e:
            import traceback
            print("\nError during graph run:", file=sys.stderr)
            traceback.print_exc()
            print()

if __name__ == "__main__":
    main()
