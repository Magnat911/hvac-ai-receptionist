# HVAC AI Receptionist - Deployment Guide

## Railway.app Deployment

### Prerequisites
- Railway account (https://railway.app)
- GitHub repository connected
- API keys: AssemblyAI, Inworld, Telnyx

### Step 1: Install Railway CLI
```bash
npm install -g @railway/cli
railway login
```

### Step 2: Link Project
```bash
railway link  # Select "gleaming-flow" project
```

### Step 3: Add Services

**PostgreSQL** (already configured):
```bash
railway add --plugin postgresql
```

**Redis** (for WebSocket pub-sub):
```bash
railway add --plugin redis
```

### Step 4: Set Environment Variables
```bash
railway variables set MOCK_MODE=0
railway variables set ASSEMBLYAI_API_KEY=your_key
railway variables set INWORLD_API_KEY=your_key
railway variables set TELNYX_API_KEY=your_key
railway variables set TELNYX_PHONE=+1XXXXXXXXXX
railway variables set JWT_SECRET=your_secure_secret
```

### Step 5: Deploy
```bash
railway up
```

### Step 6: Configure Domain
```bash
railway domain
# Or set custom domain:
railway domain add hvac-ai.yourcompany.com
```

### Step 7: Configure Telnyx Webhook
1. Go to Telnyx Portal → Voice → SIP Connections
2. Set Webhook URL: `https://your-domain.railway.app/api/telnyx/voice-webhook`
3. Save

## Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `MOCK_MODE` | Yes | Set to `0` for production |
| `ASSEMBLYAI_API_KEY` | Yes | STT + LLM Gateway |
| `INWORLD_API_KEY` | Yes | TTS (Ashley voice) |
| `TELNYX_API_KEY` | Yes | Telephony |
| `TELNYX_PHONE` | Yes | Your Telnyx number |
| `JWT_SECRET` | Yes | Auth token signing |
| `REDIS_URL` | Auto | Set by Railway Redis plugin |
| `DATABASE_URL` | Auto | Set by Railway PostgreSQL plugin |
| `BEPAID_SHOP_ID` | Optional | Payment gateway |
| `BEPAID_SECRET_KEY` | Optional | Payment gateway |

## Health Checks

- **Liveness**: `GET /health`
- **Voice Pipeline**: `GET /api/voice/health`
- **Metrics**: `GET /metrics` (Prometheus)

## Monitoring

Railway provides:
- CPU/Memory graphs
- Log streaming
- Deployment history
- Alert webhooks

## Scaling

```bash
railway scale --replicas 2
```

Note: Multiple replicas require Redis for session sharing.

## Staging Environment

```bash
railway environment add staging
railway variables set MOCK_MODE=1 --environment staging
railway up --environment staging
```

## Troubleshooting

### Container won't start
```bash
railway logs
```

### Database connection fails
- Check `DATABASE_URL` is set
- Verify PostgreSQL is running: `railway status`

### Telnyx webhook not receiving calls
- Verify domain is publicly accessible
- Check webhook URL matches exactly
- Test: `curl https://your-domain.railway.app/health`

### Voice pipeline not working
- Check `ASSEMBLYAI_API_KEY` is valid
- Verify `INWORLD_API_KEY` format (Base64)
- Test: `curl https://your-domain.railway.app/api/voice/health`

## Rollback

```bash
railway rollback
```

## Backup Database

```bash
railway connect postgresql
pg_dump hvac_ai > backup.sql
```
