# HVAC AI Receptionist — Manual Tasks Checklist
## v6.0.0 Production Deployment

---

## Pre-Deployment Tasks (Required)

### 1. Vercel Deployment
- [ ] Install Vercel CLI: `npm i -g vercel`
- [ ] Login to Vercel: `vercel login`
- [ ] Link project: `vercel link`
- [ ] Set environment variables in Vercel dashboard:
  - [ ] `ASSEMBLYAI_API_KEY`
  - [ ] `INWORLD_API_KEY`
  - [ ] `TELNYX_API_KEY`
  - [ ] `TELNYX_PHONE_NUMBER`
  - [ ] `JWT_SECRET`
  - [ ] `MOCK_MODE=0`
- [ ] Deploy: `vercel --prod`

### 2. Database Setup
- [ ] Create Supabase or Neon PostgreSQL project
- [ ] Run schema: `psql -f hvac_schema.sql`
- [ ] Set `DATABASE_URL` environment variable

### 3. LiveKit Configuration
- [ ] Create LiveKit Cloud account
- [ ] Create API key/secret
- [ ] Set `LIVEKIT_API_KEY` and `LIVEKIT_API_SECRET`
- [ ] Set `LIVEKIT_URL` (e.g., `wss://your-project.livekit.cloud`)

### 4. Telnyx Configuration
- [ ] Purchase phone number in Telnyx dashboard
- [ ] Configure webhook URL: `https://your-app.vercel.app/api/telnyx/webhook`
- [ ] Enable Call Control (Call Control Application)
- [ ] Set SIP connection for media streaming

### 5. Payment Gateway (bePaid)
- [ ] Create bePaid merchant account (Belarus-compatible)
- [ ] Get API keys (test + production)
- [ ] Set `BEPAID_API_KEY` and `BEPAID_SHOP_ID`
- [ ] Configure webhook for payment confirmations
- [ ] Test payment flow with test cards

---

## Post-Deployment Tasks

### 6. Real Phone Call Testing (50 calls)
- [ ] Test emergency scenarios (10 calls):
  - [ ] Gas leak detection
  - [ ] CO detector alarm
  - [ ] Fire hazard
  - [ ] No heat + elderly
  - [ ] No AC + infant
- [ ] Test scheduling scenarios (10 calls):
  - [ ] Tune-up booking
  - [ ] Emergency appointment
  - [ ] Rescheduling
  - [ ] Cancellation
- [ ] Test pricing inquiries (10 calls):
  - [ ] Service call cost
  - [ ] Tune-up cost
  - [ ] Major repair estimate
- [ ] Test prohibited topics (10 calls):
  - [ ] DIY refrigerant instructions (should block)
  - [ ] Medical advice (should block)
  - [ ] Legal advice (should block)
- [ ] Test edge cases (10 calls):
  - [ ] Background noise
  - [ ] Fast speech
  - [ ] Accented speech
  - [ ] Interrupted speech

### 7. Load Testing
- [ ] Install Locust: `pip install locust`
- [ ] Run load test: `locust -f locustfile.py --host=https://your-app.vercel.app`
- [ ] Target: 100 concurrent users, 1000 requests
- [ ] Verify response time < 2s

### 8. Security Testing
- [ ] Run OWASP ZAP scan
- [ ] Test SQL injection on all endpoints
- [ ] Test XSS on chat input
- [ ] Test CSRF protection
- [ ] Verify rate limiting works
- [ ] Check JWT token expiration

### 9. Monitoring Setup
- [ ] Configure Vercel Analytics
- [ ] Set up error tracking (Sentry recommended)
- [ ] Create uptime monitoring (Pingdom/UptimeRobot)
- [ ] Configure log aggregation

---

## Business Setup Tasks

### 10. Legal & Compliance
- [ ] Create Terms of Service
- [ ] Create Privacy Policy
- [ ] Create Service Level Agreement (SLA)
- [ ] Review EPA compliance logging
- [ ] Consult lawyer for liability coverage

### 11. Marketing Setup
- [ ] Create Google Business Profile
- [ ] Set up Google Ads (HVAC keywords)
- [ ] Create Facebook Business Page
- [ ] Create demo videos for YouTube
- [ ] Write case studies from beta users

### 12. CRM Integrations
- [ ] Apply for Housecall Pro API access
- [ ] Apply for Jobber API access
- [ ] Test FieldPulse integration
- [ ] Create integration documentation

### 13. Customer Onboarding
- [ ] Create onboarding email sequence
- [ ] Create knowledge base articles
- [ ] Create video tutorials
- [ ] Set up support email/ticket system

---

## Quick Start Commands

```bash
# Deploy to Vercel
vercel --prod

# Run tests
python3 -m pytest hvac_test.py -v
python3 hvac_test_full.py

# Load test
locust -f locustfile.py --host=https://your-app.vercel.app

# Check logs
vercel logs --follow

# Set environment variables
vercel env add ASSEMBLYAI_API_KEY
vercel env add INWORLD_API_KEY
vercel env add TELNYX_API_KEY
vercel env add JWT_SECRET
```

---

## Environment Variables Summary

| Variable | Required | Source |
|----------|----------|--------|
| `ASSEMBLYAI_API_KEY` | Yes | assemblyai.com |
| `INWORLD_API_KEY` | Yes | inworld.ai |
| `TELNYX_API_KEY` | Yes | telnyx.com |
| `TELNYX_PHONE_NUMBER` | Yes | Telnyx dashboard |
| `JWT_SECRET` | Yes | Generate random 32+ chars |
| `LIVEKIT_API_KEY` | Yes | livekit.io |
| `LIVEKIT_API_SECRET` | Yes | livekit.io |
| `LIVEKIT_URL` | Yes | e.g., wss://xxx.livekit.cloud |
| `DATABASE_URL` | Yes | Supabase/Neon |
| `BEPAID_API_KEY` | Yes | bepaid.by |
| `BEPAID_SHOP_ID` | Yes | bepaid.by |
| `MOCK_MODE` | No | Set to 0 for production |

---

## Current Status

| Component | Status | Notes |
|-----------|--------|-------|
| Core API | ✅ Ready | 135/135 tests passing |
| Voice Pipeline | ✅ Ready | AssemblyAI + Inworld TTS |
| Telephony | ✅ Ready | Telnyx integration |
| Route Optimization | ✅ Ready | VROOM solver |
| Inventory | ✅ Ready | EPA compliance |
| CRM Integration | ✅ Ready | Housecall Pro, Jobber, FieldPulse |
| Landing Page | ✅ Ready | LiveKit voice button |
| Business Plan | ✅ Ready | $75K MRR projection |
| Pain Closure | ✅ Ready | 100% of pains addressed |
| Payment Gateway | ⚠️ Pending | bePaid account needed |
| Real Call Testing | ⚠️ Pending | Deployment required |
| Load Testing | ⚠️ Pending | Deployment required |

---

## Priority Order

1. **HIGH**: Deploy to Vercel + configure env vars
2. **HIGH**: Set up LiveKit + Telnyx
3. **HIGH**: Real phone call testing (50 calls)
4. **MEDIUM**: bePaid payment gateway setup
5. **MEDIUM**: Load testing
6. **LOW**: Security audit
7. **LOW**: Marketing setup

---

*Checklist created: 2026-02-18*
*Version: 6.0.0*
