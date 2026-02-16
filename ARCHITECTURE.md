# HVAC AI Receptionist - Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              INGRESS                                        │
│  Phone (Telnyx) │ Web Widget │ API Clients                                  │
└────────┬─────────────┬─────────────┬────────────────────────────────────────┘
         │             │             │
         ▼             ▼             ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         FASTAPI APPLICATION                                 │
│  hvac_main.py (1083 lines)                                                  │
│  ├── Emergency Triage (rule-based, zero hallucination)                      │
│  ├── Safety Guards (5-layer validation)                                     │
│  ├── RAG Knowledge Base (keyword + pgvector)                                │
│  ├── Conversation Engine                                                    │
│  └── Auth (JWT, rate limiting, audit)                                       │
└────────┬────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           VOICE PIPELINE                                    │
│  hvac_voice.py (817 lines)                                                  │
│  ├── AssemblyAI Streaming STT (WebSocket v3, real-time)                     │
│  ├── AssemblyAI LLM Gateway (Claude Haiku 4.5)                              │
│  └── Inworld TTS (Ashley voice, MP3 streaming)                              │
└────────┬────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         TELEPHONY LAYER                                     │
│  hvac_telnyx.py (622 lines)                                                 │
│  ├── Call Control API                                                       │
│  ├── Bidirectional Media Streaming (WebSocket)                              │
│  └── DTMF handling                                                          │
└────────┬────────────────────────────────────────────────────────────────────┘
         │
    ┌────┴────┬────────────┬────────────┐
    ▼         ▼            ▼            ▼
┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
│Routing │ │Inventory│ │Payment│ │ Auth   │
│Engine  │ │Manager  │ │Service│ │Module  │
└────────┘ └────────┘ └────────┘ └────────┘
    │         │            │            │
    └────┬────┴────────────┴────────────┘
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DATA LAYER                                        │
│  ├── PostgreSQL (companies, users, calls, appointments, knowledge)          │
│  ├── Redis (session cache, WebSocket pub-sub)                               │
│  └── Persistent Volumes (recordings, logs)                                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Technology Stack

| Layer | Technology | Why |
|-------|------------|-----|
| **LLM** | Claude Haiku 4.5 via AssemblyAI Gateway | Fast, cost-effective, high quality |
| **STT** | AssemblyAI Universal Streaming v3 | Best accuracy, real-time, <500ms latency |
| **TTS** | Inworld AI (Ashley) | Natural voice, streaming, emotion control |
| **Telephony** | Telnyx Call Control | WebRTC, media streaming, global coverage |
| **Framework** | FastAPI + Uvicorn | Async, high performance, OpenAPI docs |
| **Database** | PostgreSQL + asyncpg | Relational, ACID, pgvector support |
| **Cache** | Redis (aioredis) | Session storage, pub-sub for WebSockets |
| **Routing** | VROOM solver | Open-source, time windows, skills |
| **Payments** | bePaid | Belarus merchant, card linking, recurring |
| **Deployment** | Railway.app | Auto-deploy, managed PostgreSQL/Redis |

## Key Design Decisions

### 1. Emergency Triage: 100% Rule-Based
**Why**: Zero hallucination risk for safety-critical scenarios (gas leaks, CO, fire).
- Regex-based detection runs BEFORE any AI processing
- Critical emergencies (gas/CO/fire) return immediate evacuate + 911 response
- No AI judgment in life-safety decisions

### 2. No Direct Anthropic API
**Why**: AssemblyAI LLM Gateway provides:
- Single API key for STT + LLM
- Lower latency (optimized routing)
- Simpler billing
- Same Claude Haiku 4.5 quality

### 3. 5-Layer Safety Guards
1. **Pre-generation prohibited topics** - Block DIY/refrigerant advice
2. **RAG grounding** - Only quote known pricing/services
3. **System prompt constraints** - Never diagnose, always offer technician
4. **Post-generation validation** - Catch hallucinated technical advice
5. **Confidence scoring** - Fallback to human if unsure

### 4. VROOM for Route Optimization
**Why**: 
- Open-source (no API costs)
- Handles time windows, skills, capacity
- Python bindings available
- Falls back to greedy nearest-neighbor

### 5. bePaid for Belarus Merchants
**Why**:
- Supports Belarus-based merchants
- Accepts international cards (US customers)
- Card tokenization for recurring billing
- No Stripe available in Belarus

## Data Flow

### Incoming Call Flow
```
1. Telnyx receives call → POST /api/telnyx/voice-webhook
2. Server answers → starts bidirectional media streaming
3. Audio chunks → AssemblyAI STT WebSocket
4. Transcript received → Emergency triage (rule-based)
5. If safe → LLM generates response (Claude Haiku)
6. Response → Inworld TTS → MP3 chunks
7. MP3 chunks → Telnyx WebSocket → caller audio
```

### Latency Targets
| Stage | Target | Typical |
|-------|--------|---------|
| STT (streaming) | <500ms | 200-400ms |
| Emergency triage | <10ms | 1-5ms |
| LLM generation | <1000ms | 300-800ms |
| TTS (first chunk) | <500ms | 200-400ms |
| **End-to-end** | **<2000ms** | **1000-1500ms** |

## Security Model

### Authentication
- JWT tokens (HS256)
- Bearer token in Authorization header
- Rate limiting per IP/email

### Data Protection
- No card numbers stored (tokens only)
- Passwords hashed with PBKDF2
- Audit logging for sensitive actions

### API Security
- CORS configured
- Security headers middleware
- Input sanitization
- SQL injection prevention (parameterized queries)

## Scalability

### Horizontal Scaling
- Stateless application servers
- Redis for session sharing
- PostgreSQL connection pooling

### Bottlenecks
- LLM API latency (can't parallelize)
- TTS generation (streaming helps)
- WebSocket connections (Redis pub-sub for multi-worker)

### Cost Optimization
- Mock mode for development (no API calls)
- LLM caching (5-minute TTL)
- VROOM local solver (no external API)
