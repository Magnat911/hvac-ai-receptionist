# HVAC AI Receptionist v6.0 - Deployment Guide

## Railway.app Deployment (Complete Setup)

### Prerequisites
- Railway account (https://railway.app) - Hobby plan $5/mo recommended
- GitHub repository connected
- API keys: AssemblyAI, Inworld, Telnyx, bePaid (optional)

---

## Step 1: Install Railway CLI

```bash
npm install -g @railway/cli
railway login
```

---

## Step 2: Create Project & Link

```bash
# Create new project
railway project create hvac-ai-receptionist

# Or link existing
railway link  # Select your project
```

---

## Step 3: Add Services (Required)

### PostgreSQL Database
```bash
railway add --plugin postgresql

# Verify connection
railway variables  # Should show DATABASE_URL
```

### Redis Cache (for sessions, WebSocket pub-sub)
```bash
railway add --plugin redis

# Verify connection
railway variables  # Should show REDIS_URL
```

---

## Step 4: Configure Volumes (Persistent Storage)

```bash
# Data volume (customer data, settings)
railway volume create hvac-data --mount /app/data

# Logs volume (audit trail, debugging)
railway volume create hvac-logs --mount /app/logs

# Recordings volume (call recordings)
railway volume create hvac-recordings --mount /app/recordings
```

---

## Step 5: Set Environment Variables

### Required Variables
```bash
railway variables set MOCK_MODE=0
railway variables set LOG_LEVEL=INFO

# Voice Pipeline
railway variables set ASSEMBLYAI_API_KEY=your_assemblyai_key
railway variables set INWORLD_API_KEY=your_inworld_base64_key
railway variables set TELNYX_API_KEY=your_telnyx_key
railway variables set TELNYX_PHONE_NUMBER=+1XXXXXXXXXX
railway variables set TELNYX_PUBLIC_API_KEY=your_telnyx_public_key

# Authentication
railway variables set JWT_SECRET=$(openssl rand -hex 32)
```

### Optional Variables
```bash
# Payment Processing (bePaid - Belarus merchant)
railway variables set BEPAID_SHOP_ID=your_shop_id
railway variables set BEPAID_SECRET_KEY=your_secret_key

# CRM Integration
railway variables set CRM_TYPE=housecall_pro  # or jobber, servicetitan
railway variables set CRM_API_KEY=your_crm_api_key

# Route Optimization
railway variables set OSRM_URL=  # Optional: real road distances

# Application URL (for webhooks)
railway variables set APP_URL=https://your-app.railway.app
```

---

## Step 6: Deploy

```bash
# Deploy to production
railway up

# Or with Docker
railway up --dockerfile Dockerfile
```

---

## Step 7: Configure Domain

### Railway Domain (Quick)
```bash
railway domain
# Returns: https://hvac-ai-receptionist-production.up.railway.app
```

### Custom Domain
```bash
railway domain add hvac-ai.yourcompany.com

# Add DNS records:
# CNAME hvac-ai -> your-app.railway.app
```

---

## Step 8: Configure External Webhooks

### Telnyx Voice Webhook
1. Go to Telnyx Portal → Voice → SIP Connections
2. Set Webhook URL: `https://your-domain.railway.app/api/telnyx/voice-webhook`
3. Enable: `POST` method
4. Save

### bePaid Payment Webhook
1. In bePaid dashboard, set notification URL
2. URL: `https://your-domain.railway.app/api/payment/webhook`
3. Verify signature in code

### CRM Webhooks (Housecall Pro / Jobber)
1. Configure in CRM settings
2. URL: `https://your-domain.railway.app/api/crm/webhook`

---

## Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `MOCK_MODE` | Yes | `0` for production, `1` for testing |
| `ASSEMBLYAI_API_KEY` | Yes | STT + LLM Gateway (Claude Haiku) |
| `INWORLD_API_KEY` | Yes | TTS (Ashley voice) - Base64 encoded |
| `TELNYX_API_KEY` | Yes | Telephony API key |
| `TELNYX_PHONE_NUMBER` | Yes | Your Telnyx phone number |
| `TELNYX_PUBLIC_API_KEY` | Yes | Telnyx public key for JWT |
| `JWT_SECRET` | Yes | Auth token signing (32+ chars) |
| `REDIS_URL` | Auto | Set by Railway Redis plugin |
| `DATABASE_URL` | Auto | Set by Railway PostgreSQL plugin |
| `BEPAID_SHOP_ID` | Optional | Payment gateway shop ID |
| `BEPAID_SECRET_KEY` | Optional | Payment gateway secret |
| `CRM_TYPE` | Optional | `housecall_pro`, `jobber`, `servicetitan` |
| `CRM_API_KEY` | Optional | CRM API key |
| `OSRM_URL` | Optional | OSRM server for real road distances |
| `APP_URL` | Optional | Public URL for webhooks |

---

## Health Checks

| Endpoint | Purpose | Expected Response |
|----------|---------|-------------------|
| `GET /health` | Liveness probe | `{"status": "healthy"}` |
| `GET /api/voice/health` | Voice pipeline status | `{"stt": "ok", "llm": "ok", "tts": "ok"}` |
| `GET /api/crm/health` | CRM connection status | `{"status": "ok", "crm_type": "housecall_pro"}` |
| `GET /metrics` | Prometheus metrics | Prometheus format |

---

## Monitoring & Observability

### Railway Dashboard
- CPU/Memory graphs (real-time)
- Log streaming
- Deployment history
- Alert webhooks

### Prometheus Metrics
```bash
# Available at /metrics
curl https://your-app.railway.app/metrics
```

### Log Aggregation
```bash
# View logs
railway logs

# Follow logs
railway logs --follow

# Filter by service
railway logs --service hvac-ai
```

---

## Scaling

### Horizontal Scaling (Multiple Replicas)
```bash
railway scale --replicas 2
```

**Note**: Multiple replicas require Redis for session sharing. Already configured.

### Vertical Scaling (More Resources)
```bash
# In Railway dashboard, adjust:
# - CPU: 1-8 vCPUs
# - Memory: 512MB-16GB
```

---

## Staging Environment

```bash
# Create staging environment
railway environment add staging

# Set staging variables
railway variables set MOCK_MODE=1 --environment staging
railway variables set LOG_LEVEL=DEBUG --environment staging

# Deploy to staging
railway up --environment staging

# View staging logs
railway logs --environment staging
```

---

## CI/CD Integration

### GitHub Actions
```yaml
# .github/workflows/deploy.yml
name: Deploy to Railway
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: bahmutov/npm-install@v1
      - run: npm install -g @railway/cli
      - run: railway up --token ${{ secrets.RAILWAY_TOKEN }}
```

---

## Troubleshooting

### Container won't start
```bash
railway logs
# Check for:
# - Missing environment variables
# - Port binding issues
# - Database connection failures
```

### Database connection fails
```bash
# Check DATABASE_URL is set
railway variables | grep DATABASE

# Verify PostgreSQL is running
railway status

# Connect to database
railway connect postgresql
```

### Redis connection fails
```bash
# Check REDIS_URL is set
railway variables | grep REDIS

# Verify Redis is running
railway status
```

### Telnyx webhook not receiving calls
1. Verify domain is publicly accessible: `curl https://your-domain.railway.app/health`
2. Check webhook URL matches exactly in Telnyx portal
3. Verify Telnyx credentials are correct
4. Check logs for incoming requests: `railway logs --filter telnyx`

### Voice pipeline not working
```bash
# Test each component
curl https://your-domain.railway.app/api/voice/health

# Check API keys
railway variables | grep ASSEMBLYAI
railway variables | grep INWORLD

# Common issues:
# - ASSEMBLYAI_API_KEY invalid
# - INWORLD_API_KEY not Base64 encoded
# - WebSocket connection blocked by firewall
```

### Payment webhook fails
```bash
# Check bePaid credentials
railway variables | grep BEPAID

# Verify signature in logs
railway logs --filter payment
```

---

## Rollback

```bash
# List recent deployments
railway status

# Rollback to previous deployment
railway rollback

# Rollback to specific deployment
railway rollback --deployment <deployment-id>
```

---

## Backup & Recovery

### Database Backup
```bash
# Connect to PostgreSQL
railway connect postgresql

# Create backup
pg_dump $POSTGRES_DB > backup_$(date +%Y%m%d).sql

# Restore backup
psql $POSTGRES_DB < backup_20260217.sql
```

### Volume Backup
```bash
# Download volume contents
railway volume download hvac-data ./backup-data
```

---

## Security Checklist

- [ ] `JWT_SECRET` is 32+ random characters
- [ ] `MOCK_MODE=0` in production
- [ ] All API keys are valid and not expired
- [ ] Telnyx webhook signature verification enabled
- [ ] bePaid webhook signature verification enabled
- [ ] HTTPS only (Railway default)
- [ ] No sensitive data in logs (`LOG_LEVEL=INFO` not `DEBUG`)

---

## Cost Estimation (Railway Hobby Plan)

| Service | Cost |
|---------|------|
| Compute (1 vCPU, 512MB) | ~$5/mo |
| PostgreSQL (1GB) | ~$5/mo |
| Redis (256MB) | ~$3/mo |
| Volumes (3GB) | ~$1/mo |
| Bandwidth (10GB) | ~$1/mo |
| **Total** | **~$15/mo** |

**Note**: Costs scale with usage. See Railway pricing for details.

---

## Support

- Railway Docs: https://docs.railway.app
- Railway Discord: https://discord.gg/railway
- Project Issues: https://github.com/your-repo/hvac-ai/issues
