import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Payment(Base):
    __tablename__ = "payments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    merchant_id = Column(String(255), nullable=False)
    amount = Column(Integer, nullable=False)  # centavos
    currency = Column(String(10), nullable=False)
    status = Column(String(50), nullable=False, default="pending")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    events = relationship("WebhookEvent", back_populates="payment")


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    webhook_id = Column(String(255), nullable=False, unique=True)
    payment_id = Column(String(36), ForeignKey("payments.id"), nullable=False)
    event_type = Column(String(100), nullable=False)
    payload = Column(Text, nullable=True)
    processing_status = Column(String(50), nullable=False, default="processing")
    received_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    processed_at = Column(DateTime, nullable=True)

    payment = relationship("Payment", back_populates="events")

    __table_args__ = (
        Index("ix_webhook_events_webhook_id", "webhook_id"),
    )
