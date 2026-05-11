from langgraph.checkpoint.memory import MemorySaver

def get_in_memory_checkpointer() -> MemorySaver:
    """
    Creates and returns a MemorySaver checkpointer to persist conversation history
    and execution state across graph invocations.
    """
    return MemorySaver()
