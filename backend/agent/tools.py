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

class InteractionPatch(BaseModel):
    hcp_name: Optional[str] = None
    topics_discussed: Optional[str] = None
    sentiment: Optional[str] = None
    # Field names match Redux formSlice keys (materials_shared / samples_distributed) so that
    # a patch returned by edit_interaction merges correctly into Redux state and triggers
    # the flashGreen animation on the correct form fields.
    materials_shared: Optional[List[str]] = None
    samples_distributed: Optional[List[str]] = None

class FollowUpSuggestions(BaseModel):
    actions: List[str] = Field(description="List of exactly 3 strategic follow-up actions.")

# ---------------------------------------------------------
# Tools
# ---------------------------------------------------------
@tool
def log_interaction(text_input: str) -> str:
    """Extracts hcp_name, topics_discussed, sentiment, materials_shared, and samples_distributed from raw interaction notes."""
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
    """Analyzes a correction against the current form and outputs a JSON patch of fields to update."""
    try:
        # llama-3.1-8b-instant: fast, cheap model appropriate for deterministic patch generation (temperature=0).
        llm = ChatGroq(model="llama-3.1-8b-instant", api_key=os.getenv("GROQ_API_KEY"), temperature=0)
        structured_llm = llm.with_structured_output(InteractionPatch)
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
        # exclude_none=True produces a clean patch — only explicitly changed fields are returned.
        return result.model_dump_json(exclude_none=True)
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
def update_submitted_interaction(interaction_id: str, updates: dict) -> str:
    """Updates an already submitted interaction in the database given its ID and fields to update."""
    db: Session = get_session()
    try:
        interaction = db.query(models.Interaction).filter(models.Interaction.id == interaction_id).first()
        if not interaction:
            return json.dumps({"error": f"Interaction with ID {interaction_id} not found."})
        
        # Explicit allowlist — intentionally excludes hcp_id so the agent cannot reassign
        # an interaction to a different HCP. That operation requires a deliberate human action.
        valid_fields = ["interaction_type", "interaction_date", "interaction_time", "topics_discussed", "sentiment", "outcomes"]
        for k, v in updates.items():
            if k in valid_fields:
                setattr(interaction, k, v)
        
        db.commit()
        return json.dumps({"success": True, "interaction_id": interaction_id, "updated_fields": list(updates.keys())})
    except Exception as e:
        db.rollback()
        return json.dumps({"error": f"Failed to update interaction: {str(e)}"})
    finally:
        db.close()

# List of tools to bind to our LangGraph nodes
tools = [log_interaction, edit_interaction, search_hcp_history, suggest_followups, resolve_materials_and_samples, update_submitted_interaction]
