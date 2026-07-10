import os
import json
from typing import Literal
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, ToolMessage, AIMessage, HumanMessage
from .state import AgentState
from .tools import tools

# Initialize primary model and bind our tools
llm = ChatGroq(model="llama-3.1-8b-instant", api_key=os.getenv("GROQ_API_KEY"), temperature=0)
llm_with_tools = llm.bind_tools(tools)

system_prompt = """You are an AI assistant for a life-science CRM.
Your role is to help a pharmaceutical field rep log interactions with Healthcare Professionals (HCPs).
- Use `log_interaction` to extract structured data from raw notes.
- Use `edit_interaction` if the user is correcting the current form.
- Use `update_submitted_interaction` if the user specifically asks to update a previously logged interaction by ID or context.
- Use `search_hcp_history` to pull past context if the user asks.
- Use `suggest_followups` to generate next steps.
- Use `resolve_materials_and_samples` to verify database IDs.
Once you have successfully executed the necessary tools, provide a brief, conversational confirmation to the user.
"""

def intent_router(state: AgentState):
    """
    Decides whether the user is logging new data, editing, or just chatting,
    and binds the tools accordingly.
    """
    messages = state.get("messages", [])
    if not messages:
        return {"messages": []}
    
    # Inject system prompt at the beginning if not present
    if not any(isinstance(m, SystemMessage) for m in messages):
        messages = [SystemMessage(content=system_prompt)] + messages

    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}

def should_continue(state: AgentState) -> Literal["tool_executor", "state_synchronizer"]:
    """Conditional routing based on whether the intent router called a tool."""
    messages = state.get("messages", [])
    last_message = messages[-1]
    
    # If the LLM requested tool calls, route to tool execution
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tool_executor"
    
    # If no tool calls, the LLM has finished reasoning and given its final chat response. 
    # Route to state synchronization and then end.
    return "state_synchronizer"

def state_synchronizer(state: AgentState):
    """
    Merges pending updates into the main form state and validates for missing mandatory fields.
    """
    form_state = state.get("form_state", {}).copy()
    pending_updates = state.get("pending_updates", {}).copy()
    validation_errors = []
    messages = state.get("messages", [])

    # Scan the recent messages for ToolMessage outputs to parse and merge
    for msg in reversed(messages):
        if isinstance(msg, ToolMessage):
            try:
                data = json.loads(msg.content)
                if "error" not in data:
                    if msg.name == "edit_interaction" and "updates" in data:
                        for update in data["updates"]:
                            field = update["field_name"]
                            val = update["new_value"]
                            pending_updates[field] = val
                    else:
                        for k, v in data.items():
                            # Only update if the value is meaningful and explicitly provided
                            if v is not None and v != "" and v != [] and v != "HCP" and k not in ["history", "follow_ups", "resolved"]:
                                pending_updates[k] = v
            except json.JSONDecodeError:
                pass
        # Stop scanning once we hit the user's original message for this turn
        elif isinstance(msg, HumanMessage):
            break

    # Merge pending updates into the global form state
    form_state.update(pending_updates)
    
    # Check for mandatory fields based on the updated state
    if not form_state.get("hcp_name"):
        validation_errors.append("HCP Name missing")
    if not form_state.get("topics_discussed"):
        validation_errors.append("Topics Discussed missing")

    return {
        "form_state": form_state,
        "pending_updates": pending_updates,
        "validation_errors": validation_errors
    }

# ---------------------------------------------------------
# Graph Construction
# ---------------------------------------------------------
workflow = StateGraph(AgentState)

workflow.add_node("intent_router", intent_router)
workflow.add_node("tool_executor", ToolNode(tools))
workflow.add_node("state_synchronizer", state_synchronizer)

workflow.add_edge(START, "intent_router")
workflow.add_conditional_edges("intent_router", should_continue)

# CORE FIX: Loop back from the tool executor to the intent router.
# This allows the LLM to read the tool output and decide if it needs to call 
# another tool or formulate a final response to the user.
workflow.add_edge("tool_executor", "intent_router")

workflow.add_edge("state_synchronizer", END)

# Compile graph
app = workflow.compile()
