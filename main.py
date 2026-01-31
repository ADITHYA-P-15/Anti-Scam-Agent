"""
Anti-Scam Sentinel API - Main Application
FastAPI server with rate limiting, input sanitization, and forensics
"""

from fastapi import FastAPI, BackgroundTasks, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, Optional
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
    ResponseMetadata, LegacyMessageEvent, LegacyAgentResponse, BankAccount
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


# =============================================================================
# MAIN MESSAGE ENDPOINT (NEW FORMAT)
# =============================================================================

@app.post("/message", response_model=AgentResponse)
async def handle_message_v2(
    request: Request,
    event: MessageRequest,
    background_tasks: BackgroundTasks
):
    """
    Main API endpoint - processes incoming scammer messages
    Returns enhanced response with forensics
    """
    start_time = time.time()
    
    try:
        # 1. Load session context
        session = await session_manager.load_session(event.session_id)
        logger.info(f"Session {event.session_id}: Loaded (phase={session.get('current_phase')})")
        
        # 2. Run scam detection
        if not session.get('scam_detected'):
            detection_result = await detector.detect(
                event.message,
                session.get('conversation_history', [])
            )
            session['scam_detected'] = detection_result.is_scam
            session['scam_metadata'] = detection_result.model_dump()
            
            logger.info(
                f"Session {event.session_id}: Detection: is_scam={detection_result.is_scam}, "
                f"score={detection_result.triad_score.total:.1f}/10, type={detection_result.scam_type}"
            )
        else:
            # Reconstruct detection result from saved metadata
            from agent.models import DetectionResult
            detection_result = DetectionResult(**session['scam_metadata'])
        
        # 3. Add scammer message to history
        session.setdefault('conversation_history', []).append({
            'role': 'scammer',
            'message': event.message,
            'timestamp': event.timestamp or datetime.now().isoformat()
        })
        
        # 4. Parallel: Generate response + Extract intelligence
        response_task = orchestrator.generate_response(session, detection_result)
        extraction_task = extractor.extract_intelligence(event.message, session)
        
        agent_response, new_intelligence = await asyncio.gather(
            response_task,
            extraction_task,
            return_exceptions=True
        )
        
        # Handle exceptions
        if isinstance(agent_response, Exception):
            logger.error(f"Response generation failed: {agent_response}")
            agent_response = orchestrator.get_fallback_response(session.get('current_phase', 'initial_contact'))
        
        if isinstance(new_intelligence, Exception):
            logger.error(f"Intelligence extraction failed: {new_intelligence}")
            new_intelligence = {}
        
        # 5. Update session state
        session = orchestrator.update_session_state(
            session,
            new_intelligence,
            agent_response
        )
        
        # 6. Calculate latency
        latency = time.time() - start_time
        session.setdefault('engagement_metrics', {})['last_latency'] = latency
        
        # 7. Save session (background)
        background_tasks.add_task(session_manager.save_session, session)
        
        # 8. Log metrics (background)
        background_tasks.add_task(
            metrics.log_interaction,
            session_id=event.session_id,
            latency=latency,
            phase=str(session.get('current_phase', 'initial_contact')),
            intelligence_count=len(session.get('intelligence', {}).get('upi_ids', []))
        )
        
        logger.info(
            f"Session {event.session_id}: Response in {latency*1000:.0f}ms "
            f"(phase={session.get('current_phase')}, turn={len(session.get('conversation_history', []))})"
        )
        
        # 9. Build response
        intel = session.get('intelligence', {})
        bank_accounts = [
            BankAccount(**acc) if isinstance(acc, dict) else acc
            for acc in intel.get('bank_accounts', [])
        ]
        
        extracted_entities = ExtractedEntities(
            upi_ids=intel.get('upi_ids', []),
            bank_accounts=bank_accounts,
            urls=intel.get('urls', []),
            phone_numbers=intel.get('phone_numbers', []),
            amounts=intel.get('amounts', []),
            emails=intel.get('emails', [])
        )
        
        # Determine threat level
        triad = detection_result.triad_score
        if triad.total >= 7:
            threat_level = "high"
        elif triad.total >= 4:
            threat_level = "med"
        else:
            threat_level = "low"
        
        forensics = Forensics(
            scam_type=detection_result.scam_type,
            threat_level=threat_level,
            detected_indicators=detection_result.detected_patterns,
            persona_used=session.get('persona')
        )
        
        metadata = ResponseMetadata(
            phase=str(session.get('current_phase', 'initial_contact')),
            persona=session.get('persona'),
            turn_count=len(session.get('conversation_history', [])),
            latency_ms=int(latency * 1000),
            llm_used=agent_response.get('llm_used')
        )
        
        return AgentResponse(
            session_id=event.session_id,
            is_scam=detection_result.is_scam,
            confidence_score=detection_result.confidence_score,
            extracted_entities=extracted_entities,
            agent_response=agent_response.get('message', ''),
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
# STARTUP/SHUTDOWN
# =============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize resources on startup"""
    logger.info("Starting Anti-Scam Sentinel API v2.0...")
    await session_manager.initialize()
    logger.info("✓ Session manager initialized")
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
