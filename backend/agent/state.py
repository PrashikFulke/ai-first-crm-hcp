from typing import TypedDict, List, Dict, Any, Annotated
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    """
    State definition for the LangGraph agent handling CRM interactions.
    """
    messages: Annotated[list[BaseMessage], add_messages]
    form_state: Dict[str, Any]
    pending_updates: Dict[str, Any]
    validation_errors: List[str]
