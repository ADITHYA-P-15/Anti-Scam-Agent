"""
Metrics Collector
Track competition-relevant metrics
"""

from typing import Dict, List
import logging
from datetime import datetime
from collections import defaultdict

logger = logging.getLogger(__name__)


class MetricsCollector:
    """
    Collect and analyze performance metrics
    """
    
    def __init__(self):
        """Initialize metrics storage"""
        self.metrics = {
            'interactions': [],
            'detections': [],
            'phases': defaultdict(int),
            'intelligence_scores': []
        }
    
    async def log_interaction(
        self,
        session_id: str,
        latency: float,
        phase: str,
        intelligence_count: int
    ):
        """
        Log a single interaction
        """
        interaction = {
            'session_id': session_id,
            'timestamp': datetime.now().isoformat(),
            'latency_ms': int(latency * 1000),
            'phase': phase,
            'intelligence_count': intelligence_count
        }
        
        self.metrics['interactions'].append(interaction)
        self.metrics['phases'][phase] += 1
        
        logger.debug(f"Logged interaction: {session_id} - {latency*1000:.0f}ms - {phase}")
    
    async def log_detection(
        self,
        session_id: str,
        is_scam: bool,
        scam_type: str,
        confidence: float
    ):
        """
        Log a scam detection
        """
        detection = {
            'session_id': session_id,
            'timestamp': datetime.now().isoformat(),
            'is_scam': is_scam,
            'scam_type': scam_type,
            'confidence': confidence
        }
        
        self.metrics['detections'].append(detection)
        logger.debug(f"Logged detection: {session_id} - scam={is_scam} ({confidence:.2f})")
    
    async def log_intelligence_score(
        self,
        session_id: str,
        intelligence: Dict
    ):
        """
        Calculate and log intelligence quality score
        """
        score = self._calculate_intelligence_score(intelligence)
        
        self.metrics['intelligence_scores'].append({
            'session_id': session_id,
            'timestamp': datetime.now().isoformat(),
            'score': score,
            'intelligence': intelligence
        })
        
        logger.debug(f"Intelligence score for {session_id}: {score:.1f}/100")
    
    def _calculate_intelligence_score(self, intelligence: Dict) -> float:
        """
        Score intelligence quality based on completeness
        
        Scoring:
        - UPI IDs: 40 points (20 per UPI, max 2)
        - Bank accounts: 40 points (complete account with IFSC)
        - URLs: 10 points
        - Phone numbers: 5 points
        - Emails: 5 points
        """
        score = 0.0
        
        # UPI IDs (40 points max)
        upi_count = len(intelligence.get('upi_ids', []))
        score += min(upi_count * 20, 40)
        
        # Bank accounts (40 points max)
        bank_accounts = intelligence.get('bank_accounts', [])
        for acc in bank_accounts:
            if acc.get('account_number') and acc.get('ifsc'):
                score += 40
                break  # Max 40 points even if multiple accounts
        
        # URLs (10 points)
        if intelligence.get('urls'):
            score += 10
        
        # Phone numbers (5 points)
        if intelligence.get('phone_numbers'):
            score += 5
        
        # Emails (5 points)
        if intelligence.get('emails'):
            score += 5
        
        return min(score, 100.0)
    
    async def get_summary(self) -> Dict:
        """
        Get comprehensive metrics summary
        """
        interactions = self.metrics['interactions']
        detections = self.metrics['detections']
        intel_scores = self.metrics['intelligence_scores']
        
        # Calculate averages
        if not interactions:
            return {
                'status': 'no_data',
                'total_interactions': 0
            }
        
        avg_latency = sum(i['latency_ms'] for i in interactions) / len(interactions)
        
        # Detection accuracy
        if detections:
            avg_detection_confidence = sum(d['confidence'] for d in detections) / len(detections)
            scam_count = sum(1 for d in detections if d['is_scam'])
        else:
            avg_detection_confidence = 0
            scam_count = 0
        
        # Intelligence quality
        if intel_scores:
            avg_intelligence_score = sum(s['score'] for s in intel_scores) / len(intel_scores)
        else:
            avg_intelligence_score = 0
        
        # Phase distribution
        phase_distribution = dict(self.metrics['phases'])
        
        # Calculate engagement duration (unique sessions)
        session_turns = defaultdict(int)
        for interaction in interactions:
            session_turns[interaction['session_id']] += 1
        
        avg_engagement = sum(session_turns.values()) / len(session_turns) if session_turns else 0
        
        return {
            'status': 'operational',
            'timestamp': datetime.now().isoformat(),
            'total_interactions': len(interactions),
            'unique_sessions': len(session_turns),
            'performance': {
                'avg_latency_ms': round(avg_latency, 2),
                'max_latency_ms': max(i['latency_ms'] for i in interactions),
                'min_latency_ms': min(i['latency_ms'] for i in interactions)
            },
            'detection': {
                'total_detections': len(detections),
                'scams_detected': scam_count,
                'avg_confidence': round(avg_detection_confidence, 3)
            },
            'engagement': {
                'avg_turns_per_session': round(avg_engagement, 1),
                'max_turns': max(session_turns.values()) if session_turns else 0,
                'phase_distribution': phase_distribution
            },
            'intelligence': {
                'avg_quality_score': round(avg_intelligence_score, 1),
                'total_scored': len(intel_scores)
            }
        }
    
    async def get_session_metrics(self, session_id: str) -> Dict:
        """
        Get metrics for a specific session
        """
        session_interactions = [
            i for i in self.metrics['interactions']
            if i['session_id'] == session_id
        ]
        
        session_detections = [
            d for d in self.metrics['detections']
            if d['session_id'] == session_id
        ]
        
        session_intel = [
            s for s in self.metrics['intelligence_scores']
            if s['session_id'] == session_id
        ]
        
        return {
            'session_id': session_id,
            'total_turns': len(session_interactions),
            'avg_latency_ms': (
                sum(i['latency_ms'] for i in session_interactions) / len(session_interactions)
                if session_interactions else 0
            ),
            'phases_visited': list(set(i['phase'] for i in session_interactions)),
            'scam_detected': any(d['is_scam'] for d in session_detections),
            'intelligence_score': (
                session_intel[-1]['score'] if session_intel else 0
            )
        }
    
    def reset(self):
        """
        Reset all metrics (for testing)
        """
        self.metrics = {
            'interactions': [],
            'detections': [],
            'phases': defaultdict(int),
            'intelligence_scores': []
        }
        logger.info("Metrics reset")


# Test
if __name__ == "__main__":
    import asyncio
    
    async def test():
        collector = MetricsCollector()
        
        # Log some test data
        await collector.log_interaction("test-1", 0.5, "building_trust", 0)
        await collector.log_interaction("test-1", 0.6, "extracting_intel", 1)
        await collector.log_detection("test-1", True, "bank_impersonation", 0.95)
        
        await collector.log_intelligence_score("test-1", {
            'upi_ids': ['scammer@paytm'],
            'urls': ['http://fake.com']
        })
        
        # Get summary
        summary = await collector.get_summary()
        print("Summary:")
        import json
        print(json.dumps(summary, indent=2))
        
        # Get session metrics
        session = await collector.get_session_metrics("test-1")
        print("\nSession metrics:")
        print(json.dumps(session, indent=2))
    
    asyncio.run(test())
