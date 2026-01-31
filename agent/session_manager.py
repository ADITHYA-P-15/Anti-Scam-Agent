"""
Session Manager
Handles session storage and retrieval using Redis
"""

import json
from typing import Dict, Optional
import logging
from datetime import datetime
import os

logger = logging.getLogger(__name__)

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("redis package not installed - using in-memory storage")


class SessionManager:
    """
    Manage conversation sessions with Redis backend
    """
    
    def __init__(self):
        """Initialize session manager"""
        self.redis_client = None
        self.in_memory_store = {}  # Fallback storage
        self.redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        self.ttl = int(os.getenv('SESSION_TTL', 3600))  # 1 hour default
    
    async def initialize(self):
        """Initialize Redis connection"""
        if not REDIS_AVAILABLE:
            logger.info("Using in-memory session storage (Redis not available)")
            return
        
        try:
            self.redis_client = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            
            # Test connection
            await self.redis_client.ping()
            logger.info(f"✓ Connected to Redis: {self.redis_url}")
        
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}")
            logger.info("Falling back to in-memory storage")
            self.redis_client = None
    
    async def load_session(self, session_id: str) -> Dict:
        """
        Load session from storage
        
        Returns empty session if not found
        """
        # Try Redis first
        if self.redis_client:
            try:
                key = f"session:{session_id}"
                data = await self.redis_client.get(key)
                
                if data:
                    session = json.loads(data)
                    logger.debug(f"Loaded session {session_id} from Redis")
                    return session
            
            except Exception as e:
                logger.error(f"Redis load error: {e}")
        
        # Fallback to in-memory
        if session_id in self.in_memory_store:
            logger.debug(f"Loaded session {session_id} from memory")
            return self.in_memory_store[session_id]
        
        # Return new session
        logger.info(f"Creating new session: {session_id}")
        return self._create_new_session(session_id)
    
    async def save_session(self, session: Dict):
        """
        Save session to storage
        """
        session_id = session.get('session_id')
        
        if not session_id:
            logger.error("Cannot save session without session_id")
            return
        
        # Update timestamp
        session['last_updated'] = datetime.now().isoformat()
        
        # Try Redis first
        if self.redis_client:
            try:
                key = f"session:{session_id}"
                data = json.dumps(session)
                await self.redis_client.set(key, data, ex=self.ttl)
                logger.debug(f"Saved session {session_id} to Redis (TTL={self.ttl}s)")
                return
            
            except Exception as e:
                logger.error(f"Redis save error: {e}")
        
        # Fallback to in-memory
        self.in_memory_store[session_id] = session
        logger.debug(f"Saved session {session_id} to memory")
    
    async def delete_session(self, session_id: str):
        """
        Delete session from storage
        """
        # Redis
        if self.redis_client:
            try:
                key = f"session:{session_id}"
                await self.redis_client.delete(key)
                logger.info(f"Deleted session {session_id} from Redis")
            except Exception as e:
                logger.error(f"Redis delete error: {e}")
        
        # In-memory
        if session_id in self.in_memory_store:
            del self.in_memory_store[session_id]
            logger.info(f"Deleted session {session_id} from memory")
    
    async def get_all_sessions(self) -> list:
        """
        Get all active session IDs (for monitoring)
        """
        sessions = []
        
        # Redis
        if self.redis_client:
            try:
                keys = await self.redis_client.keys("session:*")
                sessions.extend([k.replace("session:", "") for k in keys])
            except Exception as e:
                logger.error(f"Redis keys error: {e}")
        
        # In-memory
        sessions.extend(self.in_memory_store.keys())
        
        return list(set(sessions))
    
    async def cleanup(self):
        """
        Cleanup resources
        """
        if self.redis_client:
            await self.redis_client.close()
            logger.info("Redis connection closed")
    
    def _create_new_session(self, session_id: str) -> Dict:
        """
        Create a new empty session
        """
        from agent.orchestrator import ConversationPhase
        
        return {
            'session_id': session_id,
            'created_at': datetime.now().isoformat(),
            'last_updated': datetime.now().isoformat(),
            'current_phase': ConversationPhase.INITIAL_CONTACT,
            'persona': None,  # Will be selected on first scam detection
            'scam_detected': False,
            'scam_metadata': {},
            'conversation_history': [],
            'intelligence': {
                'upi_ids': [],
                'bank_accounts': [],
                'phone_numbers': [],
                'urls': [],
                'amounts': [],
                'emails': []
            },
            'engagement_metrics': {
                'start_time': datetime.now().isoformat(),
                'turn_count': 0,
                'last_latency': 0
            }
        }


# Test
if __name__ == "__main__":
    import asyncio
    
    async def test():
        manager = SessionManager()
        await manager.initialize()
        
        # Test create and load
        session = await manager.load_session("test-123")
        print(f"New session: {json.dumps(session, indent=2)}")
        
        # Test save
        session['conversation_history'].append({
            'role': 'scammer',
            'message': 'Test message'
        })
        await manager.save_session(session)
        
        # Test reload
        reloaded = await manager.load_session("test-123")
        print(f"\nReloaded session has {len(reloaded['conversation_history'])} messages")
        
        # Cleanup
        await manager.cleanup()
    
    asyncio.run(test())
