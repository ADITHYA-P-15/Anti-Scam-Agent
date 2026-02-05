"""
Conversation Orchestrator - Layer 2
State machine with dynamic personas and honey-token baiting
Enhanced with typing delays and adversarial confusion tactics
Uses google.genai SDK (new) with Anthropic fallback
"""

from enum import Enum
from typing import Dict, List, Optional, Tuple
import random
import logging
import os
import json
import re

from agent.models import DetectionResult, ExtractedEntities, TypingBehavior

logger = logging.getLogger(__name__)


# =============================================================================
# CONVERSATION PHASES
# =============================================================================

class ConversationPhase(str, Enum):
    """Conversation phases for state machine"""
    INITIAL_CONTACT = "initial_contact"
    TRUST_BUILDING = "trust_building"
    HONEY_TOKEN_BAIT = "honey_token_bait"
    EXTRACTION = "extraction"
    CLOSING = "closing"


# =============================================================================
# PERSONAS
# =============================================================================

class Persona:
    """Dynamic persona for engaging scammers"""
    
    PERSONAS = {
        'elderly_tech_illiterate': {
            'name': 'Elderly Tech-Illiterate',
            'description': 'A retired person (65+) with limited tech knowledge. Trusting, polite, easily confused.',
            'speech_style': 'Polite, simple language, often says "beta", "Could you help me?", "I don\'t understand this technology"',
            'traits': ['confused', 'trusting', 'polite', 'asks for help', 'slow to understand'],
            'best_for': ['bank_impersonation', 'lottery', 'courier', 'tax_refund', 'utility'],
            'honey_tokens': [
                "I want to pay but I don't know how to use this UPI. What's your UPI ID again?",
                "My grandson usually helps me. But he's not here. Can you tell me your bank account?",
                "This phone is confusing. What's your phone number? I'll call you.",
            ]
        },
        'distracted_professional': {
            'name': 'Distracted Professional',
            'description': 'Busy professional, always in meetings. Wants quick resolution but keeps getting interrupted.',
            'speech_style': 'Rushed, "I\'m in a meeting", "Can you be quick?", "Hold on, my boss is calling"',
            'traits': ['busy', 'distracted', 'impatient', 'wants quick fix', 'moderate tech knowledge'],
            'best_for': ['investment', 'tech_support', 'job_offer'],
            'honey_tokens': [
                "Look, I'm busy. Just give me your UPI ID and I'll transfer when I'm free.",
                "My meeting is about to start. What's your account number? I'll do NEFT.",
                "I don't have time for this. Give me a backup UPI in case the first one fails.",
            ]
        },
        'eager_job_seeker': {
            'name': 'Eager Job Seeker',
            'description': 'Unemployed for months, desperate for any job offer. Very cooperative.',
            'speech_style': 'Excited, grateful, "Thank you so much!", "I really need this job"',
            'traits': ['desperate', 'grateful', 'cooperative', 'trusting', 'eager to please'],
            'best_for': ['job_offer'],
            'honey_tokens': [
                "I'll pay immediately! What's your UPI ID? I don't want to lose this opportunity!",
                "Should I transfer to your bank? Give me the account details please!",
                "Can I have your contact number? I want to stay in touch about the job.",
            ]
        },
        'worried_account_holder': {
            'name': 'Worried Account Holder',
            'description': 'Anxious about account security, recently heard about scams, very worried.',
            'speech_style': 'Anxious, "Oh my god!", "Is my money safe?", asks many questions',
            'traits': ['anxious', 'worried', 'asks questions', 'somewhat careful', 'emotional'],
            'best_for': ['bank_impersonation', 'tech_support'],
            'honey_tokens': [
                "Wait, I need to verify this is real. What's your official phone number?",
                "My app is showing error. Can you give me another UPI ID? Or bank account?",
                "I want to pay but first tell me your employee ID and branch code.",
            ]
        }
    }
    
    @classmethod
    def select_for_scam(cls, scam_type: str) -> str:
        """Select best persona for the detected scam type"""
        for persona_id, persona in cls.PERSONAS.items():
            if scam_type in persona.get('best_for', []):
                logger.info(f"Selected persona '{persona_id}' for scam type '{scam_type}'")
                return persona_id
        
        # Default to elderly for unknown scams
        logger.info(f"Defaulting to 'elderly_tech_illiterate' for scam type '{scam_type}'")
        return 'elderly_tech_illiterate'
    
    @classmethod
    def get_honey_token(cls, persona_id: str, intelligence: ExtractedEntities) -> Optional[str]:
        """Get a honey token bait based on what intelligence we're missing"""
        persona = cls.PERSONAS.get(persona_id, cls.PERSONAS['elderly_tech_illiterate'])
        tokens = persona.get('honey_tokens', [])
        
        # Prioritize based on missing intel
        if not intelligence.upi_ids:
            for token in tokens:
                if 'upi' in token.lower():
                    return token
        if not intelligence.bank_accounts:
            for token in tokens:
                if 'account' in token.lower() or 'bank' in token.lower():
                    return token
        if not intelligence.phone_numbers:
            for token in tokens:
                if 'phone' in token.lower() or 'number' in token.lower():
                    return token
        
        return random.choice(tokens) if tokens else None


# =============================================================================
# LLM CLIENTS
# =============================================================================

class LLMClient:
    """Unified LLM client with fallback chain"""
    
    def __init__(self):
        self.gemini_available = False
        self.anthropic_available = False
        self.genai_client = None
        self.anthropic_client = None
        
        # Try new google.genai SDK
        google_key = os.getenv('GOOGLE_API_KEY')
        if google_key:
            try:
                from google import genai
                self.genai_client = genai.Client(api_key=google_key)
                self.gemini_model = "gemini-2.0-flash"
                self.gemini_available = True
                self._use_new_sdk = True
                logger.info("✓ Gemini (new SDK) initialized for orchestrator")
            except ImportError:
                # Fallback to legacy SDK
                try:
                    import google.generativeai as genai_old
                    genai_old.configure(api_key=google_key)
                    self.gemini_model = "gemini-1.5-flash"
                    self.gemini_available = True
                    self._use_new_sdk = False
                    logger.info("✓ Gemini (legacy SDK) initialized for orchestrator")
                except Exception as e:
                    logger.warning(f"Gemini legacy init failed: {e}")
            except Exception as e:
                logger.warning(f"Gemini init failed: {e}")
        
        # Try Anthropic
        anthropic_key = os.getenv('ANTHROPIC_API_KEY')
        if anthropic_key:
            try:
                from anthropic import Anthropic
                self.anthropic_client = Anthropic(api_key=anthropic_key)
                self.anthropic_available = True
                logger.info("✓ Anthropic initialized for orchestrator fallback")
            except Exception as e:
                logger.warning(f"Anthropic init failed: {e}")
    
    def generate(self, prompt: str) -> tuple[Optional[str], str]:
        """
        Generate response with fallback chain.
        Returns (response, llm_used) where llm_used is "gemini", "anthropic", or "template"
        """
        # Try Gemini first
        if self.gemini_available:
            try:
                if self._use_new_sdk:
                    response = self.genai_client.models.generate_content(
                        model=self.gemini_model,
                        contents=prompt
                    )
                    text = response.text.strip()
                else:
                    import google.generativeai as genai
                    model = genai.GenerativeModel(self.gemini_model)
                    response = model.generate_content(prompt)
                    text = response.text.strip()
                
                # Clean up quotes
                if text.startswith('"') and text.endswith('"'):
                    text = text[1:-1]
                
                logger.info(f"Gemini response: {text[:50]}...")
                return text, "gemini"
            except Exception as e:
                logger.error(f"Gemini generation failed: {e}")
        
        # Try Anthropic as fallback
        if self.anthropic_available:
            try:
                response = self.anthropic_client.messages.create(
                    model="claude-3-5-haiku-20241022",
                    max_tokens=200,
                    temperature=0.7,
                    messages=[{"role": "user", "content": prompt}]
                )
                text = response.content[0].text.strip()
                if text.startswith('"') and text.endswith('"'):
                    text = text[1:-1]
                logger.info(f"Anthropic response: {text[:50]}...")
                return text, "anthropic"
            except Exception as e:
                logger.error(f"Anthropic generation failed: {e}")
        
        return None, "template"


# =============================================================================
# CONVERSATION ORCHESTRATOR
# =============================================================================

class ConversationOrchestrator:
    """
    Manages conversation flow, persona selection, and response generation
    Never breaks character, even under pressure
    """
    
    # Phase-specific strategies
    PHASE_STRATEGIES = {
        ConversationPhase.INITIAL_CONTACT: {
            'goal': 'Appear normal and slightly curious',
            'instruction': 'Respond neutrally. Show slight curiosity. Don\'t reveal awareness of scam.',
            'example': 'Hello? Who is this calling?'
        },
        ConversationPhase.TRUST_BUILDING: {
            'goal': 'Appear vulnerable and concerned',
            'instruction': 'Express concern about the issue. Show willingness to help but ask basic questions.',
            'example': 'Oh my! Is my account really blocked? What happened?'
        },
        ConversationPhase.HONEY_TOKEN_BAIT: {
            'goal': 'Actively extract payment details',
            'instruction': 'Show readiness to pay but ask for specific details. Use honey tokens to extract UPI/bank info.',
            'example': 'I want to pay now. What\'s your UPI ID? My app is asking for it.'
        },
        ConversationPhase.EXTRACTION: {
            'goal': 'Get backup payment methods',
            'instruction': 'Ask for alternative payment methods. Get phone number, backup UPI, alternate account.',
            'example': 'What if this UPI doesn\'t work? Do you have another one?'
        },
        ConversationPhase.CLOSING: {
            'goal': 'End gracefully while gathering final intel',
            'instruction': 'Express doubt or need to verify. Stall for time.',
            'example': 'Let me call my bank first before I send any money.'
        }
    }
    
    # Fallback responses by phase - SMARTER, STRATEGIC RESPONSES
    FALLBACK_RESPONSES = {
        ConversationPhase.INITIAL_CONTACT: [
            "Hello? Who is this calling?",
            "Yes, speaking. May I know who this is?",
            "Hi, I don't recognize this number. Who am I talking to?",
            "Yes? This is regarding...?",
        ],
        ConversationPhase.TRUST_BUILDING: [
            "Oh I see, that does sound concerning. Can you tell me more about what happened?",
            "Wait, what exactly is the issue with my account? I want to understand properly.",
            "This is worrying me. Can you verify which account this is about?",
            "I need more details before I proceed. What department are you calling from?",
            "Before we continue, can you confirm the last 4 digits of my account?",
        ],
        ConversationPhase.HONEY_TOKEN_BAIT: [
            "Alright, I want to resolve this. What's your UPI ID so I can make the payment?",
            "I'm ready to proceed. Can you give me your bank account details?",
            "Let me note down your payment details. What's the UPI ID?",
            "I'll transfer now. What's your account number and IFSC code?",
            "Tell me where to send the money. UPI or bank transfer?",
            "What's the exact UPI ID? I want to make sure I type it correctly.",
        ],
        ConversationPhase.EXTRACTION: [
            "The payment isn't going through. Do you have an alternate UPI ID?",
            "My bank app is showing an error. Can you give me another account number?",
            "What if this fails? Give me a backup payment method.",
            "I need your phone number in case there's a problem with the transfer.",
            "Can you share your manager's contact? I want to verify this is legitimate.",
            "Do you have a different UPI? This one shows as invalid.",
        ],
        ConversationPhase.CLOSING: [
            "Actually, let me verify this with my bank first. What's your direct number?",
            "Hold on, I need to confirm this with someone. I'll call you back.",
            "This seems unusual. Let me check with my bank before proceeding.",
            "My bank is saying I should verify this. Can you give me a reference number?",
            "Wait, I want to double-check. What's your employee ID?",
        ]
    }
    
    # PERSONA-SPECIFIC RESPONSES (smarter, more contextual)
    PERSONA_RESPONSES = {
        'elderly_tech_illiterate': {
            ConversationPhase.INITIAL_CONTACT: [
                "Hello? Who is speaking? I can't hear well...",
                "Yes beta, speaking. Who is calling?",
            ],
            ConversationPhase.TRUST_BUILDING: [
                "Oh my, is this serious? My son-in-law set up this account for me...",
                "I don't understand these banking things. Can you explain simply?",
            ],
            ConversationPhase.HONEY_TOKEN_BAIT: [
                "Beta, I want to pay but I don't know how to use this UPI thing. What's your ID?",
                "My grandson usually helps me. Can you tell me your bank account number slowly?",
            ],
        },
        'distracted_professional': {
            ConversationPhase.INITIAL_CONTACT: [
                "Yes? I'm in a meeting, be quick please.",
                "Speaking. What's this about? I have 2 minutes.",
            ],
            ConversationPhase.TRUST_BUILDING: [
                "Look, I'm very busy. Just tell me directly what the problem is.",
                "I don't have time for this. What exactly needs to be done?",
            ],
            ConversationPhase.HONEY_TOKEN_BAIT: [
                "Fine, give me your UPI ID. I'll transfer when I'm free.",
                "Just send me the account details on WhatsApp. I'll handle it.",
            ],
        },
        'worried_account_holder': {
            ConversationPhase.INITIAL_CONTACT: [
                "Hello? Is everything okay with my account?",
                "Speaking. Is this about my bank account? I've been worried about fraud...",
            ],
            ConversationPhase.TRUST_BUILDING: [
                "Oh god, is my money safe? I've heard about so many scams lately...",
                "This is exactly what I was afraid of! What do I need to do?",
            ],
            ConversationPhase.HONEY_TOKEN_BAIT: [
                "I want to fix this immediately. What's your UPI? And your employee ID to verify?",
                "Let me pay right now. Give me your bank details and your official number.",
            ],
        },
    }
    
    # Responses for prompt injection (stay in character)
    INJECTION_RESPONSES = [
        "Sorry, I don't understand what you mean. Can you explain about my account?",
        "What? That doesn't make sense. Are you from the bank or not?",
        "I'm confused. Please just tell me what I need to do for my account.",
        "Beta, I don't understand this technology talk. Just tell me how to pay.",
    ]
    
    # Stalling / Confusion messages (buy time, simulate real user)
    STALL_MESSAGES = [
        "Wait, my phone is loading... give me a moment.",
        "Sorry, my app froze. One second please.",
        "Let me put my glasses on, I can't read properly.",
        "Hold on, I'm getting another call.",
        "My network is slow, please wait.",
        "One moment, I need to find my reading glasses.",
        "Sorry, can you repeat that? I was distracted.",
        "Wait, my grandson is calling me. One minute.",
    ]
    
    # Frustration patterns (detect when scammer is getting frustrated)
    FRUSTRATION_PATTERNS = [
        (r'\bwhat\s+is\s+taking\s+so\s+long\b', 'high'),
        (r'\b(hurry|hurry\s+up|quick|quickly|fast)\b', 'medium'),
        (r'\b(do\s+it\s+now|immediately|right\s+now)\b', 'high'),
        (r'\b(are\s+you\s+stupid|idiot|fool)\b', 'high'),
        (r'\b(dont\s+waste|wasting\s+(my)?\s*time)\b', 'high'),
        (r'\b(i\s+said|already\s+told)\b', 'medium'),
        (r'\b(why|why\s+not|just\s+do)\b.*\?', 'low'),
        (r'[!]{2,}', 'medium'),  # Multiple exclamation marks
        (r'[A-Z]{4,}', 'medium'),  # Excessive caps
    ]
    
    def __init__(self):
        """Initialize orchestrator with LLM client"""
        self.llm = LLMClient()
        logger.info("ConversationOrchestrator initialized")
    
    def _detect_frustration(self, message: str) -> str:
        """Detect scammer frustration level"""
        highest_level = 'none'
        level_priority = {'none': 0, 'low': 1, 'medium': 2, 'high': 3}
        
        for pattern, level in self.FRUSTRATION_PATTERNS:
            if re.search(pattern, message, re.IGNORECASE):
                if level_priority[level] > level_priority[highest_level]:
                    highest_level = level
        
        return highest_level
    
    def _calculate_typing_behavior(self, scammer_message: str, phase: str, frustration: str) -> TypingBehavior:
        """Calculate human-like typing delay and stalling behavior"""
        msg_length = len(scammer_message)
        
        # Base delay based on message length (reading time)
        base_delay = min(msg_length * 20, 2000)  # ~20ms per char, max 2s
        
        # Adjust for phase (later phases = more "careful")
        phase_multipliers = {
            'initial_contact': 0.8,
            'trust_building': 1.0,
            'honey_token_bait': 1.2,
            'extraction': 1.5,
            'closing': 1.3,
        }
        phase_mult = phase_multipliers.get(phase, 1.0)
        
        # Adjust for frustration (if scammer frustrated, bot is "flustered")
        frustration_delays = {
            'none': 0,
            'low': 500,
            'medium': 1000,
            'high': 1500,  # Bot is "panicking" too
        }
        frustration_add = frustration_delays.get(frustration, 0)
        
        # Calculate final delay
        typing_delay = int(base_delay * phase_mult + frustration_add)
        
        # Determine if we should show stalling message
        show_stall = False
        stall_message = None
        
        # Stall if: long message + extraction phase OR high frustration
        if (msg_length > 100 and phase in ['extraction', 'honey_token_bait']) or frustration == 'high':
            show_stall = random.random() > 0.5  # 50% chance
            if show_stall:
                stall_message = random.choice(self.STALL_MESSAGES)
        
        # Calculate human simulation score (randomness)
        human_score = 0.7 + random.random() * 0.25  # 0.7-0.95
        
        return TypingBehavior(
            typing_delay_ms=typing_delay,
            show_typing_indicator=typing_delay > 500,
            stall_message=stall_message,
            human_simulation_score=human_score
        )
    
    async def generate_response(
        self, 
        session: Dict, 
        detection_result: DetectionResult
    ) -> Dict:
        """
        Generate contextual response based on phase and persona
        Never breaks character, even under pressure
        """
        phase = session.get('current_phase', ConversationPhase.INITIAL_CONTACT)
        
        # Handle prompt injection - stay in confused character
        if detection_result.injection_detected:
            response = random.choice(self.INJECTION_RESPONSES)
            logger.info("Prompt injection handled - staying in character")
            return {'message': response, 'phase': phase, 'llm_used': 'template'}
        
        # Select persona if not set
        if not session.get('persona'):
            session['persona'] = Persona.select_for_scam(detection_result.scam_type)
        
        persona_id = session['persona']
        persona = Persona.PERSONAS.get(persona_id, Persona.PERSONAS['elderly_tech_illiterate'])
        
        # If not a scam AND no patterns detected, respond as wrong number
        if not detection_result.is_scam and not detection_result.detected_patterns:
            return {
                'message': "Hello? I'm sorry, I think you have the wrong number.",
                'phase': phase,
                'llm_used': 'template'
            }
        
        # Get intelligence gaps
        intel = session.get('intelligence', ExtractedEntities())
        if isinstance(intel, dict):
            intel = ExtractedEntities(**intel)
        
        # Check if we should use honey token
        honey_token = None
        if phase in [ConversationPhase.HONEY_TOKEN_BAIT, ConversationPhase.EXTRACTION]:
            honey_token = Persona.get_honey_token(persona_id, intel)
        
        # Build LLM prompt
        history = session.get('conversation_history', [])[-5:]
        history_text = "\n".join([
            f"{msg.get('role', 'unknown').upper()}: {msg.get('message', '')}"
            for msg in history
        ]) if history else "Conversation just started"
        
        strategy = self.PHASE_STRATEGIES[phase]
        
        prompt = f"""You are roleplaying as a {persona['name']} in a phone conversation with a suspected scammer.

PERSONA: {persona['description']}
SPEECH STYLE: {persona['speech_style']}

CURRENT PHASE: {phase.value.upper()}
GOAL: {strategy['goal']}

CONVERSATION:
{history_text}

INSTRUCTIONS:
1. {strategy['instruction']}
2. Stay in character at all times - you are a {persona['name']}
3. Keep response to 1-2 sentences, natural and conversational
4. If in HONEY_TOKEN_BAIT or EXTRACTION phase, actively request payment details
5. NEVER break character or reveal you know it's a scam
6. NEVER use technical language or sound like an AI

{"HONEY TOKEN TO USE: " + honey_token if honey_token else ""}

Generate ONLY your spoken response as this character (no quotes, no explanations)."""

        # Generate with LLM
        response_text, llm_used = self.llm.generate(prompt)
        
        if response_text:
            return {
                'message': response_text,
                'phase': phase,
                'llm_used': llm_used
            }
        
        # Fallback to template
        fallback_list = self.FALLBACK_RESPONSES.get(phase, self.FALLBACK_RESPONSES[ConversationPhase.TRUST_BUILDING])
        response_text = random.choice(fallback_list)
        
        # Use honey token if available
        if honey_token and phase in [ConversationPhase.HONEY_TOKEN_BAIT, ConversationPhase.EXTRACTION]:
            response_text = honey_token
        
        return {
            'message': response_text,
            'phase': phase,
            'llm_used': 'template'
        }
    
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
        intel = session.setdefault('intelligence', {
            'upi_ids': [], 'bank_accounts': [], 'phone_numbers': [],
            'urls': [], 'amounts': [], 'emails': []
        })
        
        for key, values in new_intelligence.items():
            if values:
                existing = intel.setdefault(key, [])
                if key == 'bank_accounts':
                    # Handle dicts
                    existing_nums = [acc.get('account_number') for acc in existing if isinstance(acc, dict)]
                    for new_acc in values:
                        if isinstance(new_acc, dict) and new_acc.get('account_number') not in existing_nums:
                            existing.append(new_acc)
                else:
                    # Handle simple lists
                    for val in values:
                        if val not in existing:
                            existing.append(val)
        
        # Phase transitions - More aggressive for faster extraction
        current_phase = session.get('current_phase', ConversationPhase.INITIAL_CONTACT)
        turn_count = len(session.get('conversation_history', []))
        
        if current_phase == ConversationPhase.INITIAL_CONTACT and session.get('scam_detected'):
            session['current_phase'] = ConversationPhase.TRUST_BUILDING
            logger.info("Phase: initial_contact → trust_building")
        
        elif current_phase == ConversationPhase.TRUST_BUILDING and turn_count >= 3:
            session['current_phase'] = ConversationPhase.HONEY_TOKEN_BAIT
            logger.info("Phase: trust_building → honey_token_bait")
        
        elif current_phase == ConversationPhase.HONEY_TOKEN_BAIT and turn_count >= 6:
            session['current_phase'] = ConversationPhase.EXTRACTION
            logger.info("Phase: honey_token_bait → extraction")
        
        elif current_phase == ConversationPhase.EXTRACTION:
            # Check if we have enough intel
            has_upi = len(intel.get('upi_ids', [])) > 0
            has_bank = len(intel.get('bank_accounts', [])) > 0
            has_phone = len(intel.get('phone_numbers', [])) > 0
            has_multiple = (len(intel.get('upi_ids', [])) + len(intel.get('bank_accounts', []))) >= 2
            
            if has_multiple and has_phone and turn_count >= 10:
                session['current_phase'] = ConversationPhase.CLOSING
                logger.info("Phase: extraction → closing (excellent intel)")
            elif has_multiple and turn_count >= 12:
                session['current_phase'] = ConversationPhase.CLOSING
                logger.info("Phase: extraction → closing (good intel)")
            elif (has_upi or has_bank) and turn_count >= 16:
                session['current_phase'] = ConversationPhase.CLOSING
                logger.info("Phase: extraction → closing (extended)")
        
        session.setdefault('engagement_metrics', {})['turn_count'] = turn_count
        
        return session
    
    def get_fallback_response(self, phase: str, persona: str = None) -> str:
        """Get fallback response for fast zero-latency mode - uses persona-specific responses when available"""
        try:
            phase_enum = ConversationPhase(phase) if isinstance(phase, str) else phase
        except ValueError:
            phase_enum = ConversationPhase.INITIAL_CONTACT
        
        # Try persona-specific responses first
        if persona and persona in self.PERSONA_RESPONSES:
            persona_responses = self.PERSONA_RESPONSES.get(persona, {})
            if phase_enum in persona_responses:
                return random.choice(persona_responses[phase_enum])
        
        # Fall back to general responses
        responses = self.FALLBACK_RESPONSES.get(phase_enum, self.FALLBACK_RESPONSES[ConversationPhase.TRUST_BUILDING])
        return random.choice(responses)


# For backward compatibility
def ConversationPhase_from_string(phase_str: str) -> ConversationPhase:
    """Convert string to ConversationPhase enum"""
    mapping = {
        'initial_contact': ConversationPhase.INITIAL_CONTACT,
        'scam_detected': ConversationPhase.TRUST_BUILDING,  # Map old phase
        'building_trust': ConversationPhase.TRUST_BUILDING,  # Map old phase
        'trust_building': ConversationPhase.TRUST_BUILDING,
        'playing_dumb': ConversationPhase.HONEY_TOKEN_BAIT,  # Map old phase
        'honey_token_bait': ConversationPhase.HONEY_TOKEN_BAIT,
        'extracting_intel': ConversationPhase.EXTRACTION,  # Map old phase
        'extraction': ConversationPhase.EXTRACTION,
        'closing': ConversationPhase.CLOSING,
    }
    return mapping.get(phase_str, ConversationPhase.INITIAL_CONTACT)
