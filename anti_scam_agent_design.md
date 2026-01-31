# Anti-Scam Honeypot Agent - System Design Document

## Executive Summary
This system implements a sophisticated conversational agent designed to detect, engage, and extract intelligence from scam attempts through a dual-layer architecture combining fast detection with adaptive persona-based engagement.

---

## 1. System Architecture

### 1.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    API Gateway (FastAPI)                     │
└──────────────────┬──────────────────────────────────────────┘
                   │
    ┏━━━━━━━━━━━━━┻━━━━━━━━━━━━━┓
    ┃                            ┃
┌───▼────────────────┐  ┌────────▼──────────────┐
│  Layer 1:          │  │  Session Manager      │
│  Detection Engine  │  │  (Redis/SQL)          │
└───┬────────────────┘  └────────┬──────────────┘
    │                             │
┌───▼─────────────────────────────▼──────────────┐
│  Layer 2: Orchestrator (State Machine)         │
│  - Phase Management                            │
│  - Persona Selection                           │
│  - Strategy Adaptation                         │
└───┬────────────────────────────────────────────┘
    │
┌───▼────────────────────────────────────────────┐
│  Layer 3: Intelligence Extractor               │
│  - Parallel Processing                         │
│  - Multi-Format Parsing                        │
│  - Data Validation                             │
└────────────────────────────────────────────────┘
```

### 1.2 Component Breakdown

#### **Layer 1: Detection Engine**
**Purpose:** Fast binary classification of incoming messages

**Implementation Options:**
1. **Hybrid Approach (Recommended):**
   - **Rule-Based Classifier (50ms latency):**
     - Keyword blacklist: "KYC", "verify account", "lottery", "prize", "tax refund", "courier blocked", "FedEx", "customs clearance"
     - Pattern matching: Phone numbers, UPI IDs, suspicious URLs
     - Urgency indicators: "immediately", "within 24 hours", "account will be blocked"
   
   - **LLM Classifier (200-500ms latency):**
     - Use GPT-4o-mini or Claude 3.5 Haiku
     - Prompt template:
       ```
       Classify if this message is a scam attempt. Consider:
       - Impersonation (bank, government, courier)
       - Urgency tactics
       - Request for sensitive information
       - Romance/investment schemes (pig butchering)
       
       Message: "{message}"
       
       Respond with JSON: {"is_scam": true/false, "scam_type": "type", "confidence": 0-1}
       ```

**Output:**
```json
{
  "is_scam": true,
  "scam_type": "bank_impersonation",
  "confidence": 0.95,
  "detected_patterns": ["urgent_action", "kyc_update", "account_block_threat"]
}
```

---

#### **Layer 2: Orchestrator (State Machine)**

**State Phases:**

```python
class ConversationPhase(Enum):
    INITIAL_CONTACT = "initial_contact"
    SCAM_DETECTED = "scam_detected"
    BUILDING_TRUST = "building_trust"
    PLAYING_DUMB = "playing_dumb"
    EXTRACTING_INTEL = "extracting_intel"
    CLOSING = "closing"
```

**Phase Transitions:**

```
INITIAL_CONTACT → [Scam Detected] → SCAM_DETECTED
                ↓
         BUILDING_TRUST (2-3 turns)
                ↓
         PLAYING_DUMB (Ask clarifying questions)
                ↓
         EXTRACTING_INTEL (Elicit payment details)
                ↓
         CLOSING (After intelligence gathered or engagement drops)
```

**Phase-Specific Strategies:**

| Phase | Goal | Agent Behavior | Example Response |
|-------|------|----------------|------------------|
| **INITIAL_CONTACT** | Appear normal | Neutral, slightly curious | "Hello, who is this?" |
| **BUILDING_TRUST** | Appear vulnerable | Show concern, ask basic questions | "Oh no, is my account really blocked? What do I need to do?" |
| **PLAYING_DUMB** | Increase friction | Ask for clarification, express confusion | "I'm not very good with technology. Can you explain this step by step?" |
| **EXTRACTING_INTEL** | Get payment details | Show readiness but need details | "I'm ready to pay. What's the UPI ID again? My app is asking for it." |
| **CLOSING** | End gracefully | Stall or express doubt | "Let me call my bank first to be sure." |

---

## 2. Persona Engineering

### 2.1 High-Value Personas

**Persona 1: Retired Professional (65+)**
- **Characteristics:** Has savings, not tech-savvy, trusting
- **Speech patterns:** Polite, uses simple language, asks for help
- **Example:** "I'm retired and not very good with these apps. Can you help me understand what I need to do?"

**Persona 2: Small Business Owner**
- **Characteristics:** Busy, distracted, concerned about business accounts
- **Speech patterns:** Rushed, willing to comply quickly
- **Example:** "I'm in a meeting but this sounds urgent. Just tell me quickly what I need to do."

**Persona 3: Young Professional (Anxious Type)**
- **Characteristics:** Worried about account issues, some technical knowledge but gullible
- **Speech patterns:** Anxious, asks many questions
- **Example:** "Wait, my account is really blocked? I just got paid! What exactly happened?"

### 2.2 Adaptive Tone Matching

**Scammer Tone → Agent Response:**
- **Urgent/Aggressive:** "Oh my! This sounds serious. I'm trying to understand..."
- **Friendly/Patient:** "Thank you for helping me with this. I really appreciate it."
- **Technical:** "I'm not very familiar with these technical terms. Could you explain in simpler words?"

### 2.3 Strategic Friction Techniques

1. **Clarification Loop:**
   - "Is this the official bank link? My nephew told me to be careful."
   - "I see several SMS from different numbers. Which one should I trust?"

2. **Technical Difficulties:**
   - "The link isn't opening on my phone. Can you send it again?"
   - "My app is showing an error. Do you have another way?"

3. **Verification Questions:**
   - "Can you tell me my last transaction so I know this is really my bank?"
   - "What's your employee ID? I want to report that you helped me."

4. **Backup Request:**
   - "What if the UPI doesn't work? Do you have a bank account number?"
   - "My UPI limit is low. Can I do a bank transfer instead?"

---

## 3. Intelligence Extraction Strategy

### 3.1 Extraction Goals (Priority Order)

1. **Primary Intelligence:**
   - UPI IDs (name@bank)
   - Bank account numbers + IFSC codes
   - Phone numbers
   - Phishing URLs

2. **Secondary Intelligence:**
   - Scammer names/aliases
   - Organization names claimed
   - Script patterns
   - Geographic indicators

### 3.2 Extraction Tactics by Phase

**Phase: Building Trust (Turns 1-3)**
- Goal: Don't push yet, just appear cooperative
- Extract: Basic scam type, claimed identity

**Phase: Playing Dumb (Turns 4-6)**
- Goal: Force scammer to repeat/clarify details
- Extract: URLs, phone numbers
- Technique: "I didn't quite catch that. Can you send it again?"

**Phase: Extracting Intel (Turns 7+)**
- Goal: Direct extraction of payment details
- Key Trigger Phrases:
  - "Okay, I'm ready to pay. Where do I send the money?"
  - "My app is asking for the UPI ID. Can you type it exactly?"
  - "The first link failed. Do you have a backup account?"
  - "My bank needs the IFSC code too. What is it?"

### 3.3 Multi-Format Parsing

**Regex Patterns:**

```python
PATTERNS = {
    'upi_id': r'\b[a-zA-Z0-9._-]+@[a-zA-Z]{3,}\b',
    'phone': r'\b(?:\+91|0)?[6-9]\d{9}\b',
    'bank_account': r'\b\d{9,18}\b',
    'ifsc': r'\b[A-Z]{4}0[A-Z0-9]{6}\b',
    'url': r'https?://[^\s]+',
    'amount': r'(?:Rs\.?|₹)\s*\d+(?:,\d+)*(?:\.\d{2})?'
}
```

**LLM NER Extraction:**

```python
extraction_prompt = f"""
Extract financial/contact information from this message:

Message: "{message}"

Return JSON with:
{{
  "upi_ids": [],
  "bank_accounts": [{{"account_number": "", "ifsc": "", "bank_name": ""}}],
  "phone_numbers": [],
  "urls": [],
  "amounts_mentioned": [],
  "scammer_identity": ""
}}
"""
```

### 3.4 Validation & Enrichment

```python
def validate_intelligence(extracted_data):
    """
    Validate and enrich extracted data
    """
    validated = {}
    
    # Validate UPI format
    for upi in extracted_data.get('upi_ids', []):
        if '@' in upi and len(upi.split('@')[1]) >= 3:
            validated.setdefault('upi_ids', []).append(upi)
    
    # Validate IFSC format
    for account in extracted_data.get('bank_accounts', []):
        if re.match(r'^[A-Z]{4}0[A-Z0-9]{6}$', account.get('ifsc', '')):
            validated.setdefault('bank_accounts', []).append(account)
    
    # Check URL reputation (optional: integrate with URLhaus API)
    for url in extracted_data.get('urls', []):
        validated.setdefault('urls', []).append({
            'url': url,
            'status': check_url_reputation(url)
        })
    
    return validated
```

---

## 4. Technical Implementation

### 4.1 Tech Stack

```yaml
Core:
  Language: Python 3.11+
  Framework: FastAPI 0.104+
  
LLM:
  Primary: Claude 3.5 Haiku (fast, cheap)
  Fallback: GPT-4o-mini
  Orchestration: LangGraph 0.0.50+
  
Storage:
  Session Memory: Redis 7.0+ (sub-millisecond read/write)
  Persistent Storage: PostgreSQL 15+ (conversation logs, analytics)
  
Parsing:
  Regex: Python re module
  NER: spaCy 3.7+ or LLM-based extraction
  
Deployment:
  Platform: AWS Lambda (burst traffic) or DigitalOcean App Platform
  Container: Docker
  API Gateway: AWS API Gateway / Nginx
```

### 4.2 Database Schema

**Redis (Session Memory):**
```python
# Key structure: session:{session_id}
{
    "session_id": "uuid",
    "conversation_history": [
        {"role": "scammer", "message": "...", "timestamp": "..."},
        {"role": "agent", "message": "...", "timestamp": "..."}
    ],
    "current_phase": "extracting_intel",
    "persona": "retired_professional",
    "intelligence": {
        "upi_ids": ["scammer@paytm"],
        "bank_accounts": [],
        "urls": ["http://fake-bank.com"],
        "confidence_scores": {"upi_ids": 0.95}
    },
    "scam_metadata": {
        "scam_type": "bank_impersonation",
        "detected_at": "timestamp",
        "confidence": 0.95
    },
    "engagement_metrics": {
        "turn_count": 8,
        "start_time": "timestamp",
        "last_interaction": "timestamp"
    }
}
```

**PostgreSQL (Analytics):**
```sql
CREATE TABLE conversations (
    id UUID PRIMARY KEY,
    session_id VARCHAR(255) UNIQUE,
    scam_type VARCHAR(100),
    detection_confidence FLOAT,
    persona_used VARCHAR(100),
    total_turns INT,
    duration_seconds INT,
    intelligence_extracted JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE extracted_intelligence (
    id SERIAL PRIMARY KEY,
    conversation_id UUID REFERENCES conversations(id),
    intelligence_type VARCHAR(50), -- 'upi', 'bank_account', 'url', 'phone'
    value TEXT,
    confidence FLOAT,
    extracted_at TIMESTAMP DEFAULT NOW()
);
```

### 4.3 API Implementation

**FastAPI Endpoint:**

```python
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
import asyncio

app = FastAPI()

class MessageEvent(BaseModel):
    session_id: str
    message: str
    timestamp: str

class AgentResponse(BaseModel):
    session_id: str
    agent_message: str
    detected: bool
    intelligence: dict
    metadata: dict

@app.post("/message-event", response_model=AgentResponse)
async def handle_message(
    event: MessageEvent,
    background_tasks: BackgroundTasks
):
    """
    Main API endpoint - processes incoming scammer messages
    """
    
    # 1. Load session context (async)
    session = await load_session(event.session_id)
    
    # 2. Run detection (if not already detected)
    if not session.get('scam_detected'):
        detection_result = await detect_scam(event.message, session)
    else:
        detection_result = session['scam_metadata']
    
    # 3. Update conversation history
    session['conversation_history'].append({
        'role': 'scammer',
        'message': event.message,
        'timestamp': event.timestamp
    })
    
    # 4. Parallel processing: Generate response + Extract intelligence
    response_task = generate_response(session, detection_result)
    extraction_task = extract_intelligence(event.message, session)
    
    agent_response, new_intelligence = await asyncio.gather(
        response_task,
        extraction_task
    )
    
    # 5. Update session state
    session = update_session_state(session, new_intelligence, agent_response)
    
    # 6. Save session (async in background)
    background_tasks.add_task(save_session, session)
    
    # 7. Return response
    return AgentResponse(
        session_id=event.session_id,
        agent_message=agent_response['message'],
        detected=detection_result['is_scam'],
        intelligence=session['intelligence'],
        metadata={
            'phase': session['current_phase'],
            'persona': session['persona'],
            'turn_count': len(session['conversation_history'])
        }
    )
```

**Key Implementation Functions:**

```python
async def detect_scam(message: str, session: dict) -> dict:
    """
    Hybrid detection: Rule-based + LLM
    """
    # Fast rule-based check
    rule_based_score = check_keyword_patterns(message)
    
    if rule_based_score > 0.7:
        return {
            'is_scam': True,
            'scam_type': 'keyword_match',
            'confidence': rule_based_score
        }
    
    # LLM classification for edge cases
    llm_result = await llm_classify_scam(message, session['conversation_history'])
    return llm_result

async def generate_response(session: dict, detection: dict) -> dict:
    """
    Generate contextual response based on phase and persona
    """
    phase = session.get('current_phase', 'initial_contact')
    persona = session.get('persona', 'retired_professional')
    
    # Get phase-specific strategy
    strategy = PHASE_STRATEGIES[phase]
    
    # Build prompt with conversation history + persona + strategy
    prompt = build_response_prompt(
        conversation_history=session['conversation_history'],
        persona=PERSONAS[persona],
        strategy=strategy,
        intelligence_goals=get_intelligence_gaps(session['intelligence'])
    )
    
    # LLM call with fallback
    try:
        response = await llm_generate(prompt, model="claude-3-5-haiku")
    except Exception:
        response = FALLBACK_RESPONSES[phase]
    
    return {
        'message': response,
        'phase': phase
    }

async def extract_intelligence(message: str, session: dict) -> dict:
    """
    Multi-format intelligence extraction
    """
    # Regex extraction (fast)
    regex_data = extract_with_regex(message)
    
    # LLM NER extraction (parallel)
    llm_data = await extract_with_llm(message)
    
    # Merge and validate
    combined = merge_intelligence(regex_data, llm_data)
    validated = validate_intelligence(combined)
    
    return validated

def update_session_state(session: dict, new_intel: dict, response: dict) -> dict:
    """
    State machine: Update phase based on intelligence gathered
    """
    # Add agent response to history
    session['conversation_history'].append({
        'role': 'agent',
        'message': response['message'],
        'timestamp': datetime.now().isoformat()
    })
    
    # Merge new intelligence
    for key, value in new_intel.items():
        session['intelligence'].setdefault(key, []).extend(value)
    
    # Phase transition logic
    current_phase = session['current_phase']
    intel = session['intelligence']
    turn_count = len(session['conversation_history'])
    
    if current_phase == 'initial_contact' and session.get('scam_detected'):
        session['current_phase'] = 'building_trust'
    
    elif current_phase == 'building_trust' and turn_count >= 4:
        session['current_phase'] = 'playing_dumb'
    
    elif current_phase == 'playing_dumb' and turn_count >= 6:
        session['current_phase'] = 'extracting_intel'
    
    elif current_phase == 'extracting_intel':
        # Check if we have sufficient intelligence
        has_upi = len(intel.get('upi_ids', [])) > 0
        has_bank = len(intel.get('bank_accounts', [])) > 0
        
        if (has_upi or has_bank) and turn_count >= 10:
            session['current_phase'] = 'closing'
    
    return session
```

### 4.4 LangGraph State Machine Implementation

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class AgentState(TypedDict):
    session_id: str
    messages: List[dict]
    phase: str
    persona: str
    intelligence: dict
    scam_detected: bool

def create_agent_workflow():
    workflow = StateGraph(AgentState)
    
    # Nodes
    workflow.add_node("detect", detect_node)
    workflow.add_node("build_trust", build_trust_node)
    workflow.add_node("play_dumb", play_dumb_node)
    workflow.add_node("extract", extract_node)
    workflow.add_node("close", close_node)
    
    # Edges (transitions)
    workflow.set_entry_point("detect")
    
    workflow.add_conditional_edges(
        "detect",
        should_engage,
        {
            True: "build_trust",
            False: END
        }
    )
    
    workflow.add_conditional_edges(
        "build_trust",
        check_phase_transition,
        {
            "continue": "build_trust",
            "next": "play_dumb"
        }
    )
    
    workflow.add_conditional_edges(
        "play_dumb",
        check_phase_transition,
        {
            "continue": "play_dumb",
            "next": "extract"
        }
    )
    
    workflow.add_conditional_edges(
        "extract",
        check_completion,
        {
            "continue": "extract",
            "done": "close"
        }
    )
    
    workflow.add_edge("close", END)
    
    return workflow.compile()
```

---

## 5. Optimization for Competition Metrics

### 5.1 Scam Detection Accuracy (Target: >95%)

**Strategy:**
- Ensemble approach: Rule-based (fast) + LLM (accurate)
- Continuous learning from false positives/negatives
- Multi-signal detection:
  - Keyword presence
  - Urgency language
  - Impersonation patterns
  - Request for sensitive data

**Implementation:**
```python
def calculate_scam_score(message: str, context: dict) -> float:
    """
    Weighted scoring system
    """
    scores = {
        'keywords': check_keywords(message) * 0.3,
        'urgency': detect_urgency(message) * 0.2,
        'impersonation': detect_impersonation(message, context) * 0.3,
        'data_request': detect_sensitive_request(message) * 0.2
    }
    return sum(scores.values())
```

### 5.2 Engagement Duration (Target: >10 turns)

**Key Tactics:**
1. **Never give information immediately** - Always ask 1-2 clarifying questions first
2. **Technical difficulties** - Force scammer to provide alternatives
3. **Progress signals** - Make scammer think they're close: "Okay I'm opening the app now..."
4. **Backup requests** - "What if this doesn't work? Do you have another way?"

**Engagement Extension Framework:**
```python
class EngagementExtender:
    """
    Dynamically generate stalling tactics
    """
    
    TACTICS = {
        'clarification': [
            "Can you explain that again? I didn't quite understand.",
            "Is this really from {claimed_org}? How can I verify?"
        ],
        'technical_issue': [
            "The link isn't working. Can you send another?",
            "My app is showing an error: 'Invalid request'. What should I do?"
        ],
        'cooperation_signal': [
            "Okay I'm ready to do this. Just walk me through it step by step.",
            "I'm opening the app now, give me a second..."
        ],
        'backup_request': [
            "What if the UPI doesn't work? Do you have a bank account?",
            "My daily UPI limit is only ₹5000. Can I send in two parts?"
        ]
    }
    
    def get_tactic(self, phase: str, turn_count: int) -> str:
        """
        Select appropriate tactic based on conversation state
        """
        if turn_count < 5:
            return random.choice(self.TACTICS['clarification'])
        elif turn_count < 8:
            return random.choice(self.TACTICS['technical_issue'])
        else:
            return random.choice(self.TACTICS['backup_request'])
```

### 5.3 Intelligence Quality (Target: High-confidence data)

**Multi-pass Extraction:**
```python
async def extract_with_confidence(message: str) -> dict:
    """
    Extract with confidence scoring
    """
    # Pass 1: Regex (high precision)
    regex_data = extract_with_regex(message)
    
    # Pass 2: LLM extraction
    llm_data = await extract_with_llm(message)
    
    # Pass 3: Validation
    validated = {}
    for key in regex_data:
        if key in llm_data and regex_data[key] == llm_data[key]:
            validated[key] = {
                'value': regex_data[key],
                'confidence': 0.95  # Both methods agree
            }
        elif key in regex_data:
            validated[key] = {
                'value': regex_data[key],
                'confidence': 0.75  # Regex only
            }
    
    return validated
```

### 5.4 Response Latency (Target: <2 seconds)

**Optimization Strategies:**

1. **Model Selection:**
   - Use Claude 3.5 Haiku (~200-400ms) for responses
   - Use regex first, LLM only if needed

2. **Async Processing:**
```python
async def parallel_processing(message, session):
    """
    Run response generation and extraction in parallel
    """
    tasks = [
        generate_response(session),
        extract_intelligence(message),
        update_analytics(session)  # Don't wait for this
    ]
    
    response, intelligence, _ = await asyncio.gather(*tasks)
    return response, intelligence
```

3. **Caching:**
```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def get_persona_prompt(persona_name: str) -> str:
    """
    Cache persona prompts
    """
    return PERSONAS[persona_name]['system_prompt']
```

4. **Response Templates:**
```python
# For common scenarios, use templates with variable substitution
QUICK_RESPONSES = {
    'link_not_working': "The link you sent isn't opening. Can you send it again or provide another way?",
    'upi_request': "My app is asking for the UPI ID. Can you type it exactly as I should enter it?",
    'confusion': "I'm a bit confused. Can you explain this more simply?"
}
```

### 5.5 System Stability

**Error Handling:**
```python
class RobustAgent:
    def __init__(self):
        self.fallback_responses = FALLBACK_RESPONSES
        self.max_retries = 3
    
    async def generate_with_fallback(self, prompt: str) -> str:
        """
        Robust generation with fallback
        """
        for attempt in range(self.max_retries):
            try:
                return await self.llm_generate(prompt, timeout=2.0)
            except Exception as e:
                logger.warning(f"LLM call failed (attempt {attempt}): {e}")
                
                if attempt == self.max_retries - 1:
                    # Final fallback: Use phase-appropriate template
                    return self.fallback_responses[self.current_phase]
                
                await asyncio.sleep(0.1 * (attempt + 1))  # Exponential backoff
```

**Health Monitoring:**
```python
@app.middleware("http")
async def monitor_performance(request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    
    # Log slow requests
    if duration > 2.0:
        logger.warning(f"Slow request: {request.url.path} took {duration:.2f}s")
    
    return response
```

---

## 6. Prompt Engineering

### 6.1 Detection Prompt

```python
DETECTION_PROMPT = """You are a scam detection specialist. Analyze this message and determine if it's a scam attempt.

Consider:
1. Impersonation (bank, government, courier, lottery, romantic interest)
2. Urgency tactics ("immediately", "within 24 hours", "account will be blocked")
3. Request for sensitive information (OTP, password, bank details)
4. Suspicious links or payment requests
5. Unusual grammar or spelling for official communication

Message: "{message}"

Conversation context (if any):
{context}

Respond ONLY with valid JSON:
{{
  "is_scam": true/false,
  "scam_type": "bank_impersonation|lottery|romance|investment|courier|other",
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation"
}}"""
```

### 6.2 Response Generation Prompt

```python
RESPONSE_PROMPT_TEMPLATE = """You are roleplaying as a {persona_name} in a conversation with a suspected scammer.

PERSONA DETAILS:
{persona_description}

CURRENT PHASE: {phase}
PHASE GOAL: {phase_goal}

CONVERSATION HISTORY:
{conversation_history}

INTELLIGENCE GAPS (what we still need):
{intelligence_gaps}

STRATEGIC GUIDELINES:
1. Stay in character - sound like a real {persona_name}
2. {phase_specific_instruction}
3. If appropriate, work toward getting: {priority_intelligence}
4. Use natural language - no overly formal speech
5. Keep responses concise (1-3 sentences unless asking multiple questions)

Generate your next response as the {persona_name}. Be natural and believable."""

# Example phase-specific instructions:
PHASE_INSTRUCTIONS = {
    'building_trust': "Express concern about the issue. Ask basic questions to understand the situation. Show willingness to comply but don't act immediately.",
    'playing_dumb': "Ask for clarification. Express technical difficulties or confusion. Make the scammer explain things step-by-step.",
    'extracting_intel': "Show readiness to comply. Ask for specific payment details (UPI, account number). Request backup methods in case the first option doesn't work."
}
```

### 6.3 Intelligence Extraction Prompt

```python
EXTRACTION_PROMPT = """Extract financial and contact information from this message.

Message: "{message}"

Look for:
- UPI IDs (format: name@bank)
- Bank account numbers (9-18 digits)
- IFSC codes (format: ABCD0123456)
- Phone numbers (10 digits, may include +91 or 0 prefix)
- URLs (especially suspicious ones)
- Amounts mentioned
- Names/aliases used by the sender

Respond ONLY with valid JSON:
{{
  "upi_ids": ["list of UPI IDs found"],
  "bank_accounts": [
    {{"account_number": "...", "ifsc": "...", "bank_name": "..."}}
  ],
  "phone_numbers": ["list of phone numbers"],
  "urls": ["list of URLs"],
  "amounts": ["list of amounts with currency"],
  "sender_identity": "name or alias used"
}}

If nothing found for a category, return empty list. Be precise - only extract actual financial information."""
```

---

## 7. Deployment Architecture

### 7.1 AWS Lambda Deployment

```yaml
# serverless.yml
service: anti-scam-agent

provider:
  name: aws
  runtime: python3.11
  region: us-east-1
  memorySize: 1024
  timeout: 30
  environment:
    REDIS_URL: ${env:REDIS_URL}
    ANTHROPIC_API_KEY: ${env:ANTHROPIC_API_KEY}
    
functions:
  messageHandler:
    handler: handler.handle_message
    events:
      - http:
          path: /message-event
          method: post
          cors: true
    reservedConcurrency: 100  # Handle burst traffic

layers:
  pythonDeps:
    path: layer
    compatibleRuntimes:
      - python3.11
```

### 7.2 Docker Container

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Run FastAPI
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### 7.3 Environment Configuration

```python
# config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # API Keys
    anthropic_api_key: str
    openai_api_key: str = None
    
    # Redis
    redis_url: str = "redis://localhost:6379"
    redis_ttl: int = 3600  # 1 hour
    
    # PostgreSQL
    database_url: str
    
    # LLM Settings
    primary_model: str = "claude-3-5-haiku-20241022"
    fallback_model: str = "gpt-4o-mini"
    max_tokens: int = 500
    temperature: float = 0.7
    
    # Performance
    response_timeout: float = 2.0
    max_conversation_length: int = 50
    
    class Config:
        env_file = ".env"

settings = Settings()
```

---

## 8. Testing Strategy

### 8.1 Unit Tests

```python
import pytest
from agent import detect_scam, extract_intelligence

def test_scam_detection_bank_impersonation():
    message = "Your SBI account will be blocked. Click here immediately: http://fake-sbi.com"
    result = detect_scam(message, {})
    
    assert result['is_scam'] == True
    assert result['scam_type'] == 'bank_impersonation'
    assert result['confidence'] > 0.8

def test_intelligence_extraction_upi():
    message = "Please send payment to scammer@paytm"
    result = extract_intelligence(message, {})
    
    assert 'scammer@paytm' in result['upi_ids']
    assert len(result['upi_ids']) == 1

def test_persona_response_generation():
    session = {
        'phase': 'extracting_intel',
        'persona': 'retired_professional',
        'conversation_history': []
    }
    
    response = generate_response(session, {'is_scam': True})
    
    # Check response is in character
    assert len(response['message']) > 0
    assert response['message'].islower() or any(word in response['message'].lower() 
                                                 for word in ['please', 'help', 'understand'])
```

### 8.2 Integration Tests

```python
@pytest.mark.asyncio
async def test_full_conversation_flow():
    """
    Test complete scam conversation from detection to extraction
    """
    agent = AntiScamAgent()
    
    # Scammer's opening
    response1 = await agent.handle_message("Your account has been blocked due to KYC update.")
    assert response1['detected'] == True
    
    # Phase progression
    response2 = await agent.handle_message("Click this link to update: http://fake-bank.com")
    assert 'fake-bank.com' in response2['intelligence']['urls']
    
    # Intelligence extraction
    response3 = await agent.handle_message("Send ₹500 to verify. My UPI is scammer@paytm")
    assert 'scammer@paytm' in response3['intelligence']['upi_ids']
    
    # Check engagement
    assert agent.get_turn_count() >= 3
```

### 8.3 Performance Tests

```python
import time
import asyncio

async def test_response_latency():
    """
    Ensure responses are generated within 2 seconds
    """
    agent = AntiScamAgent()
    
    start = time.time()
    response = await agent.handle_message("Test message")
    duration = time.time() - start
    
    assert duration < 2.0, f"Response took {duration:.2f}s (target: <2s)"

async def test_concurrent_sessions():
    """
    Test handling multiple sessions concurrently
    """
    agent = AntiScamAgent()
    
    tasks = [
        agent.handle_message("Test", session_id=f"session_{i}")
        for i in range(100)
    ]
    
    start = time.time()
    responses = await asyncio.gather(*tasks)
    duration = time.time() - start
    
    assert len(responses) == 100
    assert duration < 10.0  # 100 requests in <10s
```

---

## 9. Monitoring & Analytics

### 9.1 Key Metrics to Track

```python
class MetricsCollector:
    """
    Track competition-relevant metrics
    """
    
    def __init__(self):
        self.metrics = {
            'detection_accuracy': [],
            'engagement_durations': [],
            'intelligence_quality_scores': [],
            'response_latencies': [],
            'phase_distributions': {},
            'scam_type_counts': {}
        }
    
    def log_conversation(self, conversation: dict):
        """
        Log metrics from completed conversation
        """
        # Detection accuracy
        self.metrics['detection_accuracy'].append({
            'detected': conversation['scam_detected'],
            'confidence': conversation['detection_confidence']
        })
        
        # Engagement duration
        duration = len(conversation['conversation_history'])
        self.metrics['engagement_durations'].append(duration)
        
        # Intelligence quality
        intel_score = self.calculate_intelligence_score(conversation['intelligence'])
        self.metrics['intelligence_quality_scores'].append(intel_score)
        
        # Latency
        avg_latency = sum(m['latency'] for m in conversation['messages']) / len(conversation['messages'])
        self.metrics['response_latencies'].append(avg_latency)
    
    def calculate_intelligence_score(self, intelligence: dict) -> float:
        """
        Score intelligence quality based on completeness and confidence
        """
        score = 0.0
        
        # UPI IDs (40 points)
        if intelligence.get('upi_ids'):
            score += 40 * min(len(intelligence['upi_ids']), 2) / 2
        
        # Bank accounts (40 points)
        if intelligence.get('bank_accounts'):
            for acc in intelligence['bank_accounts']:
                if acc.get('account_number') and acc.get('ifsc'):
                    score += 40
                    break
        
        # URLs (20 points)
        if intelligence.get('urls'):
            score += 20
        
        return min(score, 100.0)
    
    def get_summary(self) -> dict:
        """
        Get performance summary
        """
        return {
            'avg_detection_accuracy': sum(m['confidence'] for m in self.metrics['detection_accuracy']) / len(self.metrics['detection_accuracy']),
            'avg_engagement_duration': sum(self.metrics['engagement_durations']) / len(self.metrics['engagement_durations']),
            'avg_intelligence_quality': sum(self.metrics['intelligence_quality_scores']) / len(self.metrics['intelligence_quality_scores']),
            'avg_response_latency': sum(self.metrics['response_latencies']) / len(self.metrics['response_latencies']),
            'total_conversations': len(self.metrics['engagement_durations'])
        }
```

### 9.2 Real-time Dashboard

```python
from fastapi import WebSocket

@app.websocket("/ws/metrics")
async def websocket_metrics(websocket: WebSocket):
    """
    Real-time metrics dashboard
    """
    await websocket.accept()
    
    while True:
        metrics = metrics_collector.get_summary()
        await websocket.send_json(metrics)
        await asyncio.sleep(5)  # Update every 5 seconds
```

---

## 10. Winning Edge: Advanced Tactics

### 10.1 Conversation Steering

```python
class ConversationSteerer:
    """
    Actively steer conversation toward intelligence extraction
    """
    
    def get_steering_response(self, intelligence_gaps: dict, phase: str) -> str:
        """
        Generate response that guides scammer toward providing missing info
        """
        
        if not intelligence_gaps.get('upi_ids') and phase == 'extracting_intel':
            return random.choice([
                "I'm ready to send the payment. What's your UPI ID?",
                "My app is asking for a UPI ID to complete the payment. Can you provide it?",
                "Should I use UPI or bank transfer? If UPI, what's your ID?"
            ])
        
        elif not intelligence_gaps.get('bank_accounts'):
            return random.choice([
                "My UPI has a daily limit. Can I transfer to your bank account instead?",
                "The UPI isn't working. Do you have a bank account I can use?",
                "My bank app needs your account number and IFSC code. What are they?"
            ])
        
        elif not intelligence_gaps.get('urls') and phase == 'playing_dumb':
            return random.choice([
                "Can you send me the link again? I can't find it in my messages.",
                "The link you sent earlier - can you resend it? I want to make sure I have the right one."
            ])
        
        # Default: Express readiness and ask for details
        return "Okay I understand. What exactly do I need to do now?"
```

### 10.2 Adaptive Difficulty

```python
class AdaptiveDifficultyManager:
    """
    Adjust agent difficulty based on scammer persistence
    """
    
    def adjust_persona_based_on_scammer(self, scammer_messages: list) -> str:
        """
        If scammer is getting frustrated, make agent more cooperative
        If scammer is patient, add more friction
        """
        
        # Detect frustration
        frustration_keywords = ['hurry', 'quickly', 'fast', 'now', 'immediately']
        frustration_score = sum(
            any(kw in msg.lower() for kw in frustration_keywords)
            for msg in scammer_messages[-3:]  # Last 3 messages
        )
        
        if frustration_score >= 2:
            # Scammer is frustrated - be more cooperative
            return 'cooperative_victim'
        else:
            # Scammer is patient - add friction
            return 'confused_victim'
```

### 10.3 Multi-Language Support (Bonus)

```python
async def detect_language_and_respond(message: str, session: dict) -> str:
    """
    Detect message language and respond accordingly
    """
    # Common Indian languages used in scams
    LANGUAGE_PATTERNS = {
        'hindi': ['aapka', 'khata', 'band', 'hoga', 'turant'],
        'tamil': ['ungal', 'kaṇakku', 'muṭakkum'],
        'telugu': ['mī', 'khātā', 'block']
    }
    
    detected_lang = 'english'
    for lang, patterns in LANGUAGE_PATTERNS.items():
        if any(pattern in message.lower() for pattern in patterns):
            detected_lang = lang
            break
    
    if detected_lang != 'english':
        # Respond in detected language
        return await generate_multilingual_response(message, detected_lang, session)
    
    return await generate_response(session, {})
```

---

## 11. Final Checklist

### Pre-Deployment

- [ ] All regex patterns tested with diverse input formats
- [ ] LLM prompts validated for consistent output
- [ ] Redis connection pool configured correctly
- [ ] Database migrations run successfully
- [ ] Error handling covers all edge cases
- [ ] Fallback responses defined for all phases
- [ ] Rate limiting configured on API gateway
- [ ] Monitoring and logging enabled
- [ ] Performance benchmarks met (<2s latency)
- [ ] Security: No API keys in code, using environment variables

### Competition Day

- [ ] Health check endpoint responding
- [ ] Redis cache warmed up with common patterns
- [ ] Database connections pooled and ready
- [ ] Fallback LLM configured in case primary fails
- [ ] Metrics collection enabled
- [ ] Real-time dashboard accessible
- [ ] Team ready to monitor and adjust

---

## 12. Competitive Advantages Summary

| Advantage | How It Beats Competition |
|-----------|-------------------------|
| **Dual-layer Architecture** | Faster detection + better context retention |
| **Strategic Friction** | Longer engagement without seeming robotic |
| **Parallel Processing** | Sub-2s latency while doing complex extraction |
| **Conversation Steering** | Actively guides scammer to reveal intel (not passive) |
| **Adaptive Personas** | Adjusts difficulty based on scammer behavior |
| **Multi-pass Extraction** | Higher confidence intelligence through validation |
| **LangGraph State Machine** | Clean phase transitions, maintainable code |
| **Comprehensive Fallbacks** | Never fails due to LLM errors |

---

## Conclusion

This architecture is designed to **win** by:
1. **Maximizing engagement** through believable personas and strategic friction
2. **Extracting high-quality intelligence** via multi-format parsing and validation
3. **Maintaining stability** with comprehensive error handling and fallbacks
4. **Staying fast** through async processing and smart caching

The key differentiator: **Your agent doesn't just respond—it steers the conversation toward your intelligence goals.**
