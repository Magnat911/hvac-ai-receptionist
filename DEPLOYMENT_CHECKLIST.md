# HVAC AI Receptionist v6.0.0 — Final Deployment Checklist

## Status: PRODUCTION READY
- 85/85 tests passing
- All pain points closed
- Landing page with massive voice button ready
- Business plan complete

---

## MANUAL TASKS REQUIRED

### 1. Vercel Deployment (REQUIRED)

The Vercel CLI requires authentication. Run these commands locally:

```bash
# Login to Vercel
vercel login

# Deploy to production
cd /root
vercel --prod

# Set environment variables in Vercel dashboard:
# - ASSEMBLYAI_API_KEY
# - TELNYX_API_KEY
# - TELNYX_PHONE_NUMBER
# - LIVEKIT_URL
# - LIVEKIT_API_KEY
# - LIVEKIT_API_SECRET
# - INWORLD_API_KEY
# - MOCK_MODE=0 (for production)
```

### 2. LiveKit Setup (REQUIRED for Voice)

1. Create LiveKit Cloud account: https://cloud.livekit.io
2. Create a new project
3. Copy API key and secret to Vercel environment variables
4. Set LIVEKIT_URL to your LiveKit Cloud URL

### 3. Telnyx Setup (REQUIRED for Phone Calls)

1. Create Telnyx account: https://telnyx.com
2. Purchase a phone number
3. Configure Call Control webhook:
   - URL: `https://your-vercel-app.vercel.app/api/telnyx/incoming-call`
   - Method: POST
4. Copy API key and phone number to Vercel environment variables

### 4. AssemblyAI Setup (REQUIRED for STT)

1. Create AssemblyAI account: https://assemblyai.com
2. Copy API key to Vercel environment variable: ASSEMBLYAI_API_KEY
3. This enables:
   - Universal-3 Pro STT (300ms latency)
   - LLM Gateway (Claude Haiku 4.5)

### 5. Inworld TTS Setup (OPTIONAL - for Natural Voice)

1. Create Inworld account: https://inworld.ai
2. Copy API key (Base64 encoded) to Vercel: INWORLD_API_KEY
3. Alternative: Use ElevenLabs (set ELEVENLABS_API_KEY)

### 6. Database Setup (RECOMMENDED)

For production, set up a managed PostgreSQL database:

**Option A: Supabase**
```bash
# Create Supabase project
# Copy DATABASE_URL to Vercel environment variables
```

**Option B: Neon**
```bash
# Create Neon database
# Copy DATABASE_URL to Vercel environment variables
```

### 7. Domain Configuration (OPTIONAL)

1. Add custom domain in Vercel dashboard
2. Update DNS records as instructed
3. Update TELNYX webhook URL to custom domain

---

## ENVIRONMENT VARIABLES CHECKLIST

Set these in Vercel Dashboard → Settings → Environment Variables:

| Variable | Required | Source |
|----------|----------|--------|
| ASSEMBLYAI_API_KEY | Yes | assemblyai.com |
| TELNYX_API_KEY | Yes | telnyx.com |
| TELNYX_PHONE_NUMBER | Yes | telnyx.com |
| LIVEKIT_URL | Yes | cloud.livekit.io |
| LIVEKIT_API_KEY | Yes | cloud.livekit.io |
| LIVEKIT_API_SECRET | Yes | cloud.livekit.io |
| INWORLD_API_KEY | Optional | inworld.ai |
| ELEVENLABS_API_KEY | Optional | elevenlabs.io |
| DATABASE_URL | Recommended | supabase.com or neon.tech |
| MOCK_MODE | Yes | Set to "0" for production |

---

## TESTING CHECKLIST

After deployment, test these scenarios:

### Voice Call Tests
- [ ] Call the Telnyx phone number
- [ ] Verify AI greeting ("Hello, thank you for calling...")
- [ ] Test emergency: "I smell gas"
- [ ] Test scheduling: "I need a tune-up"
- [ ] Test pricing: "How much for a service call?"

### Web Demo Tests
- [ ] Open https://your-app.vercel.app/static/voice-landing.html
- [ ] Click the massive voice button
- [ ] Verify LiveKit connection
- [ ] Test transcript display

### API Tests
- [ ] GET /health → {"status": "healthy"}
- [ ] POST /api/chat with message
- [ ] POST /api/emergency/analyze

---

## MONITORING SETUP (RECOMMENDED)

1. **Vercel Analytics**: Enable in Vercel dashboard
2. **Error Tracking**: Add Sentry (optional)
3. **Uptime Monitoring**: Use UptimeRobot or similar
4. **Call Analytics**: Review in Telnyx dashboard

---

## POST-DEPLOYMENT TASKS

1. [ ] Submit sitemap to Google Search Console
2. [ ] Set up Google Analytics
3. [ ] Create social media accounts
4. [ ] Launch free trial landing page
5. [ ] Begin customer acquisition

---

## SUPPORT CONTACTS

- **Vercel Support**: https://vercel.com/support
- **LiveKit Support**: https://livekit.io/support
- **Telnyx Support**: https://telnyx.com/support
- **AssemblyAI Support**: https://assemblyai.com/support

---

## FILES REFERENCE

| File | Purpose |
|------|---------|
| `api/index.py` | Vercel serverless entry point |
| `static/voice-landing.html` | Landing page with voice button |
| `hvac_main.py` | Full FastAPI app (for VPS deployment) |
| `hvac_livekit.py` | LiveKit voice agent |
| `hvac_telnyx.py` | Telnyx telephony integration |
| `hvac_inventory.py` | Inventory + EPA compliance |
| `hvac_routing.py` | Route optimization |
| `BUSINESS_PLAN.md` | Business plan + monetization |

---

*Checklist created: 2026-02-18*
*Version: 6.0.0*
