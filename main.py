"""
Anti-Scam Honeypot Agent - Main Application
FastAPI server with dual-layer architecture
"""

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional
import asyncio
import time
from datetime import datetime
import logging

from agent.detector import ScamDetector
from agent.orchestrator import ConversationOrchestrator
from agent.extractor import IntelligenceExtractor
from agent.session_manager import SessionManager
from agent.metrics import MetricsCollector

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(title="Anti-Scam Honeypot Agent", version="1.0.0")

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


# Request/Response Models
class MessageEvent(BaseModel):
    session_id: str
    message: str
    timestamp: Optional[str] = None


class AgentResponse(BaseModel):
    session_id: str
    agent_message: str
    detected: bool
    intelligence: Dict
    metadata: Dict


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "components": {
            "detector": "operational",
            "orchestrator": "operational",
            "extractor": "operational",
            "session_manager": "operational"
        }
    }


# Main endpoint
@app.post("/message-event", response_model=AgentResponse)
async def handle_message(
    event: MessageEvent,
    background_tasks: BackgroundTasks
):
    """
    Main API endpoint - processes incoming scammer messages
    
    Workflow:
    1. Load session context
    2. Detect scam (if not already detected)
    3. Run parallel: Generate response + Extract intelligence
    4. Update session state
    5. Return response
    """
    start_time = time.time()
    
    try:
        # 1. Load session context
        session = await session_manager.load_session(event.session_id)
        logger.info(f"Session {event.session_id}: Loaded (phase={session.get('current_phase')})")
        
        # Set timestamp
        if not event.timestamp:
            event.timestamp = datetime.now().isoformat()
        
        # 2. Run detection (if not already detected)
        if not session.get('scam_detected'):
            detection_result = await detector.detect(
                event.message, 
                session.get('conversation_history', [])
            )
            session['scam_detected'] = detection_result['is_scam']
            session['scam_metadata'] = detection_result
            
            logger.info(
                f"Session {event.session_id}: Detection result = {detection_result['is_scam']} "
                f"({detection_result.get('scam_type', 'unknown')})"
            )
        else:
            detection_result = session['scam_metadata']
        
        # 3. Update conversation history with scammer message
        session.setdefault('conversation_history', []).append({
            'role': 'scammer',
            'message': event.message,
            'timestamp': event.timestamp
        })
        
        # 4. Parallel processing: Generate response + Extract intelligence
        response_task = orchestrator.generate_response(session, detection_result)
        extraction_task = extractor.extract_intelligence(event.message, session)
        
        agent_response, new_intelligence = await asyncio.gather(
            response_task,
            extraction_task,
            return_exceptions=True
        )
        
        # Handle exceptions from parallel tasks
        if isinstance(agent_response, Exception):
            logger.error(f"Response generation failed: {agent_response}")
            agent_response = orchestrator.get_fallback_response(session['current_phase'])
        
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
        
        # 7. Save session (async in background)
        background_tasks.add_task(session_manager.save_session, session)
        
        # 8. Log metrics
        background_tasks.add_task(
            metrics.log_interaction,
            session_id=event.session_id,
            latency=latency,
            phase=session['current_phase'],
            intelligence_count=len(session['intelligence'].get('upi_ids', []))
        )
        
        logger.info(
            f"Session {event.session_id}: Response generated in {latency:.3f}s "
            f"(phase={session['current_phase']}, turn={len(session['conversation_history'])})"
        )
        
        # 9. Return response
        return AgentResponse(
            session_id=event.session_id,
            agent_message=agent_response['message'],
            detected=detection_result['is_scam'],
            intelligence=session['intelligence'],
            metadata={
                'phase': session['current_phase'],
                'persona': session.get('persona', 'default'),
                'turn_count': len(session['conversation_history']),
                'scam_type': detection_result.get('scam_type'),
                'confidence': detection_result.get('confidence'),
                'latency_ms': int(latency * 1000)
            }
        )
    
    except Exception as e:
        logger.error(f"Error handling message: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/metrics")
async def get_metrics():
    """
    Get current performance metrics
    """
    return await metrics.get_summary()


@app.get("/session/{session_id}")
async def get_session(session_id: str):
    """
    Get session details (for debugging)
    """
    session = await session_manager.load_session(session_id)
    return {
        "session_id": session_id,
        "phase": session.get('current_phase'),
        "persona": session.get('persona'),
        "scam_detected": session.get('scam_detected'),
        "turn_count": len(session.get('conversation_history', [])),
        "intelligence": session.get('intelligence'),
        "conversation": session.get('conversation_history', [])[-5:]  # Last 5 messages
    }


# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize resources on startup"""
    logger.info("Starting Anti-Scam Honeypot Agent...")
    await session_manager.initialize()
    logger.info("✓ Session manager initialized")
    logger.info("✓ All systems operational")


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup resources on shutdown"""
    logger.info("Shutting down Anti-Scam Honeypot Agent...")
    await session_manager.cleanup()
    logger.info("✓ Cleanup complete")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
