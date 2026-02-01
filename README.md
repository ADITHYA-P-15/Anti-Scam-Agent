# 🛡️ Anti-Scam Sentinel

**An AI-powered honeypot agent that engages phone/text scammers in realistic conversations to extract their payment credentials for law enforcement and fraud prevention.**

[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-green.svg)](https://fastapi.tiangolo.com/)
[![Gemini](https://img.shields.io/badge/Gemini-2.0_Flash-orange.svg)](https://ai.google.dev/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 📖 Table of Contents

- [Overview](#overview)
- [How It Works](#how-it-works)
- [Key Features](#key-features)
- [Installation](#installation)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [Detection Engine](#detection-engine)
- [Personas](#personas)
- [Intelligence Extraction](#intelligence-extraction)
- [Scammer Profiling](#scammer-profiling)
- [Webhooks](#webhooks)
- [Testing](#testing)
- [Architecture](#architecture)
- [Performance](#performance)
- [Contributing](#contributing)

---

## Overview

Anti-Scam Sentinel is a **conversational AI agent** designed to act as a realistic scam victim. When a scammer initiates contact, the agent:

1. **Detects** the scam within the first 1-2 messages using the Scam-Triad heuristic
2. **Engages** using one of four convincing victim personas (elderly, professional, etc.)
3. **Extracts** payment credentials (UPI IDs, bank accounts, phone numbers)
4. **Profiles** scammers across multiple sessions for pattern analysis
5. **Alerts** stakeholders via webhook notifications

### Why This Matters

Phone scams cost victims billions annually. Traditional approaches (blocking, warnings) are reactive. Anti-Scam Sentinel is **proactive** – it wastes scammers' time and extracts intelligence that can be shared with authorities.

---

## How It Works

```
┌─────────────────────────────────────────────────────────────────────┐
│                        SCAMMER MESSAGE                               │
│  "Your SBI account will be blocked! Update KYC immediately!"        │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│  LAYER 1: DETECTION (Scam-Triad Heuristic)                          │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐   │
│  │ Urgency: 2.0│ │Authority:2.5│ │ Emotion: 1.0│ │Financial:0.0│   │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘   │
│                     Total: 5.5/10 → SCAM DETECTED ✅                 │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│  LAYER 2: PERSONA SELECTION                                          │
│  Selected: "elderly_tech_illiterate" (best match for bank scam)     │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│  LAYER 3: RESPONSE GENERATION                                        │
│  Agent: "Oh dear! What do I need to do? I'm not good with phones."  │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│  LAYER 4: INTELLIGENCE EXTRACTION                                    │
│  Extracted: UPI verify.sbi@paytm (Paytm Payments Bank, verified)    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Key Features

### 🎯 Early Detection
- **Scam-Triad Heuristic**: Scores messages on 4 dimensions (Urgency, Authority, Emotion, Financial)
- **62 Detection Patterns**: Comprehensive regex patterns for 8+ scam types
- **First-Message Detection**: Most scams detected in turn 1

### ⚡ Zero-Latency Response
- **<300ms Response Time**: Heavy LLM processing runs in background
- **Template Fallbacks**: Instant responses while processing
- **Async Architecture**: Non-blocking request handling

### 🏦 UPI Bank Validation
- **60+ Provider Mappings**: `@ybl` → Yes Bank, `@paytm` → Paytm Payments Bank
- **Verification Status**: Confidence scores for each extracted ID
- **Intelligence Completeness**: 0-100 score for intel quality

### 🎭 Dynamic Personas
- **4 Victim Profiles**: Elderly, professional, gullible student, distracted parent
- **Adaptive Behavior**: Persona matches scam type
- **Honey-Token Baiting**: Proactively asks for missing credentials

### 🕵️ Scammer Profiling
- **Cross-Session Tracking**: Links scammers by UPI, phone, bank accounts
- **Risk Scoring**: 0-100 based on session count and identifiers
- **Scam Type Clustering**: Groups by techniques used

### 📡 Webhook Notifications
- **Real-Time Alerts**: Scam detection, intel extraction, high-risk profiles
- **HMAC Signatures**: Secure webhook delivery
- **Retry Logic**: Exponential backoff on failure

---

## Installation

### Prerequisites
- Python 3.12+
- pip
- (Optional) Redis for persistent sessions

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/ADITHYA-P-15/Anti-Scam-Agent.git
cd Anti-Scam-Agent

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your API keys

# 5. Start the server
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Verify Installation

```bash
curl http://localhost:8000/health
# Response: {"status": "ok", ...}
```

---

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```env
# Required: Google Gemini API Key
GOOGLE_API_KEY=your_gemini_api_key_here

# Optional: Anthropic API for fallback
ANTHROPIC_API_KEY=your_anthropic_key_here

# Optional: Redis for persistent sessions
REDIS_URL=redis://localhost:6379

# Optional: Debug mode
DEBUG=false
```

### Getting API Keys

1. **Google Gemini**: Visit [Google AI Studio](https://aistudio.google.com/) → Get API Key
2. **Anthropic**: Visit [Anthropic Console](https://console.anthropic.com/) → Create API Key

---

## API Reference

### Core Endpoints

#### `POST /message` - Process Scammer Message

The main endpoint for handling incoming scammer messages.

**Request:**
```json
{
  "session_id": "unique-session-id",
  "message": "Your account will be blocked!",
  "timestamp": "2026-02-01T10:00:00Z"  // optional
}
```

**Response:**
```json
{
  "session_id": "unique-session-id",
  "is_scam": true,
  "confidence_score": 0.85,
  "extracted_entities": {
    "upi_ids": [
      {
        "upi_id": "scammer@paytm",
        "bank_provider": "Paytm Payments Bank",
        "provider_type": "wallet",
        "verified": true,
        "confidence": 0.95
      }
    ],
    "bank_accounts": [],
    "phone_numbers": ["9876543210"],
    "urls": [],
    "intel_completeness_score": 45.0
  },
  "agent_response": "Hello? Who is this calling?",
  "forensics": {
    "scam_type": "bank_impersonation",
    "threat_level": "high",
    "detected_indicators": ["urgency_cue", "authority_claim", "kyc_mention"],
    "persona_used": "elderly_tech_illiterate",
    "scammer_frustration": "none",
    "intel_quality": "partial"
  },
  "metadata": {
    "phase": "trust_building",
    "turn_count": 3,
    "latency_ms": 142,
    "typing_behavior": {
      "typing_delay_ms": 1500,
      "show_typing_indicator": true,
      "stall_message": "Wait, my phone is slow..."
    },
    "processing_async": true
  }
}
```

---

#### `GET /analytics/{session_id}` - Session Analytics

Get detailed analytics for a conversation session.

**Response:**
```json
{
  "session_id": "test-123",
  "created_at": "2026-02-01T10:00:00Z",
  "total_turns": 14,
  "is_scam": true,
  "scam_type": "bank_impersonation",
  "timeline": [
    {
      "turn": 1,
      "timestamp": "2026-02-01T10:00:00Z",
      "role": "scammer",
      "message_preview": "Your SBI account will be blocked...",
      "indicators": ["urgency_indicator", "authority_claim"],
      "phase": "initial_contact"
    }
  ],
  "intelligence_score": 85.0,
  "scammer_profile_id": "scammer-a1b2c3d4"
}
```

---

#### Webhook Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/webhook/register` | POST | Register a new webhook |
| `/webhook/list` | GET | List all registered webhooks |
| `/webhook/{id}` | DELETE | Unregister a webhook |

**Register Webhook:**
```bash
curl -X POST http://localhost:8000/webhook/register \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://your-server.com/scam-alert",
    "events": ["scam_detected", "intel_extracted"],
    "secret": "your-hmac-secret"
  }'
```

---

#### Profile Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/profile/lookup` | GET | Find profile by UPI/phone/account |
| `/profile/{id}` | GET | Get profile by ID |
| `/profiles` | GET | List all profiles |

**Lookup Example:**
```bash
curl "http://localhost:8000/profile/lookup?upi=scammer@paytm"
```

---

## Detection Engine

### Scam-Triad Heuristic

The detection engine scores messages on four dimensions:

| Dimension | Max Score | Examples |
|-----------|-----------|----------|
| **Urgency** | 3.0 | "immediately", "within 24 hours", "will be blocked" |
| **Authority** | 3.0 | Bank names, KYC, RBI, SEBI, government agencies |
| **Emotion** | 2.0 | "lottery winner", "prize", "blocked", "hacked" |
| **Financial** | 2.0 | UPI handles, bank account numbers, payment requests |

**Detection Formula:**
- Total Score = Urgency + Authority + Emotion + Financial
- Scam Detected = Total Score ≥ 2.5

### Supported Scam Types

| Type | Key Indicators |
|------|----------------|
| `bank_impersonation` | KYC, account blocked, SBI/HDFC/ICICI |
| `lottery` | Prize, winner, lucky draw, jackpot |
| `courier` | FedEx, DHL, parcel, customs clearance |
| `tax_refund` | Income tax, GST refund, IT department |
| `investment` | Guaranteed returns, crypto, SEBI, trading |
| `job_offer` | Offer letter, recruitment, salary |
| `tech_support` | Account hacked, Instagram, security alert |
| `utility` | Electricity bill, power cut, disconnection |

---

## Personas

The agent uses four distinct victim personas:

### 1. Elderly Tech-Illiterate
```
Characteristics: Confused by technology, trusting, slow responses
Triggers: Bank scams, KYC scams
Example: "Oh dear, I don't understand these things. Can you help me step by step?"
```

### 2. Gullible Student
```
Characteristics: Eager to help, easily impressed, asks naive questions
Triggers: Lottery, job offers
Example: "WOW, I won a prize?! This is amazing! What do I need to do?"
```

### 3. Busy Professional
```
Characteristics: Short responses, asks for quick solutions, somewhat skeptical
Triggers: Tech support, account issues
Example: "I'm in a meeting. Just tell me what to do quickly."
```

### 4. Distracted Parent
```
Characteristics: Multi-tasking, frequently apologizes, slow to respond
Triggers: Courier scams, utility scams
Example: "Sorry, my kids are being noisy. Can you repeat that?"
```

---

## Intelligence Extraction

### UPI Bank Mappings (60+ Providers)

| UPI Suffix | Bank/Provider | Type |
|------------|---------------|------|
| `@ybl` | Yes Bank | Bank |
| `@paytm` | Paytm Payments Bank | Wallet |
| `@okaxis` | Axis Bank | Bank |
| `@oksbi` | State Bank of India | Bank |
| `@okicici` | ICICI Bank | Bank |
| `@okhdfcbank` | HDFC Bank | Bank |
| `@gpay`, `@okgoogleplay` | Google Pay | Wallet |
| `@ibl` | ICICI Bank | Bank |
| `@axl` | Axis Bank | Bank |

### Intelligence Completeness Score

| Entity | Points |
|--------|--------|
| UPI IDs | +30 (base) + 5 per verified |
| Bank Accounts | +25 (base) + 5 per IFSC |
| Phone Numbers | +15 |
| URLs | +10 |
| Emails | +5 |
| Amounts | +5 |

---

## Scammer Profiling

Profiles track scammers across multiple sessions:

```json
{
  "profile_id": "scammer-a1b2c3d4",
  "first_seen": "2026-01-15T08:30:00Z",
  "last_seen": "2026-02-01T10:00:00Z",
  "upi_ids": ["scammer@paytm", "fraud@okicici"],
  "phone_numbers": ["9876543210", "8765432109"],
  "bank_accounts": [
    {"account_number": "123456789012", "ifsc": "HDFC0001234"}
  ],
  "scam_types": ["bank_impersonation", "lottery"],
  "total_sessions": 5,
  "risk_score": 75.0
}
```

### Risk Score Calculation

| Factor | Points |
|--------|--------|
| Per session | +10 (max 30) |
| Per UPI ID | +5 (max 20) |
| Per phone number | +5 (max 15) |
| Per bank account | +10 (max 20) |
| Per scam type | +5 (max 15) |

---

## Webhooks

### Event Types

| Event | Trigger | Payload |
|-------|---------|---------|
| `scam_detected` | High-confidence scam identified | Session ID, scam type, confidence |
| `intel_extracted` | Payment credential captured | Entity type, value, verification |
| `high_risk_profile` | Repeat scammer (risk > 50) | Profile ID, risk score, identifiers |

### Webhook Payload

```json
{
  "event_type": "scam_detected",
  "timestamp": "2026-02-01T10:00:00Z",
  "session_id": "test-123",
  "data": {
    "scam_type": "bank_impersonation",
    "confidence": 0.85,
    "threat_level": "high"
  }
}
```

### Security

Webhooks include HMAC-SHA256 signatures:
```
X-Webhook-Signature: <hmac_hex_digest>
```

---

## Testing

### Run Test Suite

```bash
# Activate virtual environment
source venv/bin/activate

# Start server (if not running)
uvicorn main:app &

# Run tests
python test_simulator.py
```

### Expected Output

```
================================================================================
🎯 OVERALL PERFORMANCE SUMMARY
================================================================================
Scenarios tested: 4
Average intelligence score: 100.0/100

📊 Scenario Breakdown:
  bank_impersonation   | Turns: 14 | Score: 100/100 ✅
  lottery_scam         | Turns: 14 | Score: 100/100 ✅
  courier_scam         | Turns: 14 | Score: 100/100 ✅
  investment_scam      | Turns: 14 | Score: 100/100 ✅
================================================================================
```

---

## Architecture

```
anti-scam-agent/
├── main.py                 # FastAPI application (489 lines)
│                           # - 13 API endpoints
│                           # - Rate limiting middleware
│                           # - CORS configuration
│
├── agent/
│   ├── detector.py         # Scam detection engine (440 lines)
│   │                       # - Scam-Triad heuristic
│   │                       # - 62 regex patterns
│   │                       # - Prompt injection protection
│   │
│   ├── orchestrator.py     # Response generation (586 lines)
│   │                       # - 4 persona templates
│   │                       # - Phase management
│   │                       # - Typing delay simulation
│   │
│   ├── extractor.py        # Intelligence extraction (372 lines)
│   │                       # - UPI/bank regex patterns
│   │                       # - Deobfuscation (p-a-y-t-m → paytm)
│   │                       # - LLM-enhanced extraction
│   │
│   ├── models.py           # Pydantic schemas (310 lines)
│   │                       # - Request/response models
│   │                       # - UPI validation
│   │                       # - Computed fields
│   │
│   ├── analytics.py        # Advanced features (380 lines)
│   │                       # - ScammerProfiler
│   │                       # - WebhookManager
│   │                       # - SessionAnalyticsBuilder
│   │
│   ├── session_manager.py  # State management
│   │                       # - Redis (primary)
│   │                       # - In-memory (fallback)
│   │
│   └── metrics.py          # Performance tracking
│
├── test_simulator.py       # Test harness (322 lines)
├── requirements.txt        # Dependencies
└── .env                    # Configuration
```

---

## Performance

| Metric | Value | Notes |
|--------|-------|-------|
| First Response | ~200ms | Template-based |
| Average Latency | 194-427ms | With background processing |
| Detection Accuracy | ~95% | On test scenarios |
| Intel Extraction | 100/100 | All credentials captured |
| Concurrent Sessions | 1000+ | Limited by memory |

### Latency Optimization

1. **Zero-Latency Architecture**: Returns template response immediately
2. **Background Processing**: LLM calls run asynchronously
3. **Session Caching**: In-memory for <10ms lookups
4. **Pattern Compilation**: Regex pre-compiled at startup

---

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Setup

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run linting
ruff check .

# Run type checking
mypy agent/
```

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## Acknowledgments

- Google Gemini for LLM capabilities
- FastAPI for the excellent web framework
- The cybersecurity community for scam pattern research

---

## Contact

For questions or support, please open an issue on GitHub.

**Repository**: [https://github.com/ADITHYA-P-15/Anti-Scam-Agent](https://github.com/ADITHYA-P-15/Anti-Scam-Agent)
