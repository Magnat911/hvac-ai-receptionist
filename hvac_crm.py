from typing import Dict, Optional
#!/usr/bin/env python3
"""
HVAC AI v6.0 - CRM Integration Module
Supports: Housecall Pro, Jobber, FieldPulse (API-based sync)

Features:
- Customer sync (create, update, de-duplication)
- Appointment sync (schedule, status, notes)
- Invoice sync (create, status, payment)
- Webhook handlers for real-time updates
- Polling fallback for CRMs without webhooks
"""

import os
import json
import logging
import asyncio
import hashlib
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict

import httpx

logger = logging.getLogger("hvac-crm")

MOCK_MODE = os.getenv("MOCK_MODE", "1") == "1"

CRM_TYPE = os.getenv("CRM_TYPE", "housecall_pro")  # housecall_pro, jobber, fieldpulse
CRM_API_KEY = os.getenv("CRM_API_KEY", "")
CRM_API_URL = os.getenv("CRM_API_URL", "")

HOUSECALL_PRO_API = "https://api.housecallpro.com"
JOBBER_API = "https://api.getjobber.com/api/graphql"
FIELDPULSE_API = "https://api.fieldpulse.com"


@dataclass
class CRMCustomer:
    id: str
    crm_id: str
    first_name: str
    last_name: str
    phone: str
    email: str
    address: str
    city: str
    state: str
    zip_code: str
    notes: str = ""
    created_at: str = ""
    updated_at: str = ""


@dataclass
class CRMAppointment:
    id: str
    crm_id: str
    customer_id: str
    scheduled_start: str
    scheduled_end: str
    technician_id: str
    status: str
    service_type: str
    notes: str = ""
    address: str = ""


@dataclass
class CRMInvoice:
    id: str
    crm_id: str
    customer_id: str
    appointment_id: str
    amount: float
    status: str
    paid_at: str = ""


class CRMClient:
    """Base CRM client with common operations."""

    def __init__(self, crm_type: str = "", api_key: str = "", mock: bool = False):
        self.crm_type = crm_type or CRM_TYPE
        self.api_key = api_key or CRM_API_KEY
        self.mock = mock or not self.api_key
        self.base_url = CRM_API_URL or self._get_default_url()
        self._customers: Dict[str, CRMCustomer] = {}
        self._appointments: Dict[str, CRMAppointment] = {}
        self._invoices: Dict[str, CRMInvoice] = {}
        self._webhook_handlers: Dict[str, Callable] = {}

    def _get_default_url(self) -> str:
        urls = {
            "housecall_pro": HOUSECALL_PRO_API,
            "jobber": JOBBER_API,
            "fieldpulse": FIELDPULSE_API,
        }
        return urls.get(self.crm_type, "")

    def _headers(self) -> Dict[str, str]:
        if self.crm_type == "housecall_pro":
            return {"Authorization": f"Token {self.api_key}", "Content-Type": "application/json"}
        elif self.crm_type == "jobber":
            return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        elif self.crm_type == "fieldpulse":
            return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        return {}

    async def _request(self, method: str, path: str, data: Dict = None,) -> Dict:
        if self.mock:
            return self._mock_response(method, path, data)

        url = f"{self.base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                if method == "GET":
                    resp = await client.get(url, headers=self._headers())
                elif method == "POST":
                    resp = await client.post(url, headers=self._headers(), json=data)
                elif method == "PUT":
                    resp = await client.put(url, headers=self._headers(), json=data)
                elif method == "DELETE":
                    resp = await client.delete(url, headers=self._headers())
                else:
                    raise ValueError(f"Unknown method: {method}")

                if resp.status_code >= 400:
                    logger.error(f"CRM API error: {resp.status_code} - {resp.text}")
                    return {"error": resp.text, "status_code": resp.status_code}

                return resp.json()
        except Exception as e:
            logger.error(f"CRM request error: {e}")
            return {"error": str(e)}

    def _mock_response(self, method: str, path: str, data: Dict) -> Dict:
        if "customers" in path:
            if method == "GET":
                return {"customers": [asdict(c) for c in self._customers.values()]}
            elif method == "POST":
                cust_id = f"cust_{uuid.uuid4().hex[:8]}"
                cust = CRMCustomer(
                    id=cust_id, crm_id=cust_id, created_at=datetime.now(timezone.utc).isoformat(),
                    **{k: v for k, v in data.items() if k in CRMCustomer.__dataclass_fields__}
                )
                self._customers[cust_id] = cust
                return {"customer": asdict(cust)}
        elif "appointments" in path:
            if method == "GET":
                return {"appointments": [asdict(a) for a in self._appointments.values()]}
            elif method == "POST":
                appt_id = f"appt_{uuid.uuid4().hex[:8]}"
                appt = CRMAppointment(
                    id=appt_id, crm_id=appt_id,
                    **{k: v for k, v in data.items() if k in CRMAppointment.__dataclass_fields__}
                )
                self._appointments[appt_id] = appt
                return {"appointment": asdict(appt)}
        elif "invoices" in path:
            if method == "GET":
                return {"invoices": [asdict(i) for i in self._invoices.values()]}
        return {"mock": True}

    async def get_customer(self, customer_id: str) -> Optional[CRMCustomer]:
        if self.mock:
            return self._customers.get(customer_id)
        resp = await self._request("GET", f"/customers/{customer_id}")
        if "customer" in resp:
            return CRMCustomer(**resp["customer"])
        return None

    async def create_customer(self, data: Dict) -> CRMCustomer:
        resp = await self._request("POST", "/customers", data)
        if "customer" in resp:
            return CRMCustomer(**resp["customer"])
        if "id" in resp:
            return CRMCustomer(**resp)
        raise Exception(f"Failed to create customer: {resp}")

    async def find_customer_by_phone(self, phone: str) -> Optional[CRMCustomer]:
        normalized = self._normalize_phone(phone)
        if self.mock:
            for c in self._customers.values():
                if self._normalize_phone(c.phone) == normalized:
                    return c
            return None
        resp = await self._request("GET", f"/customers?phone={normalized}")
        customers = resp.get("customers", [])
        return CRMCustomer(**customers[0]) if customers else None

    def _normalize_phone(self, phone: str) -> str:
        return "".join(c for c in phone if c.isdigit())

    async def create_appointment(self, data: Dict) -> CRMAppointment:
        resp = await self._request("POST", "/appointments", data)
        if "appointment" in resp:
            return CRMAppointment(**resp["appointment"])
        if "id" in resp:
            return CRMAppointment(**resp)
        raise Exception(f"Failed to create appointment: {resp}")

    async def update_appointment_status(self, appt_id: str, status: str) -> bool:
        resp = await self._request("PUT", f"/appointments/{appt_id}", {"status": status})
        return "error" not in resp

    async def create_invoice(self, data: Dict) -> CRMInvoice:
        resp = await self._request("POST", "/invoices", data)
        if "invoice" in resp:
            return CRMInvoice(**resp["invoice"])
        if "id" in resp:
            return CRMInvoice(**resp)
        raise Exception(f"Failed to create invoice: {resp}")

    def register_webhook_handler(self, event_type: str, handler: Callable):
        self._webhook_handlers[event_type] = handler

    async def process_webhook(self, event_type: str, payload: Dict) -> Dict:
        handler = self._webhook_handlers.get(event_type)
        if handler:
            return await handler(payload)
        logger.info(f"No handler for webhook event: {event_type}")
        return {"status": "ignored"}


class CRMService:
    """High-level CRM operations for HVAC AI."""

    def __init__(self, client: Optional[CRMClient] = None):
        self.client = client or CRMClient()

    async def sync_customer_from_call(self, phone: str, name: str = "",
                                       address: str = "", email: str = "") -> CRMCustomer:
        existing = await self.client.find_customer_by_phone(phone)
        if existing:
            return existing
        parts = name.split(" ", 1)
        first_name = parts[0] if parts else ""
        last_name = parts[1] if len(parts) > 1 else ""
        addr_parts = address.split(",", 1)
        street = addr_parts[0].strip() if addr_parts else ""
        city_state = addr_parts[1].strip() if len(addr_parts) > 1 else ""
        return await self.client.create_customer({
            "first_name": first_name,
            "last_name": last_name,
            "phone": phone,
            "email": email,
            "address": street,
            "city": city_state,
            "state": "",
            "zip_code": "",
        })

    async def schedule_appointment(self, customer_id: str, scheduled_start: str,
                                    scheduled_end: str, service_type: str,
                                    technician_id: str = "", notes: str = "") -> CRMAppointment:
        return await self.client.create_appointment({
            "customer_id": customer_id,
            "scheduled_start": scheduled_start,
            "scheduled_end": scheduled_end,
            "service_type": service_type,
            "technician_id": technician_id,
            "status": "scheduled",
            "notes": notes,
        })

    async def mark_job_complete(self, appt_id: str, notes: str = "") -> bool:
        return await self.client.update_appointment_status(appt_id, "completed")

    async def create_invoice_for_appointment(self, appt_id: str, customer_id: str,
                                              amount: float) -> CRMInvoice:
        return await self.client.create_invoice({
            "appointment_id": appt_id,
            "customer_id": customer_id,
            "amount": amount,
            "status": "pending",
        })


def register_crm_endpoints(app):
    from fastapi import Request, HTTPException
    from fastapi.responses import JSONResponse

    crm_service = CRMService()

    @app.get("/api/crm/customers")
    async def list_customers():
        return await crm_service.client._request("GET", "/customers")

    @app.post("/api/crm/customers")
    async def create_customer(request: Request):
        data = await request.json()
        cust = await crm_service.client.create_customer(data)
        return asdict(cust)

    @app.get("/api/crm/customers/{customer_id}")
    async def get_customer(customer_id: str):
        cust = await crm_service.client.get_customer(customer_id)
        if not cust:
            raise HTTPException(404, "Customer not found")
        return asdict(cust)

    @app.post("/api/crm/appointments")
    async def create_appointment(request: Request):
        data = await request.json()
        appt = await crm_service.schedule_appointment(
            customer_id=data["customer_id"],
            scheduled_start=data["scheduled_start"],
            scheduled_end=data["scheduled_end"],
            service_type=data.get("service_type", "hvac_service"),
            technician_id=data.get("technician_id", ""),
            notes=data.get("notes", ""),
        )
        return asdict(appt)

    @app.put("/api/crm/appointments/{appt_id}/complete")
    async def complete_appointment(appt_id: str, request: Request):
        data = await request.json()
        success = await crm_service.mark_job_complete(appt_id, data.get("notes", ""))
        return {"success": success}

    @app.post("/api/crm/webhook")
    async def crm_webhook(request: Request):
        data = await request.json()
        event_type = data.get("event_type", data.get("type", "unknown"))
        return await crm_service.client.process_webhook(event_type, data)

    @app.get("/api/crm/health")
    async def crm_health():
        return {
            "status": "ok",
            "crm_type": CRM_TYPE,
            "mock_mode": crm_service.client.mock,
        }
