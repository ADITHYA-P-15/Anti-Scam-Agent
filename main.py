"""
Anti-Scam Sentinel API - Main Application
FastAPI server with zero-latency perception, rate limiting, and forensics
Enhanced with async background processing for <300ms responses
"""

from fastapi import FastAPI, BackgroundTasks, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, Optional, List
import asyncio
import time
from datetime import datetime
import logging

# Rate limiting
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    RATE_LIMIT_AVAILABLE = True
except ImportError:
    RATE_LIMIT_AVAILABLE = False

from agent.detector import ScamDetector
from agent.orchestrator import ConversationOrchestrator, ConversationPhase
from agent.extractor import IntelligenceExtractor
from agent.session_manager import SessionManager
from agent.metrics import MetricsCollector
from agent.models import (
    MessageRequest, AgentResponse, ExtractedEntities, Forensics, 
    ResponseMetadata, LegacyMessageEvent, LegacyAgentResponse, BankAccount,
    ValidatedUPI, TypingBehavior
)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(
    title="Anti-Scam Sentinel API",
    version="2.0.0",
    description="Intelligent honeypot agent for scam detection and intelligence extraction"
)

# Rate limiting setup
if RATE_LIMIT_AVAILABLE:
    limiter = Limiter(key_func=get_remote_address)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    logger.info("✓ Rate limiting enabled")
else:
    limiter = None
    logger.warning("SlowAPI not installed - rate limiting disabled")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
detector = ScamDetector()
orchestrator = ConversationOrchestrator()
extractor = IntelligenceExtractor()
session_manager = SessionManager()
metrics = MetricsCollector()


# =============================================================================
# MIDDLEWARE
# =============================================================================

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add X-Process-Time header to all responses"""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(int(process_time * 1000))
    return response


# =============================================================================
# HEALTH CHECK
# =============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "2.0.0",
        "timestamp": datetime.now().isoformat(),
        "components": {
            "detector": "operational",
            "orchestrator": "operational",
            "extractor": "operational",
            "session_manager": "operational"
        }
    }


@app.get("/")
async def root():
    """Root endpoint - API info"""
    return {
        "name": "Anti-Scam Sentinel API",
        "version": "2.0.0",
        "description": "Intelligent honeypot agent for scam detection and intelligence extraction",
        "endpoints": {
            "health": "GET /health",
            "message": "POST /message",
            "analyze": "GET /analyze?message=...",
            "metrics": "GET /metrics",
            "docs": "GET /docs"
        }
    }


@app.get("/analyze")
async def analyze_message_get(message: str, session_id: str = "default"):
    """GET version of analyze for hackathon compatibility"""
    # Quick scam detection
    detection = detector.quick_detect(message)
    entities = await extractor.extract_intelligence(message, {})
    
    return {
        "session_id": session_id,
        "is_scam": detection.is_scam,
        "confidence_score": detection.confidence,
        "scam_type": detection.scam_type,
        "threat_level": detection.threat_level,
        "extracted_entities": {
            "upi_ids": [u.model_dump() if hasattr(u, 'model_dump') else u for u in entities.get('upi_ids', [])],
            "phone_numbers": entities.get('phone_numbers', []),
            "bank_accounts": entities.get('bank_accounts', []),
        },
        "message": "Scam detected! Stay safe." if detection.is_scam else "No scam detected."
    }


# =============================================================================
# MAIN MESSAGE ENDPOINT (ZERO-LATENCY VERSION)
# =============================================================================

@app.api_route("/message", methods=["GET", "POST"], response_model=None)
async def handle_message_v2(
    request: Request,
    background_tasks: BackgroundTasks,
    # GET params
    message: Optional[str] = None,
    session_id: Optional[str] = None,
    # POST body will be parsed manually
):
    """
    Main API endpoint - Zero-Latency Perception
    Supports both GET and POST for hackathon compatibility
    Returns immediate response (<300ms), heavy processing runs in background
    """
    start_time = time.time()
    
    # Handle both GET and POST
    if request.method == "POST":
        try:
            body = await request.json()
            session_id = body.get("session_id", "default")
            message = body.get("message", "")
        except:
            pass
    
    if not message:
        return {"error": "message parameter required", "usage": "GET /message?message=...&session_id=... or POST with JSON body"}
    
    if not session_id:
        session_id = "default"
    
    try:
        # 1. Load session context (fast - in-memory or Redis)
        session = await session_manager.load_session(session_id)
        logger.info(f"Session {session_id}: Loaded (phase={session.get('current_phase')})")
        
        # 2. FAST: Run rule-based scam detection (no LLM)
        if not session.get('scam_detected'):
            detection_result = await detector.detect(
                message,
                session.get('conversation_history', [])
            )
            session['scam_detected'] = detection_result.is_scam
            session['scam_metadata'] = detection_result.model_dump()
        else:
            from agent.models import DetectionResult
            detection_result = DetectionResult(**session['scam_metadata'])
        
        # 3. Add scammer message to history
        session.setdefault('conversation_history', []).append({
            'role': 'scammer',
            'message': message,
            'timestamp': datetime.now().isoformat()
        })
        
        # 4. Detect scammer frustration (for typing behavior)
        frustration = orchestrator._detect_frustration(message)
        
        # 5. FAST: Get template response immediately (no LLM wait)
        fast_response = orchestrator.get_fallback_response(
            session.get('current_phase', 'initial_contact'),
            session.get('persona', 'elderly_tech_illiterate')
        )
        
        # 6. Calculate typing behavior for human-like simulation
        phase_str = str(session.get('current_phase', 'initial_contact'))
        if isinstance(phase_str, ConversationPhase):
            phase_str = phase_str.value
        typing_behavior = orchestrator._calculate_typing_behavior(
            message, phase_str, frustration
        )
        
        # 7. BACKGROUND: Run expensive operations (LLM response, extraction)
        async def background_processing():
            try:
                # Get LLM-generated response
                llm_response = await orchestrator.generate_response(session, detection_result)
                # Extract intelligence with LLM
                intelligence = await extractor.extract_intelligence(message, session)
                # Update session
                orchestrator.update_session_state(session, intelligence, llm_response)
                await session_manager.save_session(session)
                logger.info(f"Session {session_id}: Background processing complete")
            except Exception as e:
                logger.error(f"Background processing error: {e}")
        
        background_tasks.add_task(background_processing)
        
        # 8. Update session state with fast response
        session = orchestrator.update_session_state(
            session, {}, {'message': fast_response, 'phase': session.get('current_phase'), 'llm_used': 'template'}
        )
        
        # 9. Calculate latency (should be <300ms now)
        latency = time.time() - start_time
        
        # 10. Build response with existing intelligence
        intel = session.get('intelligence', {})
        
        # Convert UPI strings to ValidatedUPI objects if needed
        upi_list = []
        for upi in intel.get('upi_ids', []):
            if isinstance(upi, dict):
                upi_list.append(ValidatedUPI(**upi))
            elif isinstance(upi, str):
                from agent.models import validate_upi
                validation = validate_upi(upi)
                upi_list.append(ValidatedUPI(**validation))
            else:
                upi_list.append(upi)
        
        bank_accounts = [
            BankAccount(**acc) if isinstance(acc, dict) else acc
            for acc in intel.get('bank_accounts', [])
        ]
        
        extracted_entities = ExtractedEntities(
            upi_ids=upi_list,
            bank_accounts=bank_accounts,
            urls=intel.get('urls', []),
            phone_numbers=intel.get('phone_numbers', []),
            amounts=intel.get('amounts', []),
            emails=intel.get('emails', [])
        )
        
        # Determine threat level and intel quality
        triad = detection_result.triad_score
        if triad.total >= 7:
            threat_level = "critical"
        elif triad.total >= 5:
            threat_level = "high"
        elif triad.total >= 3:
            threat_level = "med"
        else:
            threat_level = "low"
        
        # Assess intel quality
        intel_score = extracted_entities.intel_completeness_score
        if intel_score >= 60:
            intel_quality = "actionable"
        elif intel_score >= 30:
            intel_quality = "partial"
        else:
            intel_quality = "low"
        
        forensics = Forensics(
            scam_type=detection_result.scam_type,
            threat_level=threat_level,
            detected_indicators=detection_result.detected_patterns,
            persona_used=session.get('persona'),
            scammer_frustration=frustration,
            intel_quality=intel_quality
        )
        
        metadata = ResponseMetadata(
            phase=phase_str,
            persona=session.get('persona'),
            turn_count=len(session.get('conversation_history', [])),
            latency_ms=int(latency * 1000),
            llm_used='template',  # Fast response uses templates
            typing_behavior=typing_behavior,
            processing_async=True  # Indicates background processing is running
        )
        
        logger.info(
            f"Session {event.session_id}: Fast response in {latency*1000:.0f}ms "
            f"(phase={phase_str}, frustration={frustration})"
        )
        
        return AgentResponse(
            session_id=event.session_id,
            is_scam=detection_result.is_scam,
            confidence_score=detection_result.confidence_score,
            extracted_entities=extracted_entities,
            agent_response=fast_response,
            forensics=forensics,
            metadata=metadata
        )
    
    except Exception as e:
        logger.error(f"Error handling message: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# LEGACY ENDPOINT (for backward compatibility)
# =============================================================================

@app.post("/message-event", response_model=LegacyAgentResponse)
async def handle_message_legacy(
    request: Request,
    event: LegacyMessageEvent,
    background_tasks: BackgroundTasks
):
    """
    Legacy API endpoint - maintains backward compatibility
    """
    # Convert to new format
    new_request = MessageRequest(
        session_id=event.session_id,
        message=event.message,
        timestamp=event.timestamp
    )
    
    # Call new endpoint
    response = await handle_message_v2(request, new_request, background_tasks)
    
    # Convert back to legacy format
    intel_dict = {
        'upi_ids': response.extracted_entities.upi_ids,
        'bank_accounts': [acc.model_dump() for acc in response.extracted_entities.bank_accounts],
        'urls': response.extracted_entities.urls,
        'phone_numbers': response.extracted_entities.phone_numbers,
        'amounts': response.extracted_entities.amounts,
        'emails': response.extracted_entities.emails
    }
    
    return LegacyAgentResponse(
        session_id=response.session_id,
        agent_message=response.agent_response,
        detected=response.is_scam,
        intelligence=intel_dict,
        metadata={
            'phase': response.metadata.phase,
            'persona': response.metadata.persona,
            'turn_count': response.metadata.turn_count,
            'scam_type': response.forensics.scam_type,
            'confidence': response.confidence_score,
            'latency_ms': response.metadata.latency_ms
        }
    )


# =============================================================================
# METRICS & SESSION ENDPOINTS
# =============================================================================

@app.get("/metrics")
async def get_metrics():
    """Get current performance metrics"""
    return await metrics.get_summary()


@app.get("/session/{session_id}")
async def get_session(session_id: str):
    """Get session details (for debugging)"""
    session = await session_manager.load_session(session_id)
    return {
        "session_id": session_id,
        "phase": session.get('current_phase'),
        "persona": session.get('persona'),
        "scam_detected": session.get('scam_detected'),
        "turn_count": len(session.get('conversation_history', [])),
        "intelligence": session.get('intelligence'),
        "conversation": session.get('conversation_history', [])[-5:]
    }


# =============================================================================
# ANALYTICS ENDPOINT
# =============================================================================

from agent.analytics import (
    scammer_profiler, webhook_manager, analytics_builder,
    SessionAnalytics, ScammerProfile, ProfileMatch, WebhookConfig
)

@app.get("/analytics/{session_id}", response_model=SessionAnalytics)
async def get_session_analytics(session_id: str):
    """
    Get detailed analytics for a session
    Includes: timeline, indicators, intelligence score, profile link
    """
    session = await session_manager.load_session(session_id)
    if not session.get('conversation_history'):
        raise HTTPException(status_code=404, detail="Session not found or empty")
    
    analytics = analytics_builder.build(session)
    return analytics


# =============================================================================
# WEBHOOK ENDPOINTS
# =============================================================================

class WebhookRegistration(BaseModel):
    url: str
    events: List[str] = ["scam_detected", "intel_extracted", "high_risk_profile"]
    secret: Optional[str] = None

@app.post("/webhook/register", response_model=WebhookConfig)
async def register_webhook(config: WebhookRegistration):
    """
    Register a webhook for real-time notifications
    Events: scam_detected, intel_extracted, high_risk_profile
    """
    webhook = webhook_manager.register(
        url=config.url,
        events=config.events,
        secret=config.secret
    )
    return webhook


@app.get("/webhook/list")
async def list_webhooks():
    """List all registered webhooks"""
    return {"webhooks": [w.model_dump() for w in webhook_manager.list_webhooks()]}


@app.delete("/webhook/{webhook_id}")
async def delete_webhook(webhook_id: str):
    """Unregister a webhook"""
    success = webhook_manager.unregister(webhook_id)
    if not success:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return {"status": "deleted", "webhook_id": webhook_id}


# =============================================================================
# SCAMMER PROFILING ENDPOINTS
# =============================================================================

@app.get("/profile/lookup")
async def lookup_profile(
    upi: Optional[str] = None,
    phone: Optional[str] = None,
    account: Optional[str] = None
):
    """
    Look up scammer profile by identifier
    Returns matching profile if found
    """
    intelligence = {
        'upi_ids': [{'upi_id': upi}] if upi else [],
        'phone_numbers': [phone] if phone else [],
        'bank_accounts': [{'account_number': account}] if account else []
    }
    
    match = scammer_profiler.lookup(intelligence)
    return match.model_dump()


@app.get("/profile/{profile_id}", response_model=ScammerProfile)
async def get_profile(profile_id: str):
    """Get scammer profile by ID"""
    profile = scammer_profiler.get_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@app.get("/profiles")
async def list_profiles(limit: int = 50, min_risk: float = 0.0):
    """List all scammer profiles, optionally filtered by risk score"""
    profiles = scammer_profiler.get_all_profiles()
    filtered = [p for p in profiles if p.risk_score >= min_risk]
    sorted_profiles = sorted(filtered, key=lambda p: p.risk_score, reverse=True)[:limit]
    return {
        "total": len(profiles),
        "filtered": len(sorted_profiles),
        "profiles": [p.model_dump() for p in sorted_profiles]
    }


# =============================================================================
# STARTUP/SHUTDOWN
# =============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize resources on startup"""
    logger.info("Starting Anti-Scam Sentinel API v2.0...")
    await session_manager.initialize()
    logger.info("✓ Session manager initialized")
    logger.info("✓ Scammer profiler initialized")
    logger.info("✓ Webhook manager initialized")
    logger.info("✓ All systems operational")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup resources on shutdown"""
    logger.info("Shutting down Anti-Scam Sentinel API...")
    await session_manager.cleanup()
    logger.info("✓ Cleanup complete")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

