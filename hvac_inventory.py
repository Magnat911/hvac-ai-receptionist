#!/usr/bin/env python3
"""
HVAC AI v5.0 - Inventory Tracking
Human-confirmed part usage + automatic reorder alerts + EPA tracking (optional)
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict

logger = logging.getLogger("hvac-inventory")

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

class InventoryManager:
    """In-memory inventory (DB-backed in production)."""

    def __init__(self, db_pool=None):
        self.db_pool = db_pool
        self.parts: Dict[str, Part] = {}
        self.usage_log: List[PartUsage] = []
        self._load_defaults()

    def _load_defaults(self):
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
                     quantity: int, recorded_by: str, notes: str = "") -> Dict:
        """Record part usage (human-confirmed only)."""
        part = self.parts.get(part_id)
        if not part:
            return {"success": False, "error": "Part not found"}
        if part.quantity_on_hand < quantity:
            return {"success": False, "error": f"Insufficient stock: {part.quantity_on_hand} available"}

        # EPA check
        if part.epa_regulated and not notes:
            return {"success": False, "error": "EPA-regulated part requires certification notes"}

        part.quantity_on_hand -= quantity
        usage = PartUsage(
            id=f"use_{uuid.uuid4().hex[:8]}", part_id=part_id, job_id=job_id,
            technician_id=tech_id, quantity_used=quantity, recorded_by=recorded_by,
            recorded_at=datetime.now(timezone.utc).isoformat(), notes=notes,
        )
        self.usage_log.append(usage)
        logger.info(f"Part used: {part.name} x{quantity} for job {job_id}")

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
