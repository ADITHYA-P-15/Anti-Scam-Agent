"""
Scam Detection Engine - Layer 1
Hybrid approach: Rule-based + LLM classification
"""

import re
from typing import Dict, List
import logging
from anthropic import Anthropic
import os

logger = logging.getLogger(__name__)


class ScamDetector:
    """
    Fast, accurate scam detection using rule-based + LLM hybrid approach
    """
    
    # Keyword blacklists by category
    SCAM_KEYWORDS = {
        'bank_impersonation': [
            'kyc', 'account blocked', 'verify account', 'update kyc',
            'suspend account', 'bank verification', 'rbi', 'reserve bank'
        ],
        'lottery': [
            'congratulations', 'lottery', 'prize', 'winner', 'jackpot',
            'lucky draw', 'won', 'claim prize'
        ],
        'courier': [
            'fedex', 'dhl', 'courier', 'parcel', 'package', 'customs',
            'clearance fee', 'delivery pending'
        ],
        'tax_refund': [
            'tax refund', 'income tax', 'gst refund', 'refund pending',
            'tax department', 'refund amount'
        ],
        'investment': [
            'investment opportunity', 'guaranteed returns', 'profit',
            'trading', 'crypto', 'bitcoin', 'stock market tip'
        ]
    }
    
    URGENCY_PATTERNS = [
        r'immediately',
        r'within \d+ hours?',
        r'urgent',
        r'asap',
        r'right now',
        r'before \d+',
        r'will be (blocked|suspended|closed)',
        r'expire[sd]? (soon|today|tomorrow)'
    ]
    
    SENSITIVE_DATA_REQUESTS = [
        r'otp',
        r'password',
        r'pin',
        r'cvv',
        r'card number',
        r'account number',
        r'aadhar',
        r'pan card'
    ]
    
    def __init__(self):
        """Initialize detector with LLM client"""
        api_key = os.getenv('ANTHROPIC_API_KEY')
        self.client = Anthropic(api_key=api_key) if api_key else None
        
        if not self.client:
            logger.warning("No Anthropic API key found - LLM detection disabled")
    
    async def detect(self, message: str, conversation_history: List[Dict]) -> Dict:
        """
        Main detection method - hybrid approach
        
        Returns:
            {
                'is_scam': bool,
                'scam_type': str,
                'confidence': float,
                'detected_patterns': List[str],
                'reasoning': str
            }
        """
        # Step 1: Fast rule-based check
        rule_based_result = self._rule_based_detection(message)
        
        # IMPORTANT: Lower threshold for detection since we don't have LLM fallback
        # If ANY scam patterns detected, mark as scam
        if rule_based_result['confidence'] > 0.3:  # Was 0.8, now more sensitive
            logger.info(f"Rule-based detection: confidence ({rule_based_result['confidence']:.2f})")
            return rule_based_result
        
        # If LLM available, use it for edge cases
        if self.client and rule_based_result['confidence'] > 0.1:
            logger.info("Running LLM classification...")
            llm_result = await self._llm_detection(message, conversation_history)
            
            combined_confidence = (
                rule_based_result['confidence'] * 0.4 + 
                llm_result['confidence'] * 0.6
            )
            
            return {
                'is_scam': combined_confidence > 0.5,
                'scam_type': llm_result.get('scam_type', rule_based_result['scam_type']),
                'confidence': combined_confidence,
                'detected_patterns': rule_based_result['detected_patterns'],
                'reasoning': llm_result.get('reasoning', 'Hybrid detection')
            }
        
        # Low confidence - but in testing, be more aggressive
        # If we detected ANY patterns, call it a scam
        if rule_based_result['detected_patterns']:
            rule_based_result['is_scam'] = True
            rule_based_result['confidence'] = max(rule_based_result['confidence'], 0.6)
            return rule_based_result
        
        return rule_based_result
    
    def _rule_based_detection(self, message: str) -> Dict:
        """
        Fast keyword and pattern-based detection
        """
        message_lower = message.lower()
        detected_patterns = []
        scam_type = 'unknown'
        score = 0.0
        
        # Check keyword categories
        for category, keywords in self.SCAM_KEYWORDS.items():
            matches = [kw for kw in keywords if kw in message_lower]
            if matches:
                detected_patterns.append(f"keywords_{category}")
                score += 0.3
                scam_type = category
                logger.debug(f"Matched keywords ({category}): {matches}")
        
        # Check urgency patterns
        urgency_matches = [
            pattern for pattern in self.URGENCY_PATTERNS
            if re.search(pattern, message_lower)
        ]
        if urgency_matches:
            detected_patterns.append("urgency_tactics")
            score += 0.2
            logger.debug(f"Urgency patterns found: {len(urgency_matches)}")
        
        # Check sensitive data requests
        sensitive_matches = [
            pattern for pattern in self.SENSITIVE_DATA_REQUESTS
            if re.search(pattern, message_lower)
        ]
        if sensitive_matches:
            detected_patterns.append("sensitive_data_request")
            score += 0.25
            logger.debug(f"Sensitive data requests: {len(sensitive_matches)}")
        
        # Check for URLs (often phishing)
        url_pattern = r'https?://[^\s]+'
        if re.search(url_pattern, message):
            detected_patterns.append("contains_url")
            score += 0.15
        
        # Check for phone numbers (scammers often provide contact)
        phone_pattern = r'\b(?:\+91|0)?[6-9]\d{9}\b'
        if re.search(phone_pattern, message):
            detected_patterns.append("contains_phone")
            score += 0.1
        
        # Normalize score
        confidence = min(score, 1.0)
        
        return {
            'is_scam': confidence > 0.5,
            'scam_type': scam_type if scam_type != 'unknown' else 'general',
            'confidence': confidence,
            'detected_patterns': detected_patterns,
            'reasoning': 'Rule-based detection'
        }
    
    async def _llm_detection(self, message: str, conversation_history: List[Dict]) -> Dict:
        """
        LLM-based classification for complex cases
        """
        # Build conversation context
        context = "\n".join([
            f"{msg['role']}: {msg['message']}"
            for msg in conversation_history[-5:]  # Last 5 messages
        ])
        
        prompt = f"""You are a scam detection specialist. Analyze this message and determine if it's a scam attempt.

Consider:
1. Impersonation (bank, government, courier, lottery, romantic interest)
2. Urgency tactics ("immediately", "within 24 hours", "account will be blocked")
3. Request for sensitive information (OTP, password, bank details)
4. Suspicious links or payment requests
5. Unusual grammar or spelling for official communication
6. Romance or investment schemes (pig butchering)

Message: "{message}"

Conversation context (if any):
{context if context else "No prior context"}

Respond ONLY with valid JSON:
{{
  "is_scam": true or false,
  "scam_type": "bank_impersonation" or "lottery" or "romance" or "investment" or "courier" or "other",
  "confidence": 0.0 to 1.0,
  "reasoning": "brief explanation"
}}"""

        try:
            response = self.client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=200,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}]
            )
            
            # Parse JSON response
            import json
            result_text = response.content[0].text.strip()
            
            # Remove markdown code blocks if present
            if result_text.startswith('```'):
                result_text = result_text.split('```')[1]
                if result_text.startswith('json'):
                    result_text = result_text[4:]
            
            result = json.loads(result_text)
            
            return {
                'is_scam': result.get('is_scam', False),
                'scam_type': result.get('scam_type', 'unknown'),
                'confidence': result.get('confidence', 0.5),
                'reasoning': result.get('reasoning', 'LLM analysis')
            }
        
        except Exception as e:
            logger.error(f"LLM detection failed: {e}")
            return {
                'is_scam': False,
                'scam_type': 'unknown',
                'confidence': 0.0,
                'reasoning': f'LLM error: {str(e)}'
            }


# Standalone test
if __name__ == "__main__":
    import asyncio
    
    detector = ScamDetector()
    
    test_messages = [
        "Your SBI account will be blocked within 24 hours. Update KYC immediately: http://fake-sbi.com",
        "Hey! How are you doing today?",
        "Congratulations! You have won a lottery of Rs 5 lakh. Claim now!",
        "Your FedEx parcel is pending. Pay customs clearance of Rs 500 to: scammer@paytm"
    ]
    
    async def test():
        for msg in test_messages:
            print(f"\nMessage: {msg}")
            result = await detector.detect(msg, [])
            print(f"Result: {result}")
    
    asyncio.run(test())
