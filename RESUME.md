# HVAC AI Receptionist - Resume Instructions

## For Next Session

### Context to Load
Give Claude Code this prompt:

```
Read CHECKPOINT.md and RESUME.md first. This is the HVAC AI Receptionist project.
Continue where we left off. You have full autonomy — edit freely, test obsessively.

Key constraints:
- AI: Claude Haiku 4.5 via AssemblyAI LLM Gateway ONLY
- STT: AssemblyAI Streaming ONLY
- Telephony: Telnyx ONLY
- Payment: Belarus-compatible (research needed)
- Route optimization: Open-source (VROOM currently integrated)
- No middleware (no Zapier/Make/n8n)
- Deploy to Railway.app project "gleaming-flow"

Access:
- RAILWAY_TOKEN=742298ab-45a0-486e-a120-3c863732b0ea
- GitHub: Magnat911/hvac-ai-receptionist
- All API keys in .env.txt (read it)
- GitHub MCP and Brave MCP available
```

### Verify First
1. `git status` — confirm all files committed and pushed
2. `git log --oneline -5` — confirm checkpoint commit exists
3. `python -m pytest hvac_test.py -x -q` — confirm tests pass
4. Read `.env.txt` for all API keys

### Priority Tasks (In Order)

#### 1. Railway Deployment
```bash
# Install Railway CLI
npm install -g @railway/cli
railway login --token 742298ab-45a0-486e-a120-3c863732b0ea
railway link  # Link to "gleaming-flow" project
railway add --plugin redis  # Add Redis service
railway variables set MOCK_MODE=0 ASSEMBLYAI_API_KEY=... (all from .env.txt)
railway up  # Deploy
```

#### 2. Fix Known Test Issue
`hvac_test.py` imports `euclidean_matrix` from `hvac_routing.py` but it was renamed to `build_distance_matrix`. Fix the import.

#### 3. Payment Research
Use Brave MCP to research:
- bePaid (bepaid.by) — Belarus merchant support, card linking, recurring billing
- Alternatives: xMoney, Adyen, 2Checkout, Payeer, Crypto.com Pay
- Key requirement: Card linking for subscription recurring billing

#### 4. Route Optimization Testing
Test with 50 real Dallas-area addresses. Compare VROOM results vs naive ordering.

#### 5. CRM Integration Research
Use Brave MCP + GitHub MCP to compare:
- Housecall Pro API
- Jobber API
- FieldPulse API
Choose one for deep integration.

#### 6. End-to-End Voice Testing
Once deployed to Railway:
- Configure Telnyx webhooks to point to Railway URL
- Make real phone calls
- Test emergency detection end-to-end

### Architecture Decisions Already Made
- **LLM**: Claude Haiku 4.5 via AssemblyAI Gateway (NOT direct Anthropic API)
- **Auth header**: `Authorization: <API_KEY>` (NOT "Bearer")
- **STT**: AssemblyAI Universal Streaming v3 WebSocket
- **TTS**: Inworld AI (Ashley voice, inworld-tts-1.5-max)
- **Route optimizer**: VROOM (Python bindings) with Haversine fallback
- **Payment**: bePaid (Belarus-compatible, pending validation)
- **Emergency triage**: 100% rule-based, zero AI involvement
- **Safety guards**: Pre-generation (prohibited check) + post-generation (response validation)

### Known Issues
1. `hvac_test.py` line 28: `from hvac_routing import euclidean_matrix` — function renamed
2. VROOM Python package (`pyvroom`) needs to be in requirements.txt
3. `hvac_payment.py` uses bePaid but this hasn't been tested with real credentials
4. No Redis configured yet (needed for multi-worker WebSocket support)
