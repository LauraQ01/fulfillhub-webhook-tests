from pydantic import BaseModel, Field, StrictStr, field_validator


class PaymentData(BaseModel):
    payment_id: StrictStr
    merchant_id: StrictStr
    amount: int = Field(..., ge=0, le=999999999)
    currency: StrictStr

    @field_validator("amount")
    @classmethod
    def amount_must_be_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("amount must be non-negative")
        return v


class WebhookPayload(BaseModel):
    webhook_id: StrictStr
    event_type: StrictStr
    data: PaymentData
