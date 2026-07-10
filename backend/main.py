import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from pydantic import BaseModel

from database import engine, Base, get_db
import models
import schemas

# LangGraph agent imports
from agent.graph import app as agent_app
from langchain_core.messages import HumanMessage, AIMessage

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup event: Create all tables in Supabase
    Base.metadata.create_all(bind=engine)
    yield
    # Shutdown event
    pass

app = FastAPI(
    title="AI-First CRM API",
    description="Backend for AI-first CRM 'Log Interaction Screen'. Integrates with Supabase and LangGraph streaming.",
    lifespan=lifespan
)

# CORS enabled
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Chat Schema ---
class ChatRequest(BaseModel):
    message: str
    current_form_state: Dict[str, Any] = {}

# --- New SSE Chat Endpoint ---
@app.post("/api/v1/chat/stream")
async def chat_stream(req: ChatRequest):
    """
    Accepts user chat and current form state, processes through LangGraph, 
    and streams back Server-Sent Events for form updates and conversational text chunks.
    """
    async def event_generator():
        initial_state = {
            "messages": [HumanMessage(content=req.message)],
            "form_state": req.current_form_state,
            "pending_updates": {},
            "validation_errors": []
        }
        
        async for event in agent_app.astream(initial_state, stream_mode="updates"):
            # Check for form state updates from the state synchronizer
            if "state_synchronizer" in event:
                form_state = event["state_synchronizer"].get("form_state", {})
                yield f"event: form_update\ndata: {json.dumps(form_state)}\n\n"

            # Check for text chunks from the LLM (conversational response)
            if "intent_router" in event:
                messages = event["intent_router"].get("messages", [])
                if messages:
                    msg = messages[-1]
                    if isinstance(msg, AIMessage) and msg.content and not msg.tool_calls:
                        yield f"event: text_chunk\ndata: {json.dumps({'text': msg.content})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

# --- Phase 1 Endpoints ---
@app.get("/api/v1/hcps/search", response_model=List[schemas.HCPResponse])
def search_hcps(
    q: str = Query(..., description="Search query for HCP name"), 
    db: Session = Depends(get_db)
):
    """Returns a list of HCPs matching the query (typeahead)."""
    hcps = db.query(models.HCP).filter(models.HCP.name.ilike(f"%{q}%")).all()
    return hcps

@app.post("/api/v1/interactions", response_model=schemas.InteractionResponse)
def create_interaction(
    interaction: schemas.InteractionCreate, 
    db: Session = Depends(get_db)
):
    """Handles nested form submission, saving all related records in a single transaction."""
    try:
        actual_hcp_id = interaction.hcp_id

        # If no ID was provided, or if the provided ID doesn't exist in the DB
        if not actual_hcp_id or not db.query(models.HCP).filter(models.HCP.id == actual_hcp_id).first():
            # Fallback to the provided name, or a default
            fallback_name = interaction.hcp_name if interaction.hcp_name else "Unknown HCP"

            # Check if an HCP with this name already exists to avoid duplicates
            existing_hcp = db.query(models.HCP).filter(models.HCP.name == fallback_name).first()

            if existing_hcp:
                actual_hcp_id = existing_hcp.id
            else:
                # Create a new HCP on the fly
                new_hcp = models.HCP(name=fallback_name, specialty="General")
                db.add(new_hcp)
                db.flush() # Flush to get the new ID
                actual_hcp_id = new_hcp.id

        # 1. Main Interaction
        db_interaction = models.Interaction(
            hcp_id=actual_hcp_id,
            interaction_type=interaction.interaction_type,
            interaction_date=interaction.interaction_date,
            interaction_time=interaction.interaction_time,
            topics_discussed=interaction.topics_discussed,
            sentiment=interaction.sentiment,
            outcomes=interaction.outcomes
        )
        db.add(db_interaction)
        db.flush()

        # 2. Attendees
        for name in interaction.attendee_names:
            db.add(models.Attendee(interaction_id=db_interaction.id, name=name))

        # 3. Materials
        for material_name in interaction.materials_shared:
            material = db.query(models.Material).filter_by(name=material_name).first()
            if not material:
                material = models.Material(name=material_name)
                db.add(material)
                db.flush()
            db.add(models.InteractionMaterial(interaction_id=db_interaction.id, material_id=material.id))

        # 4. Samples
        for sample_name in interaction.samples_distributed:
            sample = db.query(models.Sample).filter_by(name=sample_name).first()
            if not sample:
                sample = models.Sample(name=sample_name)
                db.add(sample)
                db.flush()
            db.add(models.InteractionSample(interaction_id=db_interaction.id, sample_id=sample.id))

        # 5. Follow-ups
        for follow_up in interaction.follow_up_actions:
            db.add(models.FollowUpAction(
                interaction_id=db_interaction.id,
                description=follow_up.description,
                is_ai_suggested=follow_up.is_ai_suggested,
                status=follow_up.status
            ))

        db.commit()
        return {"status": "success", "interaction_id": db_interaction.id}
    
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Transaction failed: {str(e)}")

@app.patch("/api/v1/interactions/{interaction_id}", response_model=schemas.InteractionResponse)
def update_interaction(
    interaction_id: str,
    update_data: schemas.InteractionUpdate,
    db: Session = Depends(get_db)
):
    """Updates a previously logged interaction."""
    try:
        interaction = db.query(models.Interaction).filter(models.Interaction.id == interaction_id).first()
        if not interaction:
            raise HTTPException(status_code=404, detail="Interaction not found")
        
        update_dict = update_data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            setattr(interaction, key, value)
            
        db.commit()
        db.refresh(interaction)
        return {"status": "success", "interaction_id": interaction.id}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Update failed: {str(e)}")

@app.get("/")
def read_root():
    return {"message": "AI-First CRM API is running."}
