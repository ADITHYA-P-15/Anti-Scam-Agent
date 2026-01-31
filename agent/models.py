"""
Pydantic Models for Anti-Scam Sentinel API
Strict schema enforcement for request/response validation
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Optional, Literal
from datetime import datetime
import re


# =============================================================================
# Input Models
# =============================================================================

class MessageRequest(BaseModel):
    """Incoming message from scammer"""
    session_id: str = Field(..., min_length=1, max_length=100)
    message: str = Field(..., min_length=1, max_length=5000)
    timestamp: Optional[str] = None
    
    @field_validator('message')
    @classmethod
    def sanitize_message(cls, v: str) -> str:
        """
        Sanitize input but preserve content for detection.
        We DON'T remove injection attempts - we detect and handle them.
        """
        # Normalize whitespace
        v = ' '.join(v.split())
        return v
    
    @field_validator('session_id')
    @classmethod
    def validate_session_id(cls, v: str) -> str:
        """Validate session ID format"""
        # Allow alphanumeric, hyphens, underscores
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('Session ID must be alphanumeric with hyphens/underscores only')
        return v


# =============================================================================
# Intelligence Extraction Models
# =============================================================================

class BankAccount(BaseModel):
    """Extracted bank account details"""
    account_number: str
    ifsc: Optional[str] = None
    bank_name: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class ExtractedEntities(BaseModel):
    """All extracted intelligence from conversation"""
    upi_ids: List[str] = Field(default_factory=list)
    bank_accounts: List[BankAccount] = Field(default_factory=list)
    urls: List[str] = Field(default_factory=list)
    phone_numbers: List[str] = Field(default_factory=list)
    amounts: List[str] = Field(default_factory=list)
    emails: List[str] = Field(default_factory=list)


# =============================================================================
# Forensics Models
# =============================================================================

class Forensics(BaseModel):
    """Forensic analysis of the scam attempt"""
    scam_type: str = Field(
        default="unknown",
        description="Type of scam detected"
    )
    threat_level: Literal["high", "med", "low"] = Field(
        default="low",
        description="Severity of the threat"
    )
    detected_indicators: List[str] = Field(
        default_factory=list,
        description="List of scam indicators detected"
    )
    persona_used: Optional[str] = Field(
        default=None,
        description="Persona adopted by the agent"
    )


# =============================================================================
# Detection Models
# =============================================================================

class ScamTriadScore(BaseModel):
    """Scam-Triad heuristic scoring"""
    urgency: float = Field(default=0.0, ge=0.0, le=3.0, description="Urgency score (0-3)")
    authority: float = Field(default=0.0, ge=0.0, le=3.0, description="Authority impersonation score (0-3)")
    emotion: float = Field(default=0.0, ge=0.0, le=2.0, description="Emotional manipulation score (0-2)")
    financial: float = Field(default=0.0, ge=0.0, le=2.0, description="Financial request score (0-2)")
    
    @property
    def total(self) -> float:
        """Total score out of 10"""
        return self.urgency + self.authority + self.emotion + self.financial
    
    @property
    def is_scam(self) -> bool:
        """Returns True if total score > 7"""
        return self.total > 7.0
    
    def to_indicators(self) -> List[str]:
        """Convert scores to indicator list"""
        indicators = []
        if self.urgency > 1.0:
            indicators.append("urgency_tactics")
        if self.authority > 1.0:
            indicators.append("authority_impersonation")
        if self.emotion > 0.5:
            indicators.append("emotional_manipulation")
        if self.financial > 0.5:
            indicators.append("financial_request")
        return indicators


class DetectionResult(BaseModel):
    """Result from scam detection engine"""
    is_scam: bool = False
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    scam_type: str = "unknown"
    triad_score: ScamTriadScore = Field(default_factory=ScamTriadScore)
    detected_patterns: List[str] = Field(default_factory=list)
    reasoning: str = ""
    injection_detected: bool = False


# =============================================================================
# Response Models
# =============================================================================

class ResponseMetadata(BaseModel):
    """Metadata about the response"""
    phase: str
    persona: Optional[str] = None
    turn_count: int = 0
    latency_ms: int = 0
    llm_used: Optional[str] = None  # "gemini", "anthropic", "template"


class AgentResponse(BaseModel):
    """Complete API response with forensics"""
    session_id: str
    is_scam: bool
    confidence_score: float = Field(ge=0.0, le=1.0)
    extracted_entities: ExtractedEntities
    agent_response: str
    forensics: Forensics
    metadata: ResponseMetadata
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "test-session-1",
                "is_scam": True,
                "confidence_score": 0.92,
                "extracted_entities": {
                    "upi_ids": ["scammer@paytm"],
                    "bank_accounts": [],
                    "urls": ["http://fake-bank.com"],
                    "phone_numbers": []
                },
                "agent_response": "Oh no! Is my account really blocked? What do I need to do?",
                "forensics": {
                    "scam_type": "bank_impersonation",
                    "threat_level": "high",
                    "detected_indicators": ["urgency_tactics", "authority_impersonation"],
                    "persona_used": "elderly_tech_illiterate"
                },
                "metadata": {
                    "phase": "trust_building",
                    "persona": "elderly_tech_illiterate",
                    "turn_count": 1,
                    "latency_ms": 234,
                    "llm_used": "gemini"
                }
            }
        }


# =============================================================================
# Session Models
# =============================================================================

class ConversationTurn(BaseModel):
    """A single turn in the conversation"""
    role: Literal["scammer", "agent"]
    message: str
    timestamp: Optional[str] = None


class SessionState(BaseModel):
    """Complete session state"""
    session_id: str
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    last_updated: str = Field(default_factory=lambda: datetime.now().isoformat())
    current_phase: str = "initial_contact"
    persona: Optional[str] = None
    scam_detected: bool = False
    scam_metadata: Optional[DetectionResult] = None
    conversation_history: List[ConversationTurn] = Field(default_factory=list)
    intelligence: ExtractedEntities = Field(default_factory=ExtractedEntities)
    engagement_metrics: Dict = Field(default_factory=dict)


# =============================================================================
# Legacy Compatibility (for existing tests)
# =============================================================================

class LegacyMessageEvent(BaseModel):
    """Legacy format for backward compatibility"""
    session_id: str
    message: str
    timestamp: Optional[str] = None


class LegacyAgentResponse(BaseModel):
    """Legacy response format for backward compatibility"""
    session_id: str
    agent_message: str
    detected: bool
    intelligence: Dict
    metadata: Dict
