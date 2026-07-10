import os
import json
from typing import List, Dict, Any, Optional
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

# Import database and models from parent directory
from database import SessionLocal
import models

# Shared system prompts — single source of truth for all LLM-calling tools.
from agent.prompts import EXTRACTION_SYSTEM_PROMPT, PATCH_SYSTEM_PROMPT

def get_session() -> Session:
    """Helper to get a database session."""
    return SessionLocal()

# ---------------------------------------------------------
# Schemas for Structured Outputs
# ---------------------------------------------------------
class InteractionExtraction(BaseModel):
    hcp_name: Optional[str] = Field(default=None, description="Name of the Health Care Professional.")
    topics_discussed: Optional[str] = Field(default=None, description="Topics discussed during the interaction.")
    sentiment: Optional[str] = Field(default=None, description="Sentiment: Positive, Neutral, or Negative.")
    # Field names deliberately match the Redux formSlice keys so state_synchronizer can merge them directly.
    materials_shared: List[str] = Field(default_factory=list, description="List of materials shared.")
    samples_distributed: List[str] = Field(default_factory=list, description="List of samples distributed.")

class FieldUpdate(BaseModel):
    field_name: Literal[
        "hcp_name", 
        "interaction_date",
        "interaction_time",
        "interaction_type", 
        "topics_discussed", 
        "sentiment", 
        "materials_shared", 
        "samples_distributed",
        "outcomes"
    ] = Field(
        description="The exact name of the field to update."
    )
    new_value: Union[str, List[str]] = Field(description="The new value for this field. Can be a string or a list of strings depending on the field.")

class EditInteractionSchema(BaseModel):
    updates: List[FieldUpdate] = Field(
        description="A list of explicitly requested changes. ONLY include fields the user explicitly asked to change."
    )

class FollowUpSuggestions(BaseModel):
    actions: List[str] = Field(description="List of exactly 3 strategic follow-up actions.")

# ---------------------------------------------------------
# Tools
# ---------------------------------------------------------
@tool
def extract_interaction(text_input: str) -> str:
    """USE THIS TOOL FOR DRAFTING: Extracts hcp_name, topics_discussed, sentiment, materials_shared, and samples_distributed from raw interaction notes. DO NOT use this for explicit user commands to log/submit the interaction."""
    try:
        # llama-3.1-8b-instant: fast, cheap model appropriate for deterministic field extraction (temperature=0).
        llm = ChatGroq(model="llama-3.1-8b-instant", api_key=os.getenv("GROQ_API_KEY"), temperature=0)
        structured_llm = llm.with_structured_output(InteractionExtraction)
        # Two-message structure: system prompt carries grounding rules + few-shot examples;
        # human message carries only the raw rep notes to be extracted.
        messages = [
            SystemMessage(content=EXTRACTION_SYSTEM_PROMPT),
            HumanMessage(content=text_input),
        ]
        result = structured_llm.invoke(messages)
        return result.model_dump_json()
    except Exception as e:
        return json.dumps({"error": f"Failed to extract interaction data: {str(e)}"})

@tool
def edit_interaction(correction_text: str, current_form: dict) -> str:
    """USE THIS TOOL FOR EDITING: Analyzes a correction against the current form and outputs a JSON patch of fields to update. Apply ONLY the specific changes requested."""
    try:
        # llama-3.1-8b-instant: fast, cheap model appropriate for deterministic patch generation (temperature=0).
        llm = ChatGroq(model="llama-3.1-8b-instant", api_key=os.getenv("GROQ_API_KEY"), temperature=0)
        structured_llm = llm.with_structured_output(EditInteractionSchema)
        # The human turn combines the current form state with the correction request
        # so the model has full context for turn isolation.
        user_turn = (
            f"Current form state:\n{json.dumps(current_form, indent=2)}\n\n"
            f"Correction requested: {correction_text}"
        )
        messages = [
            SystemMessage(content=PATCH_SYSTEM_PROMPT),
            HumanMessage(content=user_turn),
        ]
        result = structured_llm.invoke(messages)
        return result.model_dump_json()
    except Exception as e:
        return json.dumps({"error": f"Failed to generate patch: {str(e)}"})

@tool
def search_hcp_history(hcp_name: str) -> str:
    """Queries the Supabase interactions table for past records matching the HCP."""
    db: Session = get_session()
    try:
        hcps = db.query(models.HCP).filter(models.HCP.name.ilike(f"%{hcp_name}%")).all()
        if not hcps:
            return json.dumps({"result": f"No history found for HCP: {hcp_name}."})
        
        history = []
        for hcp in hcps:
            interactions = db.query(models.Interaction).filter(models.Interaction.hcp_id == hcp.id)\
                             .order_by(models.Interaction.interaction_date.desc()).limit(3).all()
            for interaction in interactions:
                history.append({
                    "date": str(interaction.interaction_date),
                    "topics": interaction.topics_discussed,
                    "sentiment": interaction.sentiment
                })
        return json.dumps({"history": history})
    except Exception as e:
        return json.dumps({"error": f"Database search failed: {str(e)}"})
    finally:
        db.close()

@tool
def suggest_followups(topics: str, sentiment: str) -> str:
    """Generates 3 strategic, life-science-specific follow-up actions based on the interaction topics and sentiment."""
    try:
        # llama-3.3-70b-versatile: larger model used here intentionally — creative, strategic generation
        # benefits from stronger instruction-following. temperature=0.7 adds appropriate variety.
        llm = ChatGroq(model="llama-3.3-70b-versatile", api_key=os.getenv("GROQ_API_KEY"), temperature=0.7)
        structured_llm = llm.with_structured_output(FollowUpSuggestions)
        prompt = (
            f"Generate exactly 3 strategic, life-science-specific follow-up actions for a pharma rep after visiting an HCP.\n"
            f"Topics discussed: {topics}\n"
            f"Sentiment of interaction: {sentiment}"
        )
        result = structured_llm.invoke(prompt)
        return json.dumps({"follow_ups": result.actions})
    except Exception as e:
        return json.dumps({"error": f"Failed to suggest follow-ups: {str(e)}"})

@tool
def resolve_materials_and_samples(item_names: List[str]) -> str:
    """Queries the database to match string names to UUIDs for materials and samples."""
    db: Session = get_session()
    try:
        resolved = {"materials": {}, "samples": {}}
        for name in item_names:
            mat = db.query(models.Material).filter(models.Material.name.ilike(f"%{name}%")).first()
            if mat:
                resolved["materials"][name] = str(mat.id)
            
            samp = db.query(models.Sample).filter(models.Sample.name.ilike(f"%{name}%")).first()
            if samp:
                resolved["samples"][name] = str(samp.id)
                
        return json.dumps({"resolved": resolved})
    except Exception as e:
        return json.dumps({"error": f"Failed to resolve items: {str(e)}"})
    finally:
        db.close()

@tool
def draft_existing_interaction(hcp_name: str, updates: Optional[list] = None) -> str:
    """USE THIS TOOL FOR EDITING HISTORICAL RECORDS: Queries the database for the most recent interaction matching the hcp_name, applies any optional updates to it in memory, and returns the full interaction record as a draft (including interaction_id)."""
    db: Session = get_session()
    try:
        recent_interaction = (
            db.query(models.Interaction)
            .join(models.HCP)
            .filter(models.HCP.name.ilike(f"%{hcp_name}%"))
            .order_by(models.Interaction.created_at.desc())
            .first()
        )
        
        if not recent_interaction:
            return f"Error: No logged interaction found for HCP '{hcp_name}'. Tell the user the record doesn't exist."
            
        # Serialize to dict matching frontend keys
        draft = {
            "interaction_id": str(recent_interaction.id),
            "hcp_name": recent_interaction.hcp_name or (recent_interaction.hcp.name if recent_interaction.hcp else ""),
            "interaction_type": recent_interaction.interaction_type,
            "interaction_date": recent_interaction.interaction_date,
            "interaction_time": recent_interaction.interaction_time,
            "topics_discussed": recent_interaction.topics_discussed,
            "sentiment": recent_interaction.sentiment,
            "outcomes": recent_interaction.outcomes,
            "attendee_names": recent_interaction.attendee_names or [],
            "materials_shared": recent_interaction.materials_shared or [],
            "samples_distributed": recent_interaction.samples_distributed or [],
            "follow_up_actions": recent_interaction.follow_up_actions or [],
        }
        
        # Apply updates if requested immediately
        if updates:
            for update in updates:
                field = update.get("field_name")
                val = update.get("new_value")
                if field in draft:
                    draft[field] = val
                    
        return json.dumps({"draft": draft})
    except Exception as e:
        return f"Database query failed: {str(e)}. Tell the user there was a system error."
    finally:
        db.close()

# List of tools to bind to our LangGraph nodes
tools = [extract_interaction, edit_interaction, search_hcp_history, suggest_followups, resolve_materials_and_samples, draft_existing_interaction]
