#!/usr/bin/env python3
"""
HVAC AI v6.0 - Enhanced Inventory Tracking
===========================================
Real-time inventory sync with:
  - Truck inventory (parts in technician vehicles)
  - Job-part linking (track which parts were used on which jobs)
  - Supplier integration for auto-reordering
  - EPA compliance suite for refrigerant tracking
  - QR/Barcode scanning support
  - Mobile app sync capabilities
"""

import os
import logging
import uuid
import asyncio
import httpx
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
import json

logger = logging.getLogger("hvac-inventory")

# Configuration
MOCK_MODE = os.getenv("MOCK_MODE", "1") == "1"
SUPPLIER_API_URL = os.getenv("SUPPLIER_API_URL", "")
SUPPLIER_API_KEY = os.getenv("SUPPLIER_API_KEY", "")

# ============================================================================
# ENHANCED DATA MODELS
# ============================================================================

class PartCategory(str, Enum):
    FILTERS = "filters"
    CAPACITORS = "capacitors"
    MOTORS = "motors"
    CONTROLS = "controls"
    REFRIGERANT = "refrigerant"
    COMPRESSORS = "compressors"
    DUCTWORK = "ductwork"
    IGNITORS = "ignitors"
    TOOLS = "tools"
    CONSUMABLES = "consumables"

class EPAStatus(str, Enum):
    COMPLIANT = "compliant"
    WARNING = "warning"
    VIOLATION = "violation"

@dataclass
class Part:
    id: str
    sku: str
    name: str
    category: str
    quantity_on_hand: int
    reorder_point: int = 5
    unit_cost: float = 0.0
    location: str = "warehouse"
    epa_regulated: bool = False
    requires_certification: str = ""
    # New fields for v6.0
    supplier_id: str = ""
    supplier_sku: str = ""
    lead_time_days: int = 3
    min_order_qty: int = 1
    barcode: str = ""
    weight_lbs: float = 0.0
    last_restocked: str = ""
    last_used: str = ""

@dataclass
class PartUsage:
    id: str
    part_id: str
    job_id: str
    technician_id: str
    quantity_used: int
    recorded_by: str
    recorded_at: str
    notes: str = ""
    # New fields for v6.0
    truck_id: str = ""
    customer_id: str = ""
    cost_to_customer: float = 0.0
    warranty_part: bool = False
    epa_log_id: str = ""

@dataclass
class TruckInventory:
    """Parts inventory in a technician's vehicle."""
    truck_id: str
    technician_id: str
    technician_name: str
    location_lat: float = 0.0
    location_lon: float = 0.0
    last_sync: str = ""
    parts: Dict[str, int] = field(default_factory=dict)  # part_id -> quantity

@dataclass
class Supplier:
    """Supplier for auto-reordering."""
    id: str
    name: str
    api_url: str
    api_key: str = ""
    account_number: str = ""
    lead_time_days: int = 3
    free_shipping_min: float = 100.0
    active: bool = True

@dataclass
class PurchaseOrder:
    """Auto-generated purchase order."""
    id: str
    supplier_id: str
    status: str  # pending, submitted, confirmed, shipped, received
    items: List[Dict]  # [{part_id, sku, name, quantity, unit_cost}]
    total_cost: float
    created_at: str
    submitted_at: str = ""
    expected_delivery: str = ""
    tracking_number: str = ""

@dataclass
class EPARefrigerantLog:
    """EPA Section 608 compliance log for refrigerant tracking."""
    id: str
    date: str
    technician_id: str
    technician_cert_number: str
    refrigerant_type: str
    quantity_lbs: float
    job_id: str
    customer_name: str
    customer_address: str
    work_type: str  # installation, repair, recovery, disposal
    recovery_method: str = ""
    leak_check_passed: bool = True
    notes: str = ""

class InventoryManager:
    """Enhanced inventory with truck tracking, supplier integration, and EPA compliance."""

    def __init__(self, db_pool=None):
        self.db_pool = db_pool
        self.parts: Dict[str, Part] = {}
        self.usage_log: List[PartUsage] = []
        self.trucks: Dict[str, TruckInventory] = {}
        self.suppliers: Dict[str, Supplier] = {}
        self.purchase_orders: Dict[str, PurchaseOrder] = {}
        self.epa_logs: List[EPARefrigerantLog] = []
        self._load_defaults()

    def _load_defaults(self):
        """Load default parts, trucks, and suppliers."""
        # Default parts
        defaults = [
            Part("p001", "FLT-001", "Standard Air Filter 16x25x1", "filters", 50, 10, 12.99, "warehouse"),
            Part("p002", "FLT-002", "HEPA Filter 20x25x4", "filters", 20, 5, 34.99, "warehouse"),
            Part("p003", "CAP-001", "Run Capacitor 45/5 MFD", "capacitors", 15, 5, 18.50, "warehouse"),
            Part("p004", "CAP-002", "Start Capacitor 88-106 MFD", "capacitors", 10, 3, 22.00, "warehouse"),
            Part("p005", "MOT-001", "Condenser Fan Motor 1/4 HP", "motors", 8, 3, 89.99, "warehouse"),
            Part("p006", "THR-001", "Programmable Thermostat", "controls", 12, 4, 49.99, "warehouse"),
            Part("p007", "REF-001", "R-410A Refrigerant 25lb", "refrigerant", 6, 2, 149.99, "warehouse", True, "EPA 608"),
            Part("p008", "CMP-001", "Compressor 3-Ton", "compressors", 3, 1, 599.99, "warehouse"),
            Part("p009", "DUC-001", "Flex Duct 6\" x 25ft", "ductwork", 20, 5, 29.99, "warehouse"),
            Part("p010", "IGN-001", "Hot Surface Ignitor", "ignitors", 10, 3, 24.99, "warehouse"),
        ]
        for p in defaults:
            self.parts[p.id] = p

        # Default trucks
        self.trucks["truck_001"] = TruckInventory(
            truck_id="truck_001", technician_id="tech_001", technician_name="Mike Johnson",
            parts={"p001": 10, "p003": 5, "p010": 3}
        )
        self.trucks["truck_002"] = TruckInventory(
            truck_id="truck_002", technician_id="tech_002", technician_name="Sarah Williams",
            parts={"p001": 8, "p002": 2, "p003": 4, "p006": 2}
        )

        # Default supplier
        self.suppliers["sup_001"] = Supplier(
            id="sup_001", name="HVAC Supply Co.", api_url="https://api.hvacsupply.example.com",
            lead_time_days=2, free_shipping_min=150.0
        )

    # ========================================================================
    # BASIC INVENTORY OPERATIONS
    # ========================================================================

    def get_inventory(self, category: str = None) -> List[Dict]:
        parts = self.parts.values()
        if category:
            parts = [p for p in parts if p.category == category]
        return [asdict(p) for p in parts]

    def check_stock(self, part_id: str, quantity: int = 1) -> Dict:
        part = self.parts.get(part_id)
        if not part:
            return {"available": False, "error": "Part not found"}
        available = part.quantity_on_hand >= quantity
        return {
            "available": available,
            "part": asdict(part),
            "requested": quantity,
            "remaining_after": part.quantity_on_hand - quantity if available else 0,
            "needs_reorder": (part.quantity_on_hand - quantity) <= part.reorder_point if available else True,
        }

    def record_usage(self, part_id: str, job_id: str, tech_id: str,
                     quantity: int, recorded_by: str, notes: str = "",
                     truck_id: str = "", customer_id: str = "",
                     cost_to_customer: float = 0.0, warranty_part: bool = False) -> Dict:
        """Record part usage (human-confirmed only) with truck tracking."""
        part = self.parts.get(part_id)
        if not part:
            return {"success": False, "error": "Part not found"}

        # Check truck inventory if truck_id provided
        if truck_id:
            truck = self.trucks.get(truck_id)
            if not truck:
                return {"success": False, "error": f"Truck {truck_id} not found"}
            if truck.parts.get(part_id, 0) < quantity:
                return {"success": False, "error": f"Insufficient stock in truck: {truck.parts.get(part_id, 0)} available"}
        elif part.quantity_on_hand < quantity:
            return {"success": False, "error": f"Insufficient stock: {part.quantity_on_hand} available"}

        # EPA check
        if part.epa_regulated and not notes:
            return {"success": False, "error": "EPA-regulated part requires certification notes"}

        # Update inventory
        if truck_id:
            self.trucks[truck_id].parts[part_id] -= quantity
        else:
            part.quantity_on_hand -= quantity

        part.last_used = datetime.now(timezone.utc).isoformat()

        # Create usage record
        usage = PartUsage(
            id=f"use_{uuid.uuid4().hex[:8]}", part_id=part_id, job_id=job_id,
            technician_id=tech_id, quantity_used=quantity, recorded_by=recorded_by,
            recorded_at=datetime.now(timezone.utc).isoformat(), notes=notes,
            truck_id=truck_id, customer_id=customer_id, cost_to_customer=cost_to_customer,
            warranty_part=warranty_part,
        )
        self.usage_log.append(usage)
        logger.info(f"Part used: {part.name} x{quantity} for job {job_id} (truck: {truck_id or 'warehouse'})")

        result = {"success": True, "usage": asdict(usage), "remaining": part.quantity_on_hand}
        if part.quantity_on_hand <= part.reorder_point:
            result["reorder_alert"] = f"⚠️ {part.name} at {part.quantity_on_hand} units (reorder point: {part.reorder_point})"
        return result

    def get_low_stock(self) -> List[Dict]:
        return [asdict(p) for p in self.parts.values() if p.quantity_on_hand <= p.reorder_point]

    def get_usage_report(self, days: int = 30) -> Dict:
        total_used = sum(u.quantity_used for u in self.usage_log)
        by_part: Dict[str, int] = {}
        for u in self.usage_log:
            by_part[u.part_id] = by_part.get(u.part_id, 0) + u.quantity_used
        top_parts = sorted(by_part.items(), key=lambda x: x[1], reverse=True)[:5]
        return {
            "total_parts_used": total_used,
            "total_transactions": len(self.usage_log),
            "top_parts": [{"part_id": pid, "quantity": qty, "name": self.parts.get(pid, Part("","","","",0)).name}
                          for pid, qty in top_parts],
            "low_stock_count": len(self.get_low_stock()),
        }

    # ========================================================================
    # TRUCK INVENTORY MANAGEMENT
    # ========================================================================

    def get_truck_inventory(self, truck_id: str = None) -> List[Dict]:
        """Get inventory for all trucks or a specific truck."""
        if truck_id:
            truck = self.trucks.get(truck_id)
            if not truck:
                return []
            return [{
                "truck_id": truck.truck_id,
                "technician_id": truck.technician_id,
                "technician_name": truck.technician_name,
                "location": {"lat": truck.location_lat, "lon": truck.location_lon},
                "last_sync": truck.last_sync,
                "parts": [
                    {"part_id": pid, "quantity": qty, "part_name": self.parts.get(pid, Part("","","","",0)).name}
                    for pid, qty in truck.parts.items()
                ]
            }]
        return [
            {
                "truck_id": t.truck_id,
                "technician_id": t.technician_id,
                "technician_name": t.technician_name,
                "last_sync": t.last_sync,
                "total_parts": len(t.parts),
                "total_quantity": sum(t.parts.values())
            }
            for t in self.trucks.values()
        ]

    def sync_truck_inventory(self, truck_id: str, parts: Dict[str, int],
                              location: Tuple[float, float] = None) -> Dict:
        """Sync truck inventory from mobile app."""
        truck = self.trucks.get(truck_id)
        if not truck:
            return {"success": False, "error": f"Truck {truck_id} not found"}

        # Update parts
        for part_id, qty in parts.items():
            if part_id in self.parts:
                truck.parts[part_id] = qty

        # Update location
        if location:
            truck.location_lat, truck.location_lon = location

        truck.last_sync = datetime.now(timezone.utc).isoformat()
        logger.info(f"Truck {truck_id} inventory synced: {len(parts)} parts")

        return {
            "success": True,
            "truck_id": truck_id,
            "synced_at": truck.last_sync,
            "parts_count": len(truck.parts)
        }

    def transfer_part_to_truck(self, part_id: str, truck_id: str, quantity: int) -> Dict:
        """Transfer parts from warehouse to truck."""
        part = self.parts.get(part_id)
        truck = self.trucks.get(truck_id)
        if not part:
            return {"success": False, "error": "Part not found"}
        if not truck:
            return {"success": False, "error": f"Truck {truck_id} not found"}
        if part.quantity_on_hand < quantity:
            return {"success": False, "error": f"Insufficient warehouse stock: {part.quantity_on_hand} available"}

        part.quantity_on_hand -= quantity
        truck.parts[part_id] = truck.parts.get(part_id, 0) + quantity
        part.last_restocked = datetime.now(timezone.utc).isoformat()

        logger.info(f"Transferred {part.name} x{quantity} to truck {truck_id}")
        return {
            "success": True,
            "part": asdict(part),
            "truck_quantity": truck.parts[part_id],
            "warehouse_remaining": part.quantity_on_hand
        }

    # ========================================================================
    # SUPPLIER INTEGRATION & AUTO-REORDERING
    # ========================================================================

    async def check_supplier_availability(self, supplier_id: str, sku: str) -> Dict:
        """Check if a part is available from supplier."""
        if MOCK_MODE:
            return {"available": True, "quantity": 100, "price": 15.99, "lead_time_days": 2}

        supplier = self.suppliers.get(supplier_id)
        if not supplier:
            return {"available": False, "error": "Supplier not found"}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{supplier.api_url}/inventory/{sku}",
                    headers={"Authorization": f"Bearer {supplier.api_key}"}
                )
                if resp.status_code == 200:
                    return resp.json()
                return {"available": False, "error": f"API error: {resp.status_code}"}
        except Exception as e:
            logger.error(f"Supplier API error: {e}")
            return {"available": False, "error": str(e)}

    async def create_purchase_order(self, supplier_id: str, items: List[Dict],
                                     auto_submit: bool = False) -> Dict:
        """Create a purchase order for parts."""
        supplier = self.suppliers.get(supplier_id)
        if not supplier:
            return {"success": False, "error": "Supplier not found"}

        # Calculate total
        total_cost = sum(item.get("quantity", 1) * item.get("unit_cost", 0) for item in items)

        po = PurchaseOrder(
            id=f"po_{uuid.uuid4().hex[:8]}",
            supplier_id=supplier_id,
            status="pending",
            items=items,
            total_cost=total_cost,
            created_at=datetime.now(timezone.utc).isoformat(),
            expected_delivery=(datetime.now(timezone.utc) + timedelta(days=supplier.lead_time_days)).isoformat()
        )

        self.purchase_orders[po.id] = po

        if auto_submit:
            submit_result = await self._submit_po_to_supplier(po)
            if submit_result.get("success"):
                po.status = "submitted"
                po.submitted_at = datetime.now(timezone.utc).isoformat()

        logger.info(f"Created PO {po.id} for {len(items)} items, total ${total_cost:.2f}")
        return {"success": True, "purchase_order": asdict(po)}

    async def _submit_po_to_supplier(self, po: PurchaseOrder) -> Dict:
        """Submit purchase order to supplier API."""
        if MOCK_MODE:
            return {"success": True, "confirmation": f"CONF-{uuid.uuid4().hex[:8]}"}

        supplier = self.suppliers.get(po.supplier_id)
        if not supplier:
            return {"success": False, "error": "Supplier not found"}

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{supplier.api_url}/orders",
                    headers={"Authorization": f"Bearer {supplier.api_key}"},
                    json={
                        "po_number": po.id,
                        "items": po.items,
                        "shipping": "ground"
                    }
                )
                if resp.status_code in (200, 201):
                    data = resp.json()
                    return {"success": True, "confirmation": data.get("confirmation_number", "")}
                return {"success": False, "error": f"API error: {resp.status_code}"}
        except Exception as e:
            logger.error(f"Failed to submit PO: {e}")
            return {"success": False, "error": str(e)}

    def get_purchase_orders(self, status: str = None) -> List[Dict]:
        """Get all purchase orders, optionally filtered by status."""
        orders = [asdict(po) for po in self.purchase_orders.values()]
        if status:
            orders = [o for o in orders if o["status"] == status]
        return sorted(orders, key=lambda x: x["created_at"], reverse=True)

    async def auto_reorder_low_stock(self) -> Dict:
        """Automatically create purchase orders for low-stock items."""
        low_stock = self.get_low_stock()
        if not low_stock:
            return {"success": True, "orders_created": 0, "message": "No low-stock items"}

        # Group by supplier
        by_supplier: Dict[str, List[Dict]] = {}
        for part in low_stock:
            supplier_id = part.get("supplier_id") or "sup_001"  # Default supplier
            if supplier_id not in by_supplier:
                by_supplier[supplier_id] = []
            reorder_qty = max(part["reorder_point"] * 2, 10)  # Order at least 10 or 2x reorder point
            by_supplier[supplier_id].append({
                "part_id": part["id"],
                "sku": part["sku"],
                "name": part["name"],
                "quantity": reorder_qty,
                "unit_cost": part["unit_cost"]
            })

        # Create POs
        created = []
        for supplier_id, items in by_supplier.items():
            result = await self.create_purchase_order(supplier_id, items, auto_submit=True)
            if result.get("success"):
                created.append(result["purchase_order"]["id"])

        logger.info(f"Auto-reorder created {len(created)} POs for {len(low_stock)} low-stock items")
        return {
            "success": True,
            "orders_created": len(created),
            "po_ids": created,
            "items_reordered": len(low_stock)
        }

    # ========================================================================
    # EPA COMPLIANCE TRACKING
    # ========================================================================

    def log_refrigerant_usage(self, tech_id: str, tech_cert: str, refrigerant_type: str,
                               quantity_lbs: float, job_id: str, customer_name: str,
                               customer_address: str, work_type: str,
                               recovery_method: str = "", leak_check: bool = True,
                               notes: str = "") -> Dict:
        """Log refrigerant usage for EPA Section 608 compliance."""
        log = EPARefrigerantLog(
            id=f"epa_{uuid.uuid4().hex[:8]}",
            date=datetime.now(timezone.utc).isoformat(),
            technician_id=tech_id,
            technician_cert_number=tech_cert,
            refrigerant_type=refrigerant_type,
            quantity_lbs=quantity_lbs,
            job_id=job_id,
            customer_name=customer_name,
            customer_address=customer_address,
            work_type=work_type,
            recovery_method=recovery_method,
            leak_check_passed=leak_check,
            notes=notes
        )
        self.epa_logs.append(log)
        logger.info(f"EPA log: {refrigerant_type} {quantity_lbs}lbs by {tech_id} for {customer_name}")
        return {"success": True, "log_id": log.id, "log": asdict(log)}

    def get_epa_compliance_report(self, start_date: str = None, end_date: str = None) -> Dict:
        """Generate EPA compliance report for a date range."""
        logs = self.epa_logs
        if start_date:
            logs = [l for l in logs if l.date >= start_date]
        if end_date:
            logs = [l for l in logs if l.date <= end_date]

        total_refrigerant = sum(l.quantity_lbs for l in logs)
        by_type: Dict[str, float] = {}
        by_tech: Dict[str, float] = {}
        for l in logs:
            by_type[l.refrigerant_type] = by_type.get(l.refrigerant_type, 0) + l.quantity_lbs
            by_tech[l.technician_id] = by_tech.get(l.technician_id, 0) + l.quantity_lbs

        return {
            "report_period": {"start": start_date, "end": end_date},
            "total_transactions": len(logs),
            "total_refrigerant_lbs": total_refrigerant,
            "by_refrigerant_type": by_type,
            "by_technician": by_tech,
            "compliance_status": "compliant" if all(l.leak_check_passed for l in logs) else "review_required",
            "logs": [asdict(l) for l in logs]
        }

    def check_epa_compliance(self) -> Dict:
        """Check overall EPA compliance status."""
        if not self.epa_logs:
            return {"status": "no_data", "message": "No refrigerant usage logged"}

        failed_leak_checks = [l for l in self.epa_logs if not l.leak_check_passed]
        if failed_leak_checks:
            return {
                "status": "warning",
                "message": f"{len(failed_leak_checks)} failed leak checks require review",
                "failed_logs": [asdict(l) for l in failed_leak_checks]
            }

        return {
            "status": "compliant",
            "message": "All refrigerant usage properly logged and compliant",
            "total_logs": len(self.epa_logs),
            "last_log_date": max(l.date for l in self.epa_logs)
        }

    # ========================================================================
    # REAL-TIME SYNC ENDPOINTS
    # ========================================================================

    async def get_realtime_status(self) -> Dict:
        """Get real-time inventory status for dashboard."""
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "warehouse": {
                "total_parts": len(self.parts),
                "total_quantity": sum(p.quantity_on_hand for p in self.parts.values()),
                "total_value": sum(p.quantity_on_hand * p.unit_cost for p in self.parts.values()),
                "low_stock_count": len(self.get_low_stock())
            },
            "trucks": {
                "total_trucks": len(self.trucks),
                "total_parts_in_field": sum(sum(t.parts.values()) for t in self.trucks.values()),
                "last_sync": max((t.last_sync for t in self.trucks.values() if t.last_sync), default="never")
            },
            "purchase_orders": {
                "pending": len([po for po in self.purchase_orders.values() if po.status == "pending"]),
                "submitted": len([po for po in self.purchase_orders.values() if po.status == "submitted"]),
                "total_value": sum(po.total_cost for po in self.purchase_orders.values())
            },
            "epa_compliance": self.check_epa_compliance()
        }
