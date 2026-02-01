"""
Pydantic Models for Anti-Scam Sentinel API
Enhanced with UPI validation, typing delays, and intelligence scoring
"""

from pydantic import BaseModel, Field, field_validator, computed_field
from typing import List, Dict, Optional, Literal
from datetime import datetime
import re


# =============================================================================
# UPI Bank Provider Mapping (Intelligence Validation)
# =============================================================================

UPI_PROVIDERS = {
    # Major Banks
    '@ybl': {'bank': 'Yes Bank', 'type': 'bank'},
    '@axl': {'bank': 'Axis Bank', 'type': 'bank'},
    '@okaxis': {'bank': 'Axis Bank', 'type': 'bank'},
    '@okhdfcbank': {'bank': 'HDFC Bank', 'type': 'bank'},
    '@oksbi': {'bank': 'State Bank of India', 'type': 'bank'},
    '@okicici': {'bank': 'ICICI Bank', 'type': 'bank'},
    '@sbi': {'bank': 'State Bank of India', 'type': 'bank'},
    '@icici': {'bank': 'ICICI Bank', 'type': 'bank'},
    '@hdfc': {'bank': 'HDFC Bank', 'type': 'bank'},
    '@axis': {'bank': 'Axis Bank', 'type': 'bank'},
    '@kotak': {'bank': 'Kotak Mahindra Bank', 'type': 'bank'},
    '@ibl': {'bank': 'ICICI Bank', 'type': 'bank'},
    '@axisb': {'bank': 'Axis Bank', 'type': 'bank'},
    '@upi': {'bank': 'Multiple Banks', 'type': 'bank'},
    '@apl': {'bank': 'Airtel Payments Bank', 'type': 'bank'},
    '@boi': {'bank': 'Bank of India', 'type': 'bank'},
    '@pnb': {'bank': 'Punjab National Bank', 'type': 'bank'},
    '@cboi': {'bank': 'Central Bank of India', 'type': 'bank'},
    '@citi': {'bank': 'Citibank', 'type': 'bank'},
    '@dlb': {'bank': 'Dhanalakshmi Bank', 'type': 'bank'},
    '@federal': {'bank': 'Federal Bank', 'type': 'bank'},
    '@freecharge': {'bank': 'Axis Bank (Freecharge)', 'type': 'wallet'},
    '@hsbc': {'bank': 'HSBC', 'type': 'bank'},
    '@idbi': {'bank': 'IDBI Bank', 'type': 'bank'},
    '@idfc': {'bank': 'IDFC First Bank', 'type': 'bank'},
    '@indus': {'bank': 'IndusInd Bank', 'type': 'bank'},
    '@jio': {'bank': 'Jio Payments Bank', 'type': 'bank'},
    '@kbl': {'bank': 'Karnataka Bank', 'type': 'bank'},
    '@kvb': {'bank': 'Karur Vysya Bank', 'type': 'bank'},
    '@rbl': {'bank': 'RBL Bank', 'type': 'bank'},
    '@sib': {'bank': 'South Indian Bank', 'type': 'bank'},
    '@ubi': {'bank': 'Union Bank of India', 'type': 'bank'},
    '@yesbank': {'bank': 'Yes Bank', 'type': 'bank'},
    # Payment Apps
    '@paytm': {'bank': 'Paytm Payments Bank', 'type': 'wallet'},
    '@ptyes': {'bank': 'Paytm (Yes Bank)', 'type': 'wallet'},
    '@ptaxis': {'bank': 'Paytm (Axis Bank)', 'type': 'wallet'},
    '@ptsbi': {'bank': 'Paytm (SBI)', 'type': 'wallet'},
    '@gpay': {'bank': 'Google Pay', 'type': 'wallet'},
    '@oksbipaytm': {'bank': 'SBI (Paytm)', 'type': 'wallet'},
}


def validate_upi(upi_id: str) -> Dict:
    """Validate UPI ID and extract bank provider info"""
    upi_lower = upi_id.lower()
    
    for suffix, info in UPI_PROVIDERS.items():
        if upi_lower.endswith(suffix):
            return {
                'upi_id': upi_id,
                'bank_provider': info['bank'],
                'provider_type': info['type'],
                'verified': True,
                'confidence': 0.95
            }
    
    # Unknown provider
    if '@' in upi_id:
        handle = upi_id.split('@')[1]
        return {
            'upi_id': upi_id,
            'bank_provider': f'Unknown ({handle})',
            'provider_type': 'unknown',
            'verified': False,
            'confidence': 0.5
        }
    
    return {
        'upi_id': upi_id,
        'bank_provider': 'Invalid',
        'provider_type': 'invalid',
        'verified': False,
        'confidence': 0.0
    }


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
        """Normalize whitespace"""
        v = ' '.join(v.split())
        return v
    
    @field_validator('session_id')
    @classmethod
    def validate_session_id(cls, v: str) -> str:
        """Validate session ID format"""
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('Session ID must be alphanumeric with hyphens/underscores only')
        return v


# =============================================================================
# Intelligence Extraction Models (Enhanced)
# =============================================================================

class ValidatedUPI(BaseModel):
    """UPI ID with bank provider validation"""
    upi_id: str
    bank_provider: str = "Unknown"
    provider_type: Literal["bank", "wallet", "unknown", "invalid"] = "unknown"
    verified: bool = False
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class BankAccount(BaseModel):
    """Extracted bank account details"""
    account_number: str
    ifsc: Optional[str] = None
    bank_name: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    account_type: Optional[str] = None  # savings, current, etc.


class ExtractedEntities(BaseModel):
    """All extracted intelligence from conversation"""
    upi_ids: List[ValidatedUPI] = Field(default_factory=list)
    bank_accounts: List[BankAccount] = Field(default_factory=list)
    urls: List[str] = Field(default_factory=list)
    phone_numbers: List[str] = Field(default_factory=list)
    amounts: List[str] = Field(default_factory=list)
    emails: List[str] = Field(default_factory=list)
    
    @computed_field
    @property
    def intel_completeness_score(self) -> float:
        """Calculate intelligence completeness (0-100)"""
        score = 0
        if self.upi_ids:
            score += 30
            # Bonus for verified UPIs
            verified = sum(1 for u in self.upi_ids if u.verified)
            score += min(verified * 5, 10)
        if self.bank_accounts:
            score += 25
            # Bonus for IFSC
            with_ifsc = sum(1 for a in self.bank_accounts if a.ifsc)
            score += min(with_ifsc * 5, 10)
        if self.phone_numbers:
            score += 15
        if self.urls:
            score += 10
        if self.emails:
            score += 5
        if self.amounts:
            score += 5
        return min(score, 100.0)


# =============================================================================
# Forensics Models (Enhanced)
# =============================================================================

class Forensics(BaseModel):
    """Forensic analysis of the scam attempt"""
    scam_type: str = Field(default="unknown")
    threat_level: Literal["critical", "high", "med", "low"] = Field(default="low")
    detected_indicators: List[str] = Field(default_factory=list)
    persona_used: Optional[str] = None
    scammer_frustration: Literal["none", "low", "medium", "high"] = Field(
        default="none",
        description="Detected frustration level in scammer messages"
    )
    intel_quality: Literal["actionable", "partial", "low"] = Field(
        default="low",
        description="Quality assessment of gathered intelligence"
    )


# =============================================================================
# Detection Models
# =============================================================================

class ScamTriadScore(BaseModel):
    """Scam-Triad heuristic scoring"""
    urgency: float = Field(default=0.0, ge=0.0, le=3.0)
    authority: float = Field(default=0.0, ge=0.0, le=3.0)
    emotion: float = Field(default=0.0, ge=0.0, le=2.0)
    financial: float = Field(default=0.0, ge=0.0, le=2.0)
    
    @property
    def total(self) -> float:
        return self.urgency + self.authority + self.emotion + self.financial
    
    @property
    def is_scam(self) -> bool:
        return self.total > 7.0
    
    def to_indicators(self) -> List[str]:
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
# Response Models (Enhanced with Typing Delays)
# =============================================================================

class TypingBehavior(BaseModel):
    """Suggested typing simulation for realistic engagement"""
    typing_delay_ms: int = Field(
        default=0,
        description="Suggested delay before showing response (ms)"
    )
    show_typing_indicator: bool = Field(
        default=False,
        description="Whether to show 'typing...' indicator"
    )
    stall_message: Optional[str] = Field(
        default=None,
        description="Optional stalling message like 'Wait, my phone is slow...'"
    )
    human_simulation_score: float = Field(
        default=0.5,
        ge=0.0, le=1.0,
        description="How human-like the response timing should be"
    )


class ResponseMetadata(BaseModel):
    """Metadata about the response"""
    phase: str
    persona: Optional[str] = None
    turn_count: int = 0
    latency_ms: int = 0
    llm_used: Optional[str] = None
    typing_behavior: TypingBehavior = Field(default_factory=TypingBehavior)
    processing_async: bool = Field(
        default=False,
        description="True if forensics/extraction running in background"
    )


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
                    "upi_ids": [{
                        "upi_id": "scammer@paytm",
                        "bank_provider": "Paytm Payments Bank",
                        "provider_type": "wallet",
                        "verified": True,
                        "confidence": 0.95
                    }],
                    "bank_accounts": [],
                    "intel_completeness_score": 45.0
                },
                "forensics": {
                    "scam_type": "bank_impersonation",
                    "threat_level": "high",
                    "detected_indicators": ["urgency_tactics"],
                    "intel_quality": "actionable"
                },
                "metadata": {
                    "typing_behavior": {
                        "typing_delay_ms": 1500,
                        "show_typing_indicator": True,
                        "stall_message": "Wait, my phone is loading..."
                    },
                    "processing_async": True
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
# Legacy Compatibility
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
