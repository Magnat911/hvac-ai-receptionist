# Payment Integration - Belarus Merchant + US Customers

## Problem Statement
- Merchant is based in Belarus
- Customers are primarily US-based
- Need card linking for recurring subscriptions
- Stripe not available for Belarus merchants

## Solution: bePaid Gateway

### Why bePaid
- ✅ Belarus-registered merchant support
- ✅ Accepts international Visa/Mastercard (US customers)
- ✅ Card tokenization for recurring billing
- ✅ Apple Pay / Google Pay support
- ✅ Subscription management API
- ✅ PCI DSS compliant

### Alternative Options Considered

| Gateway | Belarus | US Cards | Recurring | Card Linking | Notes |
|---------|---------|----------|-----------|--------------|-------|
| **bePaid** | ✅ | ✅ | ✅ | ✅ | Recommended |
| Adyen | ❌ | ✅ | ✅ | ✅ | No Belarus merchant accounts |
| 2Checkout | ❌ | ✅ | ✅ | ✅ | No Belarus support |
| PayPro Global | ❌ | ✅ | ✅ | ✅ | Digital products only |
| Crypto.com Pay | ✅ | ✅ | ❌ | ❌ | Crypto only, no recurring |

## Integration Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Client    │────▶│  HVAC API   │────▶│  bePaid API │
│  (Browser)  │     │ /api/payment│     │   Gateway   │
└─────────────┘     └─────────────┘     └─────────────┘
                           │                    │
                           │                    ▼
                           │            ┌─────────────┐
                           │            │  Card Token │
                           │            │   Storage   │
                           │            └─────────────┘
                           │                    │
                           ▼                    ▼
                    ┌─────────────────────────────┐
                    │     Webhook Notifications   │
                    │  (payment success, failure) │
                    └─────────────────────────────┘
```

## Subscription Tiers

| Plan | Price | Calls/Month | Features |
|------|-------|-------------|----------|
| **Starter** | $49/mo | 100 | AI Receptionist, Emergency Triage, SMS |
| **Professional** | $99/mo | 500 | + Route Optimization, CRM Sync, Analytics |
| **Enterprise** | $199/mo | 2000 | + Multi-location, Custom Voice, API Access |

## Card Linking Flow

### 1. Create Checkout Session
```python
POST /api/payment/checkout
{
  "plan": "professional",
  "email": "contractor@example.com"
}

Response:
{
  "checkout_url": "https://checkout.bepaid.by/v2/checkout?token=xxx",
  "token": "checkout_token_xxx"
}
```

### 2. Customer Completes Payment
- Redirected to bePaid hosted checkout
- Enters card details (US Visa/Mastercard)
- Optionally saves card for future payments
- Redirected back to success URL

### 3. Webhook Processing
```python
POST /api/payment/webhook
{
  "transaction": {
    "status": "successful",
    "uid": "tx_123456",
    "credit_card": {
      "token": "card_token_xxx",  # Stored for recurring
      "brand": "visa",
      "last_4": "4242"
    }
  }
}
```

### 4. Recurring Billing
```python
# Monthly charge using saved card token
POST to bePaid /transactions/payments
{
  "amount": 9900,  # $99.00 in cents
  "currency": "USD",
  "credit_card": {"token": "card_token_xxx"}
}
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/payment/plans` | GET | List available plans |
| `/api/payment/checkout` | POST | Create checkout session |
| `/api/payment/webhook` | POST | Handle bePaid notifications |
| `/api/payment/subscription` | GET | Get current subscription |
| `/api/payment/invoices` | GET | List invoices |

## Environment Variables

```bash
BEPAID_SHOP_ID=your_shop_id
BEPAID_SECRET_KEY=your_secret_key
BEPAID_API_URL=https://checkout.bepaid.by/ctp/api/checkouts
BEPAID_GATEWAY_URL=https://gateway.bepaid.by/transactions
```

## Testing

### Test Mode
Set `MOCK_MODE=1` to simulate payments without real transactions.

### Test Cards
bePaid provides test card numbers in their sandbox environment.

## Compliance

### PCI DSS
- bePaid handles all card data
- Our system only stores tokens
- No card numbers in our database

### Refunds
```python
POST /api/payment/refund
{
  "invoice_id": "inv_xxx",
  "amount": 5000,  # Partial refund
  "reason": "Customer request"
}
```

## Manual Steps Required

1. **Create bePaid Account**
   - Contact: sales@bepaid.by
   - Provide Belarus business registration
   - Complete KYC process

2. **Configure Webhook URL**
   - Set in bePaid merchant dashboard
   - URL: `https://your-domain.railway.app/api/payment/webhook`

3. **Test with Real Transaction**
   - Use a personal card for $0.01 test
   - Verify webhook receives notification
   - Check token is stored correctly

4. **Enable Live Mode**
   - Switch from test to production keys
   - Update `BEPAID_API_URL` to production endpoint
