from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import date, time
from uuid import UUID
from models import SentimentEnum

class HCPResponse(BaseModel):
    id: UUID
    name: str
    specialty: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class FollowUpActionCreate(BaseModel):
    description: str
    is_ai_suggested: bool = False
    status: str = "Pending"

class InteractionCreate(BaseModel):
    hcp_id: Optional[UUID] = None
    hcp_name: Optional[str] = None
    interaction_type: str
    interaction_date: date
    interaction_time: time
    topics_discussed: Optional[str] = None
    sentiment: Optional[SentimentEnum] = None
    outcomes: Optional[str] = None
    
    attendee_names: List[str] = []
    materials_shared: List[str] = []
    samples_distributed: List[str] = []
    follow_up_actions: List[FollowUpActionCreate] = []

class InteractionResponse(BaseModel):
    status: str
    interaction_id: UUID

class InteractionUpdate(BaseModel):
    hcp_id: Optional[UUID] = None
    interaction_type: Optional[str] = None
    interaction_date: Optional[date] = None
    interaction_time: Optional[time] = None
    topics_discussed: Optional[str] = None
    sentiment: Optional[SentimentEnum] = None
    outcomes: Optional[str] = None
