import uuid
import enum
from datetime import datetime
from sqlalchemy import Column, String, ForeignKey, DateTime, Date, Time, Enum, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from database import Base

class SentimentEnum(str, enum.Enum):
    Positive = "Positive"
    Neutral = "Neutral"
    Negative = "Negative"

class TimeStampedModel:
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class HCP(Base, TimeStampedModel):
    __tablename__ = "hcps"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, index=True, nullable=False)
    specialty = Column(String, nullable=True)

    interactions = relationship("Interaction", back_populates="hcp")

class Interaction(Base, TimeStampedModel):
    __tablename__ = "interactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hcp_id = Column(UUID(as_uuid=True), ForeignKey("hcps.id"), nullable=False)
    interaction_type = Column(String, nullable=False)
    interaction_date = Column(Date, nullable=False)
    interaction_time = Column(Time, nullable=False)
    topics_discussed = Column(String, nullable=True)
    sentiment = Column(Enum(SentimentEnum), nullable=True)
    outcomes = Column(String, nullable=True)

    hcp = relationship("HCP", back_populates="interactions")
    attendees = relationship("Attendee", back_populates="interaction", cascade="all, delete-orphan")
    materials = relationship("InteractionMaterial", back_populates="interaction", cascade="all, delete-orphan")
    samples = relationship("InteractionSample", back_populates="interaction", cascade="all, delete-orphan")
    follow_ups = relationship("FollowUpAction", back_populates="interaction", cascade="all, delete-orphan")

class Attendee(Base, TimeStampedModel):
    __tablename__ = "attendees"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    interaction_id = Column(UUID(as_uuid=True), ForeignKey("interactions.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)

    interaction = relationship("Interaction", back_populates="attendees")

class Material(Base, TimeStampedModel):
    __tablename__ = "materials"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, unique=True)

    interaction_associations = relationship("InteractionMaterial", back_populates="material")

class InteractionMaterial(Base, TimeStampedModel):
    __tablename__ = "interaction_materials"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    interaction_id = Column(UUID(as_uuid=True), ForeignKey("interactions.id", ondelete="CASCADE"), nullable=False)
    material_id = Column(UUID(as_uuid=True), ForeignKey("materials.id", ondelete="CASCADE"), nullable=False)

    interaction = relationship("Interaction", back_populates="materials")
    material = relationship("Material", back_populates="interaction_associations")

class Sample(Base, TimeStampedModel):
    __tablename__ = "samples"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, unique=True)

    interaction_associations = relationship("InteractionSample", back_populates="sample")

class InteractionSample(Base, TimeStampedModel):
    __tablename__ = "interaction_samples"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    interaction_id = Column(UUID(as_uuid=True), ForeignKey("interactions.id", ondelete="CASCADE"), nullable=False)
    sample_id = Column(UUID(as_uuid=True), ForeignKey("samples.id", ondelete="CASCADE"), nullable=False)

    interaction = relationship("Interaction", back_populates="samples")
    sample = relationship("Sample", back_populates="interaction_associations")

class FollowUpAction(Base, TimeStampedModel):
    __tablename__ = "follow_up_actions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    interaction_id = Column(UUID(as_uuid=True), ForeignKey("interactions.id", ondelete="CASCADE"), nullable=False)
    description = Column(String, nullable=False)
    is_ai_suggested = Column(Boolean, default=False)
    status = Column(String, default="Pending")

    interaction = relationship("Interaction", back_populates="follow_ups")
