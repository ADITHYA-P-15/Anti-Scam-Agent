"""
Conversation Orchestrator - Layer 2
State machine for phase management and persona-based response generation
UPDATED FOR GOOGLE GEMINI
"""

from enum import Enum
from typing import Dict, List
import random
import logging
import os

logger = logging.getLogger(__name__)

# Try importing Google Gemini
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False


class ConversationPhase(str, Enum):
    """Conversation phases for state machine"""
    INITIAL_CONTACT = "initial_contact"
    SCAM_DETECTED = "scam_detected"
    BUILDING_TRUST = "building_trust"
    PLAYING_DUMB = "playing_dumb"
    EXTRACTING_INTEL = "extracting_intel"
    CLOSING = "closing"


class ConversationOrchestrator:
    """
    Manages conversation flow, persona selection, and response generation
    """
    
    # Persona definitions
    PERSONAS = {
        'retired_professional': {
            'name': 'Retired Professional (65+)',
            'description': 'A retired person with savings but limited tech knowledge. Polite, trusting, asks for help.',
            'speech_style': 'Polite, simple language, often asks "Can you help me understand..."',
            'traits': ['not tech-savvy', 'trusting', 'has money', 'polite', 'cautious but cooperative']
        },
        'small_business_owner': {
            'name': 'Small Business Owner',
            'description': 'Busy entrepreneur, distracted, concerned about business accounts.',
            'speech_style': 'Rushed, direct, "I\'m in a meeting but..."',
            'traits': ['busy', 'stressed', 'wants quick resolution', 'moderate tech knowledge']
        },
        'anxious_professional': {
            'name': 'Young Anxious Professional',
            'description': 'Young professional worried about account issues. Some tech knowledge but gullible.',
            'speech_style': 'Anxious tone, asks many questions, "Wait, what?!"',
            'traits': ['worried', 'asks questions', 'somewhat tech-savvy', 'emotional']
        }
    }
    
    # Phase-specific strategies
    PHASE_STRATEGIES = {
        ConversationPhase.INITIAL_CONTACT: {
            'goal': 'Appear normal',
            'instruction': 'Respond neutrally and show slight curiosity. Don\'t reveal awareness of scam.',
            'example': 'Hello, who is this?'
        },
        ConversationPhase.BUILDING_TRUST: {
            'goal': 'Appear vulnerable and concerned',
            'instruction': 'Express concern about the issue. Ask basic questions. Show willingness to comply but don\'t act immediately.',
            'example': 'Oh no, is my account really blocked? What happened?'
        },
        ConversationPhase.PLAYING_DUMB: {
            'goal': 'Increase engagement through friction',
            'instruction': 'Ask for clarification. Express technical difficulties or confusion. Make scammer explain step-by-step.',
            'example': 'I\'m not very good with technology. Can you explain this more simply?'
        },
        ConversationPhase.EXTRACTING_INTEL: {
            'goal': 'Get payment details',
            'instruction': 'Show readiness to comply. Ask for specific payment details (UPI, account). Request backup methods.',
            'example': 'I\'m ready to pay. What\'s your UPI ID? My app is asking for it.'
        },
        ConversationPhase.CLOSING: {
            'goal': 'End gracefully',
            'instruction': 'Stall or express doubt. Suggest calling bank or waiting.',
            'example': 'Let me call my bank first to verify this.'
        }
    }
    
    # Fallback responses (when LLM fails)
    FALLBACK_RESPONSES = {
        ConversationPhase.INITIAL_CONTACT: "Hello? Who is this?",
        ConversationPhase.BUILDING_TRUST: "I'm concerned about this. Can you explain what's happening?",
        ConversationPhase.PLAYING_DUMB: "Sorry, I didn't quite understand that. Can you explain again?",
        ConversationPhase.EXTRACTING_INTEL: "Okay, I'm ready to do this. What information do you need from me?",
        ConversationPhase.CLOSING: "Let me think about this and get back to you."
    }
    
    def __init__(self):
        """Initialize orchestrator with Gemini client"""
        google_key = os.getenv('GOOGLE_API_KEY')
        
        self.model = None
        
        if google_key and GEMINI_AVAILABLE:
            try:
                genai.configure(api_key=google_key)
                self.model = genai.GenerativeModel('gemini-1.5-flash')
                logger.info("✓ Using Google Gemini for response generation")
            except Exception as e:
                logger.warning(f"Gemini init failed: {e}")
        
        if not self.model:
            logger.warning("No Gemini available - will use template responses")
    
    async def generate_response(self, session: Dict, detection_result: Dict) -> Dict:
        """
        Generate contextual response based on phase and persona
        """
        phase = session.get('current_phase', ConversationPhase.INITIAL_CONTACT)
        persona = session.get('persona', 'retired_professional')
        
        # Select persona if not set
        if 'persona' not in session:
            persona = self._select_persona(detection_result)
            session['persona'] = persona
        
        # If not a scam, respond normally
        if not detection_result.get('is_scam'):
            return {
                'message': "I'm sorry, I don't understand. Are you trying to reach someone?",
                'phase': phase
            }
        
        # Get intelligence gaps
        intelligence_gaps = self._get_intelligence_gaps(session.get('intelligence', {}))
        
        # Generate response
        logger.info(f"Generating response - model={self.model is not None}, phase={phase}, persona={persona}")
        
        if self.model:
            try:
                logger.info("Calling Gemini to generate response...")
                response = self._gemini_generate_response(
                    session, 
                    persona, 
                    phase, 
                    intelligence_gaps
                )
                logger.info(f"Gemini returned: {response[:50]}...")
                return {'message': response, 'phase': phase}
            except Exception as e:
                logger.error(f"Gemini response generation failed: {e}", exc_info=True)
        else:
            logger.warning("No Gemini model available, using template")
        
        # Fallback to template-based response
        response = self._template_based_response(phase, intelligence_gaps)
        logger.info(f"Using template response: {response[:50]}...")
        return {'message': response, 'phase': phase}
    
    def _select_persona(self, detection_result: Dict) -> str:
        """Select appropriate persona based on scam type"""
        scam_type = detection_result.get('scam_type', 'general')
        
        persona_mapping = {
            'bank_impersonation': 'anxious_professional',
            'lottery': 'retired_professional',
            'investment': 'small_business_owner',
            'courier': 'retired_professional'
        }
        
        selected = persona_mapping.get(scam_type, 'retired_professional')
        logger.info(f"Selected persona: {selected} for scam type: {scam_type}")
        return selected
    
    def _get_intelligence_gaps(self, intelligence: Dict) -> Dict:
        """Identify what intelligence we still need"""
        gaps = {
            'needs_upi': len(intelligence.get('upi_ids', [])) == 0,
            'needs_bank': len(intelligence.get('bank_accounts', [])) == 0,
            'needs_url': len(intelligence.get('urls', [])) == 0,
            'needs_phone': len(intelligence.get('phone_numbers', [])) == 0
        }
        
        # Prioritize what to ask for
        if gaps['needs_upi']:
            gaps['priority'] = 'upi'
        elif gaps['needs_bank']:
            gaps['priority'] = 'bank'
        elif gaps['needs_phone']:
            gaps['priority'] = 'phone'
        elif gaps['needs_url']:
            gaps['priority'] = 'url'
        else:
            gaps['priority'] = 'backup'  # Ask for backup methods
        
        return gaps
    
    def _gemini_generate_response(
        self, 
        session: Dict, 
        persona: str, 
        phase: str,
        intelligence_gaps: Dict
    ) -> str:
        """Use Gemini to generate contextual response"""
        persona_info = self.PERSONAS[persona]
        strategy = self.PHASE_STRATEGIES[phase]
        
        # Build conversation history (last 5 messages)
        history = session.get('conversation_history', [])[-5:]
        history_text = "\n".join([
            f"{msg['role'].upper()}: {msg['message']}"
            for msg in history
        ])
        
        # Build intelligence goals
        goals = []
        if intelligence_gaps['needs_upi']:
            goals.append("Get the scammer's UPI ID")
        if intelligence_gaps['needs_bank']:
            goals.append("Get the scammer's bank account number and IFSC code")
        
        goals_text = ", ".join(goals) if goals else "Continue engaging naturally"
        
        prompt = f"""You are roleplaying as a {persona_info['name']} in a conversation with a suspected scammer.

PERSONA: {persona_info['description']}
Speech style: {persona_info['speech_style']}

CURRENT PHASE: {phase.upper()}
GOAL: {strategy['goal']}

CONVERSATION SO FAR:
{history_text if history_text else "Just starting"}

WHAT TO DO: {strategy['instruction']}
INTELLIGENCE GOAL: {goals_text}

CRITICAL INSTRUCTIONS:
1. Stay in character - sound like a real {persona_info['name']}
2. Keep responses natural, 1-3 sentences
3. If in EXTRACTING_INTEL phase, actively ask for payment details:
   - Ask for UPI ID if you don't have it
   - Ask for bank account + IFSC if UPI doesn't work
   - Ask for phone number "in case there's a problem"
   - Ask for BACKUP payment methods ("what if this doesn't work?")
4. Show willingness to pay but need the details
5. Never break character

Generate ONLY your next response as this character."""

        try:
            response = self.model.generate_content(prompt)
            message = response.text.strip()
            
            # Clean up
            if message.startswith('"') and message.endswith('"'):
                message = message[1:-1]
            
            logger.info(f"Gemini response (phase={phase}): {message[:50]}...")
            return message
        
        except Exception as e:
            logger.error(f"Gemini generation error: {e}")
            raise
    
    def _template_based_response(self, phase: str, intelligence_gaps: Dict) -> str:
        """Generate response using templates (fallback)"""
        if phase == ConversationPhase.EXTRACTING_INTEL:
            if intelligence_gaps.get('needs_upi'):
                return random.choice([
                    "I'm ready to send the payment. What's your UPI ID? I need to type it exactly.",
                    "My app is asking for a UPI ID. Can you type it out for me letter by letter?",
                    "Okay I understand. What's your UPI ID? And do you have a phone number in case there's a problem?",
                    "I have my phone ready. What UPI ID should I send to? Also, what if it doesn't work?"
                ])
            elif intelligence_gaps.get('needs_bank'):
                return random.choice([
                    "My UPI has a daily limit. Can I transfer to your bank account? What's the account number and IFSC?",
                    "The UPI isn't working. Do you have a bank account number and IFSC? Also your phone number?",
                    "What's your account number and IFSC code? Can you also give me a contact number?",
                    "I'll do a bank transfer. What are the details? And do you have a backup account just in case?"
                ])
            elif intelligence_gaps.get('needs_phone'):
                return random.choice([
                    "What's your phone number? I want to call you if there's any issue.",
                    "Can you give me a contact number? Just in case something goes wrong.",
                    "Do you have a phone number I can save? My friend told me to always get a contact."
                ])
            else:
                # Already have some intel, ask for backup
                return random.choice([
                    "What if that payment method doesn't work? Do you have a backup UPI or account?",
                    "Just to be safe, can you give me another payment option in case this fails?",
                    "My friend told me to always have a backup. Do you have another UPI ID or account number?",
                    "Can you also give me your phone number? Just in case I have questions later."
                ])
        
        elif phase == ConversationPhase.PLAYING_DUMB:
            return random.choice([
                "I'm not very good with technology. Can you explain this step by step?",
                "Sorry, I didn't quite understand. Can you say that again more slowly?",
                "Wait, which button do I press? I'm looking at my phone now but I'm confused.",
                "I'm a bit confused. Can you walk me through exactly what I need to do?"
            ])
        
        return self.FALLBACK_RESPONSES[phase]
    
    def update_session_state(
        self, 
        session: Dict, 
        new_intelligence: Dict, 
        response: Dict
    ) -> Dict:
        """Update session state and handle phase transitions"""
        # Add agent response to history
        session.setdefault('conversation_history', []).append({
            'role': 'agent',
            'message': response['message'],
            'timestamp': None
        })
        
        # Merge new intelligence
        for key, values in new_intelligence.items():
            if values:
                existing = session.setdefault('intelligence', {}).setdefault(key, [])
                
                # For bank_accounts, handle dicts specially
                if key == 'bank_accounts':
                    # Avoid duplicates by checking account numbers
                    existing_acc_nums = [acc.get('account_number') for acc in existing]
                    for new_acc in values:
                        if new_acc.get('account_number') not in existing_acc_nums:
                            existing.append(new_acc)
                else:
                    # For simple types (strings), extend and deduplicate
                    existing.extend(values)
                    session['intelligence'][key] = list(set(existing))
        
        # Phase transitions - SLOWER to extend conversations
        current_phase = session.get('current_phase', ConversationPhase.INITIAL_CONTACT)
        turn_count = len(session['conversation_history'])
        intelligence = session.get('intelligence', {})
        
        if current_phase == ConversationPhase.INITIAL_CONTACT and session.get('scam_detected'):
            session['current_phase'] = ConversationPhase.BUILDING_TRUST
            logger.info(f"Phase: INITIAL_CONTACT -> BUILDING_TRUST")
        
        elif current_phase == ConversationPhase.BUILDING_TRUST and turn_count >= 4:
            session['current_phase'] = ConversationPhase.PLAYING_DUMB
            logger.info(f"Phase: BUILDING_TRUST -> PLAYING_DUMB (turn={turn_count})")
        
        elif current_phase == ConversationPhase.PLAYING_DUMB and turn_count >= 7:
            session['current_phase'] = ConversationPhase.EXTRACTING_INTEL
            logger.info(f"Phase: PLAYING_DUMB -> EXTRACTING_INTEL (turn={turn_count})")
        
        elif current_phase == ConversationPhase.EXTRACTING_INTEL:
            has_upi = len(intelligence.get('upi_ids', [])) > 0
            has_bank = len(intelligence.get('bank_accounts', [])) > 0
            has_phone = len(intelligence.get('phone_numbers', [])) > 0
            has_multiple = (len(intelligence.get('upi_ids', [])) + len(intelligence.get('bank_accounts', []))) >= 2
            
            # Only close if we have GREAT intel AND enough turns
            if has_multiple and has_phone and turn_count >= 12:
                session['current_phase'] = ConversationPhase.CLOSING
                logger.info(f"Phase: EXTRACTING_INTEL -> CLOSING (excellent intel)")
            elif has_multiple and turn_count >= 14:
                session['current_phase'] = ConversationPhase.CLOSING
                logger.info(f"Phase: EXTRACTING_INTEL -> CLOSING (good intel)")
            elif (has_upi or has_bank) and turn_count >= 18:
                session['current_phase'] = ConversationPhase.CLOSING
                logger.info(f"Phase: EXTRACTING_INTEL -> CLOSING (extended conversation)")
        
        session.setdefault('engagement_metrics', {})['turn_count'] = turn_count
        
        return session
    
    def get_fallback_response(self, phase: str) -> Dict:
        """Get fallback response for when everything fails"""
        return {
            'message': self.FALLBACK_RESPONSES.get(phase, "I'm having trouble understanding. Can you repeat that?"),
            'phase': phase
        }
