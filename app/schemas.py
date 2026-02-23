from pydantic import BaseModel, Field, field_validator


class PaymentData(BaseModel):
    payment_id: str
    merchant_id: str
    amount: int = Field(..., ge=0, le=999999999)
    currency: str

    @field_validator("amount")
    @classmethod
    def amount_must_be_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("amount must be non-negative")
        return v


class WebhookPayload(BaseModel):
    webhook_id: str
    event_type: str
    data: PaymentData
