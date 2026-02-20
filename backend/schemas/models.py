from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field
from enum import Enum
import uuid


# ── Enums ──
class Gender(str, Enum):
    male = "male"
    female = "female"
    other = "other"
    prefer_not_to_say = "prefer_not_to_say"


class TriageLabel(str, Enum):
    Emergency = "Emergency"
    Urgent = "Urgent"
    HomeCare = "HomeCare"


class AnswerType(str, Enum):
    yesno = "yesno"
    text = "text"
    scale = "scale"
    choice = "choice"
    duration = "duration"


# ── Auth Schemas ──
class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)
    full_name: str = Field(..., min_length=2)
    age: Optional[int] = Field(None, ge=0, le=120)
    gender: Optional[Gender] = None
    comorbidities: Optional[List[str]] = []
    language_preference: str = "en"


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    full_name: str


class UserProfile(BaseModel):
    id: str
    email: str
    full_name: str
    age: Optional[int]
    gender: Optional[str]
    comorbidities: List[str] = []
    language_preference: str


# ── Triage Schemas ──
class TriageStartRequest(BaseModel):
    chief_complaint: str = Field(..., min_length=3, max_length=1000,
                                  description="Patient's description of symptoms in their own words")
    patient_age: Optional[int] = Field(None, ge=0, le=120)
    patient_gender: Optional[Gender] = None
    language: str = Field("en", description="Language code: en, hi, te")


class QuestionResponse(BaseModel):
    question_id: str
    question_text: str
    answer_type: AnswerType
    options: Optional[List[str]] = None
    is_follow_up: bool = True


class TriageSessionState(BaseModel):
    session_id: str
    status: str  # active | completed
    current_question: Optional[QuestionResponse] = None
    progress_percent: int = 0
    extracted_symptoms: List[str] = []
    message: Optional[str] = None


class AnswerRequest(BaseModel):
    session_id: str
    question_id: str
    answer: str


class SHAPFeature(BaseModel):
    feature: str
    value: float
    contribution: float
    direction: str  # "increases_risk" | "decreases_risk"
    human_label: str


class TriageResult(BaseModel):
    session_id: str
    triage_label: TriageLabel
    confidence: float
    probabilities: dict
    red_flag_triggered: bool = False
    red_flag_reason: Optional[str] = None
    explanation_text: str
    recommended_action: str
    diseases_considered: List[str] = []
    shap_features: List[SHAPFeature] = []
    remedies: List[str] = []
    nutrition_tips: List[str] = []
    crisis_response: bool = False
    crisis_message: Optional[str] = None


# ── NLP Schemas ──
class ExtractedEntity(BaseModel):
    text: str
    label: str  # SYMPTOM, DURATION, SEVERITY, BODY_PART, MEDICATION
    normalized: Optional[str] = None
    confidence: float = 1.0


class NLPResult(BaseModel):
    entities: List[ExtractedEntity]
    symptoms: List[str]
    intent: str  # symptom_report | emergency_signal | query | greeting
    language_detected: str
    severity_score: Optional[float] = None
    duration_hours: Optional[float] = None


# ── Hospital Schemas ──
class Hospital(BaseModel):
    name: str
    address: str
    distance_km: float
    phone: Optional[str] = None
    type: str  # emergency | specialist | clinic
    maps_url: Optional[str] = None


class HospitalRecommendation(BaseModel):
    urgency: TriageLabel
    hospitals: List[Hospital]
    recommended_specialist: Optional[str] = None
