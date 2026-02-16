#!/usr/bin/env python3
"""
HVAC AI v6.0 - Payment Integration (bePaid Gateway)
Subscription billing, card linking, invoice management for Belarus-based merchant.
"""

import os
import hmac
import hashlib
import json
import logging
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass, asdict

import httpx

logger = logging.getLogger("hvac-payment")

BEPAID_SHOP_ID = os.getenv("BEPAID_SHOP_ID", "")
BEPAID_SECRET_KEY = os.getenv("BEPAID_SECRET_KEY", "")
BEPAID_API_URL = os.getenv("BEPAID_API_URL", "https://checkout.bepaid.by/ctp/api/checkouts")
BEPAID_GATEWAY_URL = os.getenv("BEPAID_GATEWAY_URL", "https://gateway.bepaid.by/transactions")
MOCK_MODE = os.getenv("MOCK_MODE", "1") == "1"

# Subscription tiers
PLANS = {
    "starter": {"name": "Starter", "price_cents": 4900, "calls_month": 100, "features": ["ai_receptionist", "emergency_triage", "sms_notifications"]},
    "professional": {"name": "Professional", "price_cents": 9900, "calls_month": 500, "features": ["ai_receptionist", "emergency_triage", "sms_notifications", "route_optimization", "crm_sync", "analytics"]},
    "enterprise": {"name": "Enterprise", "price_cents": 19900, "calls_month": 2000, "features": ["ai_receptionist", "emergency_triage", "sms_notifications", "route_optimization", "crm_sync", "analytics", "multi_location", "custom_voice", "api_access"]},
}


@dataclass
class Subscription:
    id: str
    company_id: str
    plan: str
    status: str  # active, past_due, cancelled, trialing
    card_token: str
    current_period_start: str
    current_period_end: str
    created_at: str


@dataclass
class Invoice:
    id: str
    company_id: str
    subscription_id: str
    amount_cents: int
    currency: str
    status: str  # paid, pending, failed, refunded
    paid_at: Optional[str]
    created_at: str


class PaymentService:
    """bePaid payment gateway integration for subscription billing."""

    def __init__(self, shop_id: str = "", secret_key: str = "", mock: bool = False):
        self.shop_id = shop_id or BEPAID_SHOP_ID
        self.secret_key = secret_key or BEPAID_SECRET_KEY
        self.mock = mock or not self.shop_id
        # In-memory stores (DB-backed in production)
        self.subscriptions: Dict[str, Subscription] = {}
        self.invoices: Dict[str, Invoice] = {}
        self.card_tokens: Dict[str, Dict] = {}  # company_id -> token info

    def _auth(self) -> Tuple[str, str]:
        return (self.shop_id, self.secret_key)

    async def create_checkout(self, company_id: str, plan: str, email: str) -> Dict:
        """Create a checkout token for card linking + first payment."""
        if plan not in PLANS:
            return {"error": f"Invalid plan: {plan}"}
        plan_info = PLANS[plan]

        if self.mock:
            token = f"mock_checkout_{uuid.uuid4().hex[:12]}"
            return {
                "checkout_url": f"https://checkout.bepaid.by/v2/checkout?token={token}",
                "token": token,
                "plan": plan,
                "amount_cents": plan_info["price_cents"],
                "mock": True,
            }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    BEPAID_API_URL,
                    auth=self._auth(),
                    json={
                        "checkout": {
                            "test": False,
                            "transaction_type": "payment",
                            "order": {
                                "amount": plan_info["price_cents"],
                                "currency": "USD",
                                "description": f"HVAC AI - {plan_info['name']} Plan (Monthly)",
                            },
                            "settings": {
                                "save_card_toggle": {"display": True, "customer_contract": True},
                                "customer_fields": {"read_only": ["email"]},
                                "success_url": f"{os.getenv('APP_URL', 'https://hvac-ai.up.railway.app')}/payment/success",
                                "fail_url": f"{os.getenv('APP_URL', 'https://hvac-ai.up.railway.app')}/payment/fail",
                                "notification_url": f"{os.getenv('APP_URL', 'https://hvac-ai.up.railway.app')}/api/payment/webhook",
                            },
                            "customer": {"email": email},
                        }
                    },
                )
                data = resp.json()
                if resp.status_code in (200, 201):
                    return {
                        "checkout_url": data.get("checkout", {}).get("redirect_url", ""),
                        "token": data.get("checkout", {}).get("token", ""),
                        "plan": plan,
                        "amount_cents": plan_info["price_cents"],
                    }
                return {"error": data}
        except Exception as e:
            logger.error(f"bePaid checkout error: {e}")
            return {"error": str(e)}

    async def process_webhook(self, payload: Dict, signature: str = "") -> Dict:
        """Process bePaid webhook notification (payment completed, card saved)."""
        if not self.mock and signature:
            expected = hmac.new(
                self.secret_key.encode(), json.dumps(payload).encode(), hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(signature, expected):
                logger.warning("Invalid webhook signature")
                return {"error": "invalid_signature"}

        tx = payload.get("transaction", {})
        status = tx.get("status", "")
        uid = tx.get("uid", "")

        if status == "successful":
            card = tx.get("credit_card", {})
            company_id = tx.get("description", "").split("|")[-1].strip() if "|" in tx.get("description", "") else ""
            if card.get("token"):
                self.card_tokens[company_id] = {
                    "token": card["token"],
                    "brand": card.get("brand", ""),
                    "last_4": card.get("last_4", ""),
                    "exp_month": card.get("exp_month"),
                    "exp_year": card.get("exp_year"),
                }
            logger.info(f"Payment successful: {uid}, company: {company_id}")
            return {"status": "processed", "transaction_uid": uid}

        logger.warning(f"Payment webhook status: {status}")
        return {"status": status, "transaction_uid": uid}

    async def charge_recurring(self, company_id: str, amount_cents: int, description: str = "") -> Dict:
        """Charge a saved card for recurring billing."""
        card = self.card_tokens.get(company_id)
        if not card:
            return {"error": "no_card_on_file"}

        if self.mock:
            invoice_id = f"inv_{uuid.uuid4().hex[:8]}"
            inv = Invoice(
                id=invoice_id, company_id=company_id, subscription_id="",
                amount_cents=amount_cents, currency="USD", status="paid",
                paid_at=datetime.now(timezone.utc).isoformat(), created_at=datetime.now(timezone.utc).isoformat(),
            )
            self.invoices[invoice_id] = inv
            return {"status": "paid", "invoice_id": invoice_id, "mock": True}

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{BEPAID_GATEWAY_URL}/payments",
                    auth=self._auth(),
                    json={
                        "request": {
                            "amount": amount_cents,
                            "currency": "USD",
                            "description": description or f"HVAC AI Monthly - {company_id}",
                            "credit_card": {"token": card["token"]},
                        }
                    },
                )
                data = resp.json()
                tx = data.get("transaction", {})
                status = "paid" if tx.get("status") == "successful" else "failed"
                invoice_id = f"inv_{uuid.uuid4().hex[:8]}"
                inv = Invoice(
                    id=invoice_id, company_id=company_id, subscription_id="",
                    amount_cents=amount_cents, currency="USD", status=status,
                    paid_at=datetime.now(timezone.utc).isoformat() if status == "paid" else None,
                    created_at=datetime.now(timezone.utc).isoformat(),
                )
                self.invoices[invoice_id] = inv
                return {"status": status, "invoice_id": invoice_id, "transaction": tx.get("uid")}
        except Exception as e:
            logger.error(f"Recurring charge error: {e}")
            return {"error": str(e)}

    def create_subscription(self, company_id: str, plan: str, card_token: str = "") -> Subscription:
        """Create a subscription record."""
        now = datetime.now(timezone.utc)
        sub = Subscription(
            id=f"sub_{uuid.uuid4().hex[:8]}",
            company_id=company_id,
            plan=plan,
            status="active",
            card_token=card_token,
            current_period_start=now.isoformat(),
            current_period_end=(now + timedelta(days=30)).isoformat(),
            created_at=now.isoformat(),
        )
        self.subscriptions[sub.id] = sub
        return sub

    def get_subscription(self, company_id: str) -> Optional[Subscription]:
        for sub in self.subscriptions.values():
            if sub.company_id == company_id and sub.status in ("active", "trialing"):
                return sub
        return None

    def get_invoices(self, company_id: str) -> List[Invoice]:
        return [inv for inv in self.invoices.values() if inv.company_id == company_id]

    def get_plans(self) -> Dict:
        return {k: {**v, "price_display": f"${v['price_cents']/100:.0f}/mo"} for k, v in PLANS.items()}
