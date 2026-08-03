from typing import Literal, Optional
from pydantic import BaseModel, Field

class GeminiRemarkResult(BaseModel):
    classification: Literal["Trip", "Non-trip", "Ambiguous"]
    date: Optional[str] = None
    vehicle_identifier: Optional[str] = None
    vehicle_type: Optional[str] = None
    from_location: Optional[str] = None
    to_location: Optional[str] = None
    invoice_number: Optional[str] = None
    short_reason: str = Field(max_length=120)

