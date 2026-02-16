# HVAC AI Receptionist v5.0

**AI-powered receptionist + smart dispatch + inventory + emergency triage + EPA compliance**

One product that closes 5 interconnected pain points for small HVAC businesses.

## Quick Start (3 minutes)

```bash
# 1. Copy files to your VPS
scp -r hvac-ai-v5/ user@your-vps:~/

# 2. SSH into VPS and test core logic (no setup needed!)
ssh user@your-vps && cd hvac-ai-v5
python3 hvac_impl.py --quick       # 3 smoke tests
python3 hvac_impl.py --chat        # Interactive AI chat

# 3. Run production test suite (135 tests)
python3 hvac_test_full.py

# 4. Start full server (Docker)
chmod +x setup.sh && ./setup.sh

# 5. Open browser: http://your-vps:8000/demo
```

## What It Does

| Feature | Pain Solved | Value |
|---------|-------------|-------|
| AI Receptionist | Missed calls ($180-350 each) | 24/7 call capture |
| Emergency Triage | Gas leaks, no heat/AC → instant priority | Safety + liability |
| Smart Dispatch | Wasted drive time (30-40% reduction) | Route optimization |
| Inventory Tracking | "Part not on truck" callbacks | Parts always available |
| EPA Compliance | $37K fine risk | Automatic tracking |
| Safety Guards | AI giving bad advice | 5-layer prevention |
| Auth + Security | Multi-tenant, rate limiting | JWT + PBKDF2 |

## Testing

```bash
# Zero-dependency CLI (just Python 3.9+)
python3 hvac_impl.py --quick       # Smoke tests
python3 hvac_impl.py --emergency   # Emergency triage demo
python3 hvac_impl.py --chat        # Interactive conversation
python3 hvac_impl.py               # All 8 demo modes

# Full production suite (135 tests, 9 modules)
python3 hvac_test_full.py
python3 hvac_test_full.py --module auth
python3 hvac_test_full.py --verbose

# Server tests (after Docker setup)
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"text": "My furnace stopped and its 45 degrees"}'
```

## Files Overview

| File | Purpose |
|------|---------|
| `hvac_main.py` | FastAPI server (all endpoints + auth) |
| `hvac_impl.py` | Self-contained CLI (zero deps, 8 demo modes) |
| `hvac_auth.py` | JWT auth, rate limiting, password hashing, security |
| `hvac_routing.py` | Route optimization engine |
| `hvac_inventory.py` | Inventory + EPA compliance |
| `hvac_schema.sql` | PostgreSQL schema |
| `hvac_test_full.py` | Production test suite (135 tests) |
| `hvac_test.py` | pytest suite (60+ tests) |
| `STRATEGIC_ANALYSIS_v5.md` | Business strategy + competitive analysis |
| `VPS_GUIDE.md` | Non-programmer deployment guide |

## Going to Production

```bash
nano .env
# MOCK_MODE=0, GEMINI_API_KEY=..., TELNYX_API_KEY=..., JWT_SECRET=...
docker compose down && docker compose up -d --build
```

## Client Pricing

| Plan | Price | ROI |
|------|-------|-----|
| Starter | $99/mo | 3,500% |
| Pro | $199/mo | 2,000% |
| Enterprise | $399/mo | 1,000% |
