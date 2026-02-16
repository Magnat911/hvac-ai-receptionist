# HVAC AI Receptionist - Troubleshooting Guide

## Quick Diagnostics

### All Systems Check
```bash
curl https://your-domain.railway.app/health
```
Expected response:
```json
{
  "status": "healthy",
  "version": "6.0.0",
  "services": {
    "llm": "claude-haiku-4.5-assemblyai",
    "telephony": "telnyx",
    "db": "connected",
    "redis": "connected"
  }
}
```

## Common Problems

### 1. API Not Responding

**Symptoms**: 502 Bad Gateway, timeouts, no response

**Check**:
```bash
railway logs --tail 100
```

**Common Causes**:
- Database connection failed → Check `DATABASE_URL`
- Redis not connected → Check `REDIS_URL`
- App crashed → Check for Python errors in logs

**Solution**:
```bash
railway restart
```

---

### 2. Voice Pipeline Not Working

**Symptoms**: No TTS audio, STT not transcribing

**Check**:
```bash
curl https://your-domain.railway.app/api/voice/health
```

**Common Causes**:
- `ASSEMBLYAI_API_KEY` invalid or expired
- `INWORLD_API_KEY` incorrect format (needs Base64)
- Rate limited by API provider

**Solutions**:
```bash
# Verify AssemblyAI key
curl -H "authorization: YOUR_KEY" https://api.assemblyai.com/v2/transcript

# Test TTS
curl -X POST https://your-domain.railway.app/api/voice/tts \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello world"}'
```

---

### 3. Phone Calls Not Connecting

**Symptoms**: Calls go to voicemail, no AI response

**Check**:
```bash
curl https://your-domain.railway.app/api/telnyx/active-calls
```

**Common Causes**:
- Telnyx webhook URL incorrect
- SIP connection not configured
- Number not assigned to connection

**Solutions**:
1. Verify webhook URL in Telnyx portal:
   - Must be: `https://your-domain.railway.app/api/telnyx/voice-webhook`
2. Check SIP connection status in Telnyx portal
3. Verify phone number is assigned to the SIP connection

---

### 4. Database Connection Failed

**Symptoms**: "connection refused", "database unavailable"

**Check**:
```bash
railway status
```

**Common Causes**:
- PostgreSQL plugin not added
- Connection string wrong
- Database at capacity

**Solutions**:
```bash
# Add PostgreSQL if missing
railway add --plugin postgresql

# Get connection string
railway variables | grep DATABASE_URL
```

---

### 5. Redis Connection Failed

**Symptoms**: WebSocket errors, session not persisting

**Check**:
```bash
railway variables | grep REDIS_URL
```

**Solutions**:
```bash
# Add Redis if missing
railway add --plugin redis
```

---

### 6. Emergency Detection Not Working

**Symptoms**: Gas leak not triggering emergency response

**Check**:
```bash
curl -X POST https://your-domain.railway.app/api/emergency/analyze \
  -H "Content-Type: application/json" \
  -d '{"text": "I smell gas"}'
```

**Expected**:
```json
{
  "is_emergency": true,
  "priority": "CRITICAL",
  "requires_evacuation": true,
  "requires_911": true
}
```

**If not working**:
- Check `analyze_emergency()` in `hvac_main.py` for keyword list
- Add missing keywords if needed

---

### 7. Wrong Pricing Quoted

**Symptoms**: AI quotes wrong prices

**Root Cause**: Knowledge base outdated

**Solution**: Update `DEFAULT_KNOWLEDGE_BASE` or database entries

```python
# In hvac_main.py, update the pricing entry:
"pricing": {
    "content": "Service call: $89. Tune-up: $129. Capacitor: $149.99..."
}
```

---

### 8. Route Optimization Slow/Failing

**Symptoms**: Timeout, no route returned

**Check**:
```python
# Test with small dataset
from hvac_routing import HybridRouter, Technician, Job
import asyncio

async def test():
    router = HybridRouter()
    techs = [Technician("t1", "Test", 32.8, -96.8, ["hvac"])]
    jobs = [Job("j1", 32.85, -96.85, "maintenance")]
    return await router.optimize_routes(techs, jobs)

asyncio.run(test())
```

**Common Causes**:
- VROOM package not installed (`pip install vroom`)
- Too many jobs (limit: 100 per request)
- Memory limit reached

---

### 9. Authentication Errors

**Symptoms**: 401 Unauthorized, "Invalid token"

**Check**:
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  https://your-domain.railway.app/api/auth/verify
```

**Common Causes**:
- Token expired (default: 24 hours)
- `JWT_SECRET` changed
- Token not included in request

**Solutions**:
- Re-login to get new token
- Verify `JWT_SECRET` is set and consistent

---

### 10. High Latency

**Symptoms**: Responses taking >5 seconds

**Check**:
```bash
# Check LLM latency
curl https://your-domain.railway.app/metrics | grep hvac_llm_latency
```

**Common Causes**:
- AssemblyAI API slow → Check status.assemblyai.com
- Database queries slow → Add indexes
- Memory pressure → Scale up

---

## Performance Tuning

### Reduce Latency
```bash
# Use smaller max_tokens
# Increase worker count (if memory allows)
railway scale --replicas 2
```

### Handle More Calls
```bash
# Add more replicas
railway scale --replicas 3

# Ensure Redis is connected for session sharing
```

---

## Support Contacts

| Issue | Contact |
|-------|---------|
| AssemblyAI | support@assemblyai.com |
| Inworld | support@inworld.ai |
| Telnyx | support@telnyx.com |
| bePaid | help@bepaid.by |
| Railway | support@railway.app |

---

## Emergency Contacts

For production outages:
1. Check status pages:
   - https://status.railway.app
   - https://status.assemblyai.com
   - https://status.telnyx.com
2. Restart services: `railway restart`
3. Check logs: `railway logs`
