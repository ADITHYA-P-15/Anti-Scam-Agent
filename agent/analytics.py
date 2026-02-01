"""
Advanced Analytics, Webhooks, and Scammer Profiling
Production-grade features for Anti-Scam Sentinel
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Set
from pydantic import BaseModel, Field, HttpUrl
import httpx

logger = logging.getLogger(__name__)


# =============================================================================
# SCAMMER PROFILING MODELS
# =============================================================================

class ScammerProfile(BaseModel):
    """Profile of a scammer built from multiple sessions"""
    profile_id: str
    first_seen: str = Field(default_factory=lambda: datetime.now().isoformat())
    last_seen: str = Field(default_factory=lambda: datetime.now().isoformat())
    
    # Identifiers (collected across sessions)
    upi_ids: List[str] = Field(default_factory=list)
    bank_accounts: List[Dict] = Field(default_factory=list)
    phone_numbers: List[str] = Field(default_factory=list)
    urls: List[str] = Field(default_factory=list)
    emails: List[str] = Field(default_factory=list)
    
    # Behavior analysis
    scam_types: List[str] = Field(default_factory=list)
    session_ids: List[str] = Field(default_factory=list)
    total_sessions: int = 0
    avg_message_length: float = 0.0
    frustration_patterns: List[str] = Field(default_factory=list)
    
    # Risk assessment
    risk_score: float = 0.0  # 0-100
    confidence: float = 0.0


class ProfileMatch(BaseModel):
    """Result of profile lookup"""
    matched: bool
    profile: Optional[ScammerProfile] = None
    match_type: str = "none"  # "upi", "phone", "bank", "behavioral"
    confidence: float = 0.0


# =============================================================================
# WEBHOOK MODELS
# =============================================================================

class WebhookConfig(BaseModel):
    """Webhook configuration"""
    webhook_id: str
    url: str
    secret: Optional[str] = None
    events: List[str] = Field(default_factory=lambda: ["scam_detected", "intel_extracted"])
    active: bool = True
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class WebhookEvent(BaseModel):
    """Event payload for webhook"""
    event_type: str
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    session_id: str
    data: Dict


# =============================================================================
# SESSION ANALYTICS MODELS
# =============================================================================

class ConversationTimeline(BaseModel):
    """Timeline entry for session analytics"""
    turn: int
    timestamp: str
    role: str
    message_preview: str  # Truncated for privacy
    indicators: List[str] = Field(default_factory=list)
    phase: str = ""
    intelligence_extracted: List[str] = Field(default_factory=list)


class SessionAnalytics(BaseModel):
    """Complete analytics for a session"""
    session_id: str
    created_at: str
    last_updated: str
    
    # Summary
    total_turns: int = 0
    is_scam: bool = False
    scam_type: str = "unknown"
    persona_used: str = "unknown"
    
    # Timeline
    timeline: List[ConversationTimeline] = Field(default_factory=list)
    
    # Intelligence
    intelligence_score: float = 0.0
    entities_extracted: Dict = Field(default_factory=dict)
    
    # Engagement
    avg_latency_ms: float = 0.0
    max_frustration_level: str = "none"
    engagement_duration_seconds: int = 0
    
    # Profile link
    scammer_profile_id: Optional[str] = None


# =============================================================================
# SCAMMER PROFILER
# =============================================================================

class ScammerProfiler:
    """
    Tracks scammer patterns across sessions
    Uses in-memory storage (can be extended to Redis/DB)
    """
    
    def __init__(self):
        # In-memory storage
        self.profiles: Dict[str, ScammerProfile] = {}
        
        # Index for fast lookups
        self.upi_index: Dict[str, str] = {}  # upi -> profile_id
        self.phone_index: Dict[str, str] = {}  # phone -> profile_id
        self.bank_index: Dict[str, str] = {}  # account_number -> profile_id
        
        logger.info("ScammerProfiler initialized")
    
    def _generate_profile_id(self) -> str:
        """Generate unique profile ID"""
        import uuid
        return f"scammer-{uuid.uuid4().hex[:12]}"
    
    def lookup(self, intelligence: Dict) -> ProfileMatch:
        """Look up existing profile by intelligence data"""
        # Check UPI IDs
        for upi in intelligence.get('upi_ids', []):
            upi_id = upi.get('upi_id') if isinstance(upi, dict) else upi
            if upi_id in self.upi_index:
                profile_id = self.upi_index[upi_id]
                return ProfileMatch(
                    matched=True,
                    profile=self.profiles[profile_id],
                    match_type="upi",
                    confidence=0.95
                )
        
        # Check phone numbers
        for phone in intelligence.get('phone_numbers', []):
            if phone in self.phone_index:
                profile_id = self.phone_index[phone]
                return ProfileMatch(
                    matched=True,
                    profile=self.profiles[profile_id],
                    match_type="phone",
                    confidence=0.9
                )
        
        # Check bank accounts
        for acc in intelligence.get('bank_accounts', []):
            acc_num = acc.get('account_number') if isinstance(acc, dict) else acc
            if acc_num in self.bank_index:
                profile_id = self.bank_index[acc_num]
                return ProfileMatch(
                    matched=True,
                    profile=self.profiles[profile_id],
                    match_type="bank",
                    confidence=0.95
                )
        
        return ProfileMatch(matched=False)
    
    def update_profile(self, session: Dict) -> str:
        """Update or create profile from session data"""
        intelligence = session.get('intelligence', {})
        
        # Try to find existing profile
        match = self.lookup(intelligence)
        
        if match.matched and match.profile:
            profile = match.profile
        else:
            # Create new profile
            profile_id = self._generate_profile_id()
            profile = ScammerProfile(profile_id=profile_id)
            self.profiles[profile_id] = profile
        
        # Update profile with new data
        profile.last_seen = datetime.now().isoformat()
        profile.session_ids.append(session.get('session_id', 'unknown'))
        profile.total_sessions = len(profile.session_ids)
        
        # Add UPIs
        for upi in intelligence.get('upi_ids', []):
            upi_id = upi.get('upi_id') if isinstance(upi, dict) else upi
            if upi_id and upi_id not in profile.upi_ids:
                profile.upi_ids.append(upi_id)
                self.upi_index[upi_id] = profile.profile_id
        
        # Add phones
        for phone in intelligence.get('phone_numbers', []):
            if phone and phone not in profile.phone_numbers:
                profile.phone_numbers.append(phone)
                self.phone_index[phone] = profile.profile_id
        
        # Add bank accounts
        for acc in intelligence.get('bank_accounts', []):
            if isinstance(acc, dict):
                acc_num = acc.get('account_number')
                if acc_num and acc_num not in [a.get('account_number') for a in profile.bank_accounts]:
                    profile.bank_accounts.append(acc)
                    self.bank_index[acc_num] = profile.profile_id
        
        # Add URLs/emails
        for url in intelligence.get('urls', []):
            if url not in profile.urls:
                profile.urls.append(url)
        
        for email in intelligence.get('emails', []):
            if email not in profile.emails:
                profile.emails.append(email)
        
        # Update scam type
        scam_meta = session.get('scam_metadata', {})
        scam_type = scam_meta.get('scam_type', 'unknown')
        if scam_type != 'unknown' and scam_type not in profile.scam_types:
            profile.scam_types.append(scam_type)
        
        # Calculate risk score
        profile.risk_score = self._calculate_risk_score(profile)
        profile.confidence = min(0.5 + (profile.total_sessions * 0.1), 1.0)
        
        logger.info(f"Updated profile {profile.profile_id}: {profile.total_sessions} sessions, risk={profile.risk_score}")
        return profile.profile_id
    
    def _calculate_risk_score(self, profile: ScammerProfile) -> float:
        """Calculate risk score based on profile data"""
        score = 0.0
        
        # More sessions = higher risk
        score += min(profile.total_sessions * 10, 30)
        
        # Multiple identifiers = higher risk
        score += min(len(profile.upi_ids) * 5, 20)
        score += min(len(profile.phone_numbers) * 5, 15)
        score += min(len(profile.bank_accounts) * 10, 20)
        
        # Multiple scam types = sophisticated scammer
        score += min(len(profile.scam_types) * 5, 15)
        
        return min(score, 100.0)
    
    def get_profile(self, profile_id: str) -> Optional[ScammerProfile]:
        """Get profile by ID"""
        return self.profiles.get(profile_id)
    
    def get_all_profiles(self) -> List[ScammerProfile]:
        """Get all profiles"""
        return list(self.profiles.values())


# =============================================================================
# WEBHOOK MANAGER
# =============================================================================

class WebhookManager:
    """
    Manages webhook registrations and async event delivery
    """
    
    def __init__(self):
        self.webhooks: Dict[str, WebhookConfig] = {}
        self.event_queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        logger.info("WebhookManager initialized")
    
    def _generate_webhook_id(self) -> str:
        import uuid
        return f"wh-{uuid.uuid4().hex[:8]}"
    
    def register(self, url: str, events: List[str] = None, secret: str = None) -> WebhookConfig:
        """Register a new webhook"""
        webhook_id = self._generate_webhook_id()
        config = WebhookConfig(
            webhook_id=webhook_id,
            url=url,
            secret=secret,
            events=events or ["scam_detected", "intel_extracted", "high_risk_profile"]
        )
        self.webhooks[webhook_id] = config
        logger.info(f"Registered webhook {webhook_id} -> {url}")
        return config
    
    def unregister(self, webhook_id: str) -> bool:
        """Unregister a webhook"""
        if webhook_id in self.webhooks:
            del self.webhooks[webhook_id]
            return True
        return False
    
    def list_webhooks(self) -> List[WebhookConfig]:
        """List all registered webhooks"""
        return list(self.webhooks.values())
    
    async def trigger(self, event_type: str, session_id: str, data: Dict):
        """Trigger webhook event (async)"""
        event = WebhookEvent(
            event_type=event_type,
            session_id=session_id,
            data=data
        )
        
        # Find matching webhooks
        for webhook in self.webhooks.values():
            if webhook.active and event_type in webhook.events:
                asyncio.create_task(self._send_webhook(webhook, event))
    
    async def _send_webhook(self, webhook: WebhookConfig, event: WebhookEvent):
        """Send webhook with retry"""
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    headers = {"Content-Type": "application/json"}
                    if webhook.secret:
                        # Add HMAC signature
                        import hmac
                        import hashlib
                        payload = event.model_dump_json()
                        signature = hmac.new(
                            webhook.secret.encode(),
                            payload.encode(),
                            hashlib.sha256
                        ).hexdigest()
                        headers["X-Webhook-Signature"] = signature
                    
                    response = await client.post(
                        webhook.url,
                        json=event.model_dump(),
                        headers=headers
                    )
                    
                    if response.status_code in [200, 201, 202, 204]:
                        logger.info(f"Webhook {webhook.webhook_id} delivered: {event.event_type}")
                        return
                    else:
                        logger.warning(f"Webhook {webhook.webhook_id} failed: {response.status_code}")
            except Exception as e:
                logger.error(f"Webhook {webhook.webhook_id} error (attempt {attempt+1}): {e}")
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
        
        logger.error(f"Webhook {webhook.webhook_id} failed after {max_retries} attempts")


# =============================================================================
# SESSION ANALYTICS BUILDER
# =============================================================================

class SessionAnalyticsBuilder:
    """
    Builds analytics from session data
    """
    
    def __init__(self, profiler: ScammerProfiler):
        self.profiler = profiler
    
    def build(self, session: Dict) -> SessionAnalytics:
        """Build analytics from session"""
        history = session.get('conversation_history', [])
        scam_meta = session.get('scam_metadata', {})
        intelligence = session.get('intelligence', {})
        metrics = session.get('engagement_metrics', {})
        
        # Build timeline
        timeline = []
        for i, turn in enumerate(history):
            indicators = []
            intel_extracted = []
            
            # Analyze turn
            if turn.get('role') == 'scammer':
                msg = turn.get('message', '').lower()
                if 'kyc' in msg or 'block' in msg:
                    indicators.append("urgency_indicator")
                if 'bank' in msg or 'sbi' in msg:
                    indicators.append("authority_claim")
            
            timeline.append(ConversationTimeline(
                turn=i + 1,
                timestamp=turn.get('timestamp', ''),
                role=turn.get('role', 'unknown'),
                message_preview=turn.get('message', '')[:50] + "..." if len(turn.get('message', '')) > 50 else turn.get('message', ''),
                indicators=indicators,
                phase=str(session.get('current_phase', '')),
                intelligence_extracted=intel_extracted
            ))
        
        # Calculate intel score
        intel_score = 0.0
        if intelligence.get('upi_ids'):
            intel_score += 30
        if intelligence.get('bank_accounts'):
            intel_score += 30
        if intelligence.get('phone_numbers'):
            intel_score += 20
        if intelligence.get('urls'):
            intel_score += 10
        if intelligence.get('emails'):
            intel_score += 10
        
        # Get profile link
        profile_match = self.profiler.lookup(intelligence)
        profile_id = profile_match.profile.profile_id if profile_match.matched else None
        
        return SessionAnalytics(
            session_id=session.get('session_id', 'unknown'),
            created_at=session.get('created_at', datetime.now().isoformat()),
            last_updated=session.get('last_updated', datetime.now().isoformat()),
            total_turns=len(history),
            is_scam=session.get('scam_detected', False),
            scam_type=scam_meta.get('scam_type', 'unknown'),
            persona_used=session.get('persona', 'unknown'),
            timeline=timeline,
            intelligence_score=min(intel_score, 100.0),
            entities_extracted={
                'upi_count': len(intelligence.get('upi_ids', [])),
                'bank_count': len(intelligence.get('bank_accounts', [])),
                'phone_count': len(intelligence.get('phone_numbers', [])),
                'url_count': len(intelligence.get('urls', []))
            },
            avg_latency_ms=metrics.get('last_latency', 0) * 1000,
            max_frustration_level=metrics.get('frustration', 'none'),
            scammer_profile_id=profile_id
        )


# =============================================================================
# GLOBAL INSTANCES (for use in main.py)
# =============================================================================

# Create singleton instances
scammer_profiler = ScammerProfiler()
webhook_manager = WebhookManager()
analytics_builder = SessionAnalyticsBuilder(scammer_profiler)
