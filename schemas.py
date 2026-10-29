from enum import Enum
from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Source(str, Enum):
    """Where a piece of data came from."""
    user_entered = "user_entered"
    extracted_from_image = "extracted_from_image"
    missing = "missing"


class Tracked(BaseModel, Generic[T]):
    """A value together with its source, so missing data is explicit."""
    value: Optional[T] = None
    source: Source = Source.missing


class Condition(BaseModel):
    name: str


class Lab(BaseModel):
    name: str
    value: float
    unit: str
    date: Optional[str] = None  # YYYY-MM-DD


class Allergy(BaseModel):
    substance: str
    reaction: Optional[str] = None
    severity: Optional[str] = None
    certainty: Optional[str] = None  # confirmed / suspected


class CurrentMedicine(BaseModel):
    name: str
    strength: Optional[str] = None
    dose: Optional[str] = None
    route: Optional[str] = None
    frequency: Optional[str] = None


class Patient(BaseModel):
    patient_key: Optional[str] = None
    age: Tracked[int] = Field(default_factory=Tracked[int])
    weight_kg: Tracked[float] = Field(default_factory=Tracked[float])
    pregnancy_status: Tracked[str] = Field(default_factory=Tracked[str])
    conditions: Tracked[List[Condition]] = Field(default_factory=Tracked[List[Condition]])
    labs: Tracked[List[Lab]] = Field(default_factory=Tracked[List[Lab]])
    allergies: Tracked[List[Allergy]] = Field(default_factory=Tracked[List[Allergy]])
    current_medicines: Tracked[List[CurrentMedicine]] = Field(
        default_factory=Tracked[List[CurrentMedicine]]
    )


class NewMedicine(BaseModel):
    raw_text: Optional[str] = None
    name: str
    strength: Optional[str] = None
    form: Optional[str] = None
    dose: Optional[str] = None
    route: Optional[str] = None
    frequency: Optional[str] = None
    duration: Optional[str] = None
    prn: bool = False  # "as needed" medicine
    source: Source = Source.user_entered
    confidence: Optional[float] = None  # OCR confidence, if read from an image
    uncertain_fields: List[str] = Field(default_factory=list)


class Context(BaseModel):
    indication: Optional[str] = None
    jurisdiction: Optional[str] = "IN"
    language: Optional[str] = "hi"


class CheckRequest(BaseModel):
    patient: Patient = Field(default_factory=Patient)
    new_prescription: List[NewMedicine]
    context: Context = Field(default_factory=Context)
    user_question: Optional[str] = None