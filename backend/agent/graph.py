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

system_prompt = """You are an AI CRM assistant. You have specific tools. You MUST follow this exact lifecycle and choose your tools accordingly:

RULE 1: DRAFTING (New Information)
If the user provides raw notes about a meeting or interaction, you MUST use the extract_interaction (or equivalent extraction) tool to parse the data into the draft form. DO NOT log the interaction yet.

RULE 2: EDITING (Corrections)
If the user asks to change, fix, update, or add to the current draft (e.g., "Actually, it was negative", "Change the materials"), you MUST use the edit_interaction tool. Apply ONLY the specific changes requested. DO NOT log the interaction yet.
RULE: If the user's message contains imperative verbs related to data modification (e.g., "change", "update", "fix", "remove", "add to"), you MUST route to the `edit_interaction` tool.
RULE: Only route to the conversational assistant if the user is asking a question (e.g., "does this look right?", "am I missing anything?") or making small talk.

RULE 3: LOGGING (Explicit Consent Only)
You are STRICTLY FORBIDDEN from using the log_interaction (or final commit) tool unless the user explicitly gives you the command to do so (e.g., "Log it", "Save it", "Looks good, submit"). If they just give you notes, assume they are still drafting.

- Use `draft_existing_interaction` if the user specifically asks to update or correct a previously logged historical interaction. It will pull the record into the draft.
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
    current_form = state.get("form_state", {})
    if not messages:
        return {"messages": []}
    
    grounding_prompt = (
        "CRITICAL: The current state of the user's draft form is provided below in JSON. "
        "Evaluate it to answer the user's question, but YOU MUST strictly follow these rules:\n"
        "1. NEVER mention the words 'JSON', 'keys', 'variables', or 'draft form'.\n"
        "2. NEVER output raw variable names like 'hcp_name' or 'topics_discussed'. Translate them into natural language (e.g., 'Healthcare Professional Name').\n"
        "3. Speak conversationally as a helpful human assistant. Do not just list fields.\n\n"
        f"Current State: {json.dumps(current_form, indent=2)}"
    )
    
    # Filter out any old system messages and inject the fresh ones
    core_messages = [m for m in messages if not isinstance(m, SystemMessage)]
    updated_messages = [
        SystemMessage(content=system_prompt),
        SystemMessage(content=grounding_prompt)
    ] + core_messages

    response = llm_with_tools.invoke(updated_messages)
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
                    if msg.name == "edit_interaction":
                        try:
                            # Handle both dicts and Pydantic models gracefully
                            updates_list = data.get("updates", []) if isinstance(data, dict) else getattr(data, "updates", [])
                            
                            for update in updates_list:
                                field = update["field_name"] if isinstance(update, dict) else update.field_name
                                val = update["new_value"] if isinstance(update, dict) else update.new_value
                                pending_updates[field] = val
                        except Exception as e:
                            print(f"Edit Tool Error: {e}")
                    elif msg.name == "draft_existing_interaction" and "draft" in data:
                        for k, v in data["draft"].items():
                            pending_updates[k] = v
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
