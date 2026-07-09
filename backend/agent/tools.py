import os
import json
from typing import List, Dict, Any, Optional
from langchain_core.tools import tool
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

# Import database and models from parent directory
from database import SessionLocal
import models

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
    materials: List[str] = Field(default_factory=list, description="List of materials shared.")
    samples: List[str] = Field(default_factory=list, description="List of samples distributed.")

class InteractionPatch(BaseModel):
    hcp_name: Optional[str] = None
    topics_discussed: Optional[str] = None
    sentiment: Optional[str] = None
    materials: Optional[List[str]] = None
    samples: Optional[List[str]] = None

class FollowUpSuggestions(BaseModel):
    actions: List[str] = Field(description="List of exactly 3 strategic follow-up actions.")

# ---------------------------------------------------------
# Tools
# ---------------------------------------------------------
@tool
def log_interaction(text_input: str) -> str:
    """Extracts hcp_name, topics_discussed, sentiment, materials, and samples from raw interaction notes."""
    try:
        llm = ChatGroq(model="llama-3.1-8b-instant", api_key=os.getenv("GROQ_API_KEY"), temperature=0)
        structured_llm = llm.with_structured_output(InteractionExtraction)
        result = structured_llm.invoke(text_input)
        return result.model_dump_json()
    except Exception as e:
        return json.dumps({"error": f"Failed to extract interaction data: {str(e)}"})

@tool
def edit_interaction(correction_text: str, current_form: dict) -> str:
    """Analyzes a correction against the current form and outputs a JSON patch of fields to update."""
    try:
        llm = ChatGroq(model="llama-3.1-8b-instant", api_key=os.getenv("GROQ_API_KEY"), temperature=0)
        structured_llm = llm.with_structured_output(InteractionPatch)
        prompt = (
            f"Current form state: {json.dumps(current_form)}\n"
            f"Correction requested: {correction_text}\n"
            f"Only return the specific fields that the user explicitly wants to change. Do not return or guess any other fields."
        )
        result = structured_llm.invoke(prompt)
        # Exclude unset fields to generate a clean patch
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

# List of tools to bind to our LangGraph nodes
tools = [log_interaction, edit_interaction, search_hcp_history, suggest_followups, resolve_materials_and_samples]
