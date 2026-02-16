# HVAC AI Receptionist - Operations Guide

## Daily Operations

### Health Monitoring
```bash
# Check service health
curl https://your-domain.railway.app/health

# Check voice pipeline
curl https://your-domain.railway.app/api/voice/health

# Check CRM integration
curl https://your-domain.railway.app/api/crm/health
```

### Log Access
```bash
# Railway logs
railway logs

# Local logs
tail -f logs/hvac.log
```

## Business Logic Configuration

### AI Answering Modes
The system supports multiple answering modes configured per company:

| Mode | Description | When to Use |
|------|-------------|-------------|
| `24/7` | AI answers all calls | Small teams, want 24/7 coverage |
| `after_hours` | AI answers outside business hours | Standard HVAC companies |
| `overflow` | AI answers after N rings | Busier companies with dispatchers |
| `scheduled` | Custom schedule (breaks, meetings) | Flexible coverage |

### Business Hours Configuration
```python
# Example: 7AM-6PM Mon-Sat, closed Sunday
business_hours = {
    "monday": {"open": "07:00", "close": "18:00"},
    "tuesday": {"open": "07:00", "close": "18:00"},
    "wednesday": {"open": "07:00", "close": "18:00"},
    "thursday": {"open": "07:00", "close": "18:00"},
    "friday": {"open": "07:00", "close": "18:00"},
    "saturday": {"open": "07:00", "close": "14:00"},
    "sunday": {"closed": True},
}
```

### Emergency Override
**Gas/CO/Fire emergencies ALWAYS trigger AI response regardless of mode.**
This is hardcoded for safety - no configuration can disable it.

### Time Zone Handling
- All times stored in UTC
- Company timezone set during onboarding
- Emergency detection uses customer's stated indoor temp, not time-based

## Call Handling Procedures

### Normal Call Flow
1. Customer calls → AI answers within 2 rings
2. Greeting: "Hello! Thank you for calling [Company Name]. How can I help you with your heating or cooling needs today?"
3. AI collects: issue description, address, contact info
4. AI schedules appointment or provides information
5. Call ends → transcript saved → CRM updated

### Emergency Call Flow
1. Customer mentions gas/smoke/fire/CO
2. **IMMEDIATE**: AI says "This is an emergency. Please evacuate immediately and call 911."
3. AI collects: current location, people present
4. AI sends SMS to dispatch with emergency details
5. AI stays on line until customer confirms evacuation

### Escalation Triggers
| Trigger | Action |
|---------|--------|
| Customer says "manager" or "supervisor" | Warm transfer to owner |
| 2+ confusion signals ("what?", "I don't understand") | SMS to owner + offer transfer |
| Anger detection (sentiment analysis) | Priority queue, calm response |
| High-value lead ($5k+ job keywords) | SMS alert to owner |

## Pricing Accuracy

### Knowledge Base Pricing
The AI ONLY quotes prices from the knowledge base:
```
- Service call / diagnostic: $89 (applied to repairs)
- Tune-up / maintenance: $129
- Capacitor replacement: $149.99
- Compressor replacement: $599.99
- Emergency surcharge: After-hours may apply
```

### Hallucination Prevention
- AI cannot invent prices not in knowledge base
- Post-generation validation catches any "I think it costs $X" phrases
- If uncertain, AI says "Let me schedule a technician who can provide an accurate quote."

## Route Optimization

### Daily Schedule Generation
```bash
# Trigger route optimization
POST /api/routing/optimize
{
  "date": "2026-02-17",
  "include_emergencies": true
}
```

### Mid-Day Re-optimization
When new emergency jobs come in:
```bash
POST /api/routing/reoptimize
{
  "new_jobs": [{"id": "j_new", "lat": 32.85, "lon": -96.80, ...}],
  "completed_job_ids": ["j01", "j02"]
}
```

## Inventory Alerts

### Low Stock Notifications
Automatic SMS/email when stock drops below reorder point:
```
⚠️ R-410A Refrigerant at 2 units (reorder point: 2)
Reorder from: [Supplier Contact]
```

### EPA Compliance Tracking
- Refrigerant usage requires EPA certification number
- Tracked in audit log
- Monthly report available

## Customer Portal

### Features
- Book appointments online
- See technician ETA (live tracking)
- View service history
- Pay invoices
- Leave reviews

### Portal URL
`https://your-domain.railway.app/portal/{company_id}`

## Technician PWA

### Features
- View optimized route
- Mark jobs complete
- Record parts used
- Access customer history
- Emergency button

### Access
`https://your-domain.railway.app/tech`

## Common Issues

### "AI not understanding"
- Check ASSEMBLYAI_API_KEY is valid
- Verify caller's phone connection quality
- Check `/api/voice/health` for STT status

### "Wrong pricing quoted"
- Update knowledge base in database
- Check `DEFAULT_KNOWLEDGE_BASE` in `hvac_main.py`

### "Emergency not detected"
- Emergency detection is rule-based - check keywords in `analyze_emergency()`
- Add missing keywords if needed

### "Route optimization too slow"
- VROOM should complete in <1s for 50 jobs
- If slower, check memory allocation
- Falls back to greedy automatically

## Maintenance Windows

### Recommended Schedule
- Sunday 2-4 AM local time
- Duration: ~5 minutes for restart
- Zero downtime with multiple replicas

### Deployment
```bash
railway up
```
Rolls out with health checks, automatic rollback on failure.
