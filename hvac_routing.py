#!/usr/bin/env python3
"""
HVAC AI v6.0 - Production Route Optimization Engine
VROOM solver (time windows, skills, capacity) + Haversine/OSRM distance matrix
+ Customer ETA Notifications (SMS/Email)
"""

import os
import math
import logging
import asyncio
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone

import httpx
import vroom

logger = logging.getLogger("hvac-routing")

OSRM_URL = os.getenv("OSRM_URL", "")  # Optional: real road distances
TELNYX_API_KEY = os.getenv("TELNYX_API_KEY", "")
TELNYX_PHONE = os.getenv("TELNYX_PHONE", "")
MOCK_MODE = os.getenv("MOCK_MODE", "1") == "1"

# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class Technician:
    id: str
    name: str
    lat: float
    lon: float
    skills: List[str] = field(default_factory=list)
    max_capacity: int = 8
    current_load: int = 0
    available_from: int = 8 * 3600   # 8 AM in seconds from midnight
    available_to: int = 18 * 3600    # 6 PM

@dataclass
class Job:
    id: str
    lat: float
    lon: float
    service_type: str
    priority: int = 1
    estimated_duration: int = 3600  # seconds
    required_skills: List[str] = field(default_factory=list)
    time_window_start: Optional[int] = None
    time_window_end: Optional[int] = None
    customer_name: str = ""
    address: str = ""

@dataclass
class RouteStop:
    job_id: str
    technician_id: str
    arrival_time: str
    departure_time: str
    travel_minutes: int
    service_minutes: int
    lat: float
    lon: float
    address: str
    distance_km: float = 0.0

@dataclass
class CustomerNotification:
    """Customer notification for ETA updates."""
    id: str
    job_id: str
    customer_name: str
    customer_phone: str
    technician_name: str
    eta_minutes: int
    message: str
    sent_at: str
    status: str  # pending, sent, delivered, failed
    notification_type: str  # eta_update, on_my_way, arrived, completed

@dataclass
class JobWithCustomer(Job):
    """Extended job with customer contact info for notifications."""
    customer_phone: str = ""
    customer_email: str = ""
    notify_on_dispatch: bool = True
    notify_on_en_route: bool = True
    notify_on_arrival: bool = True
    notify_on_completed: bool = True

SKILL_MAP = {
    "ac_repair": ["hvac", "refrigeration"],
    "furnace_repair": ["hvac", "heating"],
    "heat_pump": ["hvac", "heat_pump_certified"],
    "maintenance": ["hvac"],
    "emergency": ["hvac", "emergency_certified"],
    "installation": ["hvac", "install_certified"],
}

# Skill string → integer ID mapping for VROOM
_SKILL_IDS: Dict[str, int] = {}
_next_skill_id = 1

def _skill_to_id(skill_name: str) -> int:
    global _next_skill_id
    if skill_name not in _SKILL_IDS:
        _SKILL_IDS[skill_name] = _next_skill_id
        _next_skill_id += 1
    return _SKILL_IDS[skill_name]

def _skills_to_set(skills: List[str]) -> set:
    return {_skill_to_id(s) for s in skills}

# ============================================================================
# DISTANCE CALCULATIONS
# ============================================================================

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in km."""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def estimate_travel_seconds(distance_km: float, profile: str = "urban") -> int:
    speeds = {"urban": 30, "suburban": 45, "highway": 65, "rush_hour": 20}
    return int((distance_km / speeds.get(profile, 30)) * 3600)

def build_duration_matrix(points: List[Tuple[float, float]], profile: str = "urban") -> List[List[int]]:
    """Build duration matrix (seconds) from coordinate pairs."""
    n = len(points)
    matrix = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i != j:
                d = haversine(points[i][0], points[i][1], points[j][0], points[j][1])
                matrix[i][j] = estimate_travel_seconds(d, profile)
    return matrix

def build_distance_matrix(points: List[Tuple[float, float]]) -> List[List[float]]:
    """Build distance matrix (km) from coordinate pairs."""
    n = len(points)
    matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i != j:
                matrix[i][j] = haversine(points[i][0], points[i][1], points[j][0], points[j][1])
    return matrix

# ============================================================================
# OSRM CLIENT (optional real road distances)
# ============================================================================

async def osrm_duration_matrix(points: List[Tuple[float, float]]) -> Optional[List[List[int]]]:
    """Get real road durations from OSRM. Returns None on failure."""
    if not OSRM_URL:
        return None
    coords = ";".join(f"{lon},{lat}" for lat, lon in points)
    url = f"{OSRM_URL}/table/v1/driving/{coords}?annotations=duration"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == "Ok":
                    return [[int(v) for v in row] for row in data["durations"]]
        logger.warning("OSRM unavailable, using Haversine")
    except Exception as e:
        logger.error(f"OSRM error: {e}")
    return None

# ============================================================================
# VROOM-BASED ROUTER
# ============================================================================

class HybridRouter:
    """Production route optimizer using VROOM solver.

    Supports: time windows, skill matching, capacity constraints, priority weighting.
    Falls back to greedy nearest-neighbor if VROOM fails.
    """

    def __init__(self):
        pass

    async def optimize_routes(
        self,
        technicians: List[Technician],
        jobs: List[Job],
        depot: Tuple[float, float] = (0.0, 0.0),
        profile: str = "urban",
    ) -> Dict[str, List[RouteStop]]:
        if not technicians or not jobs:
            return {}

        try:
            return await self._vroom_optimize(technicians, jobs, depot, profile)
        except Exception as e:
            logger.error(f"VROOM solver failed, using greedy fallback: {e}")
            return self._greedy_fallback(technicians, jobs, depot, profile)

    async def _vroom_optimize(
        self,
        technicians: List[Technician],
        jobs: List[Job],
        depot: Tuple[float, float],
        profile: str,
    ) -> Dict[str, List[RouteStop]]:
        # Build coordinate list: tech starts + job locations
        # Index mapping: tech_i → index i, job_j → index len(techs) + j
        all_points: List[Tuple[float, float]] = []
        tech_idx_map: Dict[str, int] = {}
        job_idx_map: Dict[str, int] = {}

        for i, t in enumerate(technicians):
            tech_idx_map[t.id] = len(all_points)
            all_points.append((t.lat, t.lon))

        for j, job in enumerate(jobs):
            job_idx_map[job.id] = len(all_points)
            all_points.append((job.lat, job.lon))

        # Build duration matrix
        osrm_matrix = await osrm_duration_matrix(all_points)
        duration_matrix = osrm_matrix if osrm_matrix else build_duration_matrix(all_points, profile)
        dist_matrix = build_distance_matrix(all_points)

        # Build VROOM problem
        problem = vroom.Input()

        # Add vehicles (technicians)
        vehicles = []
        for t in technicians:
            idx = tech_idx_map[t.id]
            remaining_cap = max(t.max_capacity - t.current_load, 0)
            v = vroom.Vehicle(
                id=idx,
                start=vroom.Location(index=idx),
                end=vroom.Location(index=idx),
                capacity=[remaining_cap],
                skills=_skills_to_set(t.skills) if t.skills else set(),
                time_window=vroom.TimeWindow(t.available_from, t.available_to),
            )
            vehicles.append(v)
        problem.add_vehicle(vehicles)

        # Add jobs
        vroom_jobs = []
        for job in jobs:
            idx = job_idx_map[job.id]
            tws = []
            if job.time_window_start is not None and job.time_window_end is not None:
                tws = [vroom.TimeWindow(job.time_window_start, job.time_window_end)]
            elif job.time_window_start is not None:
                tws = [vroom.TimeWindow(job.time_window_start, 23 * 3600)]

            req_skills = set()
            if job.required_skills:
                req_skills = _skills_to_set(job.required_skills)

            kwargs = dict(
                id=idx,
                location=vroom.Location(index=idx),
                service=job.estimated_duration,
                delivery=[1],  # Each job uses 1 capacity unit
                priority=min(max(job.priority, 0), 100),
                skills=req_skills,
            )
            if tws:
                kwargs["time_windows"] = tws
            j = vroom.Job(**kwargs)
            vroom_jobs.append(j)
        problem.add_job(vroom_jobs)

        # Set duration matrix
        problem.set_durations_matrix("car", duration_matrix)

        # Solve
        solution = problem.solve(exploration_level=5, nb_threads=2)

        # Parse solution into RouteStop objects
        routes: Dict[str, List[RouteStop]] = {t.id: [] for t in technicians}
        idx_to_tech = {tech_idx_map[t.id]: t for t in technicians}
        idx_to_job = {job_idx_map[j.id]: j for j in jobs}

        for _, row in solution.routes.iterrows():
            step_type = row["type"]
            if step_type != "job":
                continue

            vehicle_idx = int(row["vehicle_id"])
            job_idx = int(row["id"])
            arrival_secs = int(row["arrival"])
            service_secs = int(row["service"])
            duration_secs = int(row["duration"])

            tech = idx_to_tech.get(vehicle_idx)
            job = idx_to_job.get(job_idx)
            if not tech or not job:
                continue

            departure_secs = arrival_secs + service_secs
            arrival_time = (datetime.min + timedelta(seconds=arrival_secs)).strftime("%H:%M")
            departure_time = (datetime.min + timedelta(seconds=departure_secs)).strftime("%H:%M")

            # Calculate travel from previous stop
            prev_stops = routes[tech.id]
            if prev_stops:
                prev_idx = job_idx_map.get(prev_stops[-1].job_id, tech_idx_map[tech.id])
            else:
                prev_idx = tech_idx_map[tech.id]
            travel_secs = duration_matrix[prev_idx][job_idx] if prev_idx < len(duration_matrix) and job_idx < len(duration_matrix[0]) else 0
            dist_km = dist_matrix[prev_idx][job_idx] if prev_idx < len(dist_matrix) and job_idx < len(dist_matrix[0]) else 0.0

            stop = RouteStop(
                job_id=job.id,
                technician_id=tech.id,
                arrival_time=arrival_time,
                departure_time=departure_time,
                travel_minutes=travel_secs // 60,
                service_minutes=service_secs // 60,
                lat=job.lat,
                lon=job.lon,
                address=job.address,
                distance_km=round(dist_km, 1),
            )
            routes[tech.id].append(stop)

        assigned = sum(len(v) for v in routes.values())
        unassigned = int(solution.summary.unassigned)
        logger.info(f"VROOM: {assigned} jobs assigned, {unassigned} unassigned, cost={solution.summary.cost}")
        return routes

    def _greedy_fallback(
        self,
        technicians: List[Technician],
        jobs: List[Job],
        depot: Tuple[float, float],
        profile: str,
    ) -> Dict[str, List[RouteStop]]:
        """Greedy nearest-neighbor fallback if VROOM fails."""
        points = [(t.lat, t.lon) for t in technicians] + [(j.lat, j.lon) for j in jobs]
        duration_matrix = build_duration_matrix(points, profile)
        dist_matrix = build_distance_matrix(points)

        routes: Dict[str, List[RouteStop]] = {t.id: [] for t in technicians}
        assigned_jobs = set()
        tech_time = {t.id: t.available_from for t in technicians}
        tech_pos = {t.id: i for i, t in enumerate(technicians)}
        tech_load = {t.id: t.current_load for t in technicians}

        for _ in range(len(jobs)):
            best_cost = float("inf")
            best_tech = None
            best_ji = None

            for ji, job in enumerate(jobs):
                if ji in assigned_jobs:
                    continue
                jp = len(technicians) + ji
                for tech in technicians:
                    if tech_load[tech.id] >= tech.max_capacity:
                        continue
                    if job.required_skills and not all(s in tech.skills for s in job.required_skills):
                        continue
                    tp = tech_pos[tech.id]
                    cost = duration_matrix[tp][jp] / max(job.priority, 1)
                    if cost < best_cost:
                        best_cost = cost
                        best_tech = tech
                        best_ji = ji

            if best_tech is None or best_ji is None:
                break

            job = jobs[best_ji]
            jp = len(technicians) + best_ji
            tp = tech_pos[best_tech.id]
            travel_secs = duration_matrix[tp][jp]
            dist_km = dist_matrix[tp][jp]

            arrival_secs = tech_time[best_tech.id] + travel_secs
            departure_secs = arrival_secs + job.estimated_duration

            stop = RouteStop(
                job_id=job.id,
                technician_id=best_tech.id,
                arrival_time=(datetime.min + timedelta(seconds=arrival_secs)).strftime("%H:%M"),
                departure_time=(datetime.min + timedelta(seconds=departure_secs)).strftime("%H:%M"),
                travel_minutes=travel_secs // 60,
                service_minutes=job.estimated_duration // 60,
                lat=job.lat, lon=job.lon, address=job.address,
                distance_km=round(dist_km, 1),
            )
            routes[best_tech.id].append(stop)
            tech_time[best_tech.id] = departure_secs
            tech_pos[best_tech.id] = jp
            tech_load[best_tech.id] += 1
            assigned_jobs.add(best_ji)

        logger.info(f"Greedy fallback: {len(assigned_jobs)} jobs assigned")
        return routes

    def estimate_savings(self, routes: Dict[str, List[RouteStop]], naive_factor: float = 1.4) -> Dict:
        total_km = sum(s.distance_km for stops in routes.values() for s in stops)
        total_minutes = sum(s.travel_minutes for stops in routes.values() for s in stops)
        naive_km = total_km * naive_factor
        return {
            "optimized_km": round(total_km, 1),
            "naive_estimate_km": round(naive_km, 1),
            "savings_km": round(naive_km - total_km, 1),
            "savings_pct": round((1 - total_km / naive_km) * 100, 1) if naive_km > 0 else 0,
            "total_travel_minutes": total_minutes,
            "jobs_assigned": sum(len(v) for v in routes.values()),
        }

    async def reoptimize(
        self,
        technicians: List[Technician],
        existing_routes: Dict[str, List[RouteStop]],
        new_jobs: List[Job],
        completed_job_ids: set = None,
        depot: Tuple[float, float] = (0.0, 0.0),
    ) -> Dict[str, List[RouteStop]]:
        """Re-optimize mid-day: keep completed jobs, add new ones, drop cancelled."""
        completed = completed_job_ids or set()

        # Collect remaining jobs from existing routes
        remaining_jobs = []
        for tech_id, stops in existing_routes.items():
            for stop in stops:
                if stop.job_id not in completed:
                    remaining_jobs.append(Job(
                        id=stop.job_id,
                        lat=stop.lat, lon=stop.lon,
                        service_type="existing",
                        estimated_duration=stop.service_minutes * 60,
                        address=stop.address,
                    ))

        all_jobs = remaining_jobs + new_jobs

        # Update tech positions/loads based on completed work
        for tech in technicians:
            completed_count = sum(1 for s in existing_routes.get(tech.id, []) if s.job_id in completed)
            tech.current_load = completed_count

        return await self.optimize_routes(technicians, all_jobs, depot)


# ============================================================================
# CUSTOMER ETA NOTIFICATION SERVICE
# ============================================================================

class CustomerNotificationService:
    """Send ETA notifications to customers via SMS/Email."""

    def __init__(self):
        self.notifications: List[CustomerNotification] = []
        self.telnyx_api_key = TELNYX_API_KEY
        self.telnyx_phone = TELNYX_PHONE
        self.mock = MOCK_MODE or not TELNYX_API_KEY

    async def send_eta_notification(
        self,
        job_id: str,
        customer_name: str,
        customer_phone: str,
        technician_name: str,
        eta_minutes: int,
        notification_type: str = "eta_update"
    ) -> Dict:
        """Send ETA notification to customer."""
        # Build message based on type
        messages = {
            "eta_update": f"Hi {customer_name}, {technician_name} from HVAC Pro will arrive in approximately {eta_minutes} minutes. You'll receive another update when they're on their way.",
            "on_my_way": f"Hi {customer_name}, {technician_name} is on the way to your location! ETA: {eta_minutes} minutes. Address: We have your address on file.",
            "arrived": f"Hi {customer_name}, {technician_name} has arrived at your location and will be with you shortly.",
            "completed": f"Hi {customer_name}, your service has been completed. Thank you for choosing HVAC Pro! You'll receive a summary shortly."
        }

        message = messages.get(notification_type, messages["eta_update"])

        notification = CustomerNotification(
            id=f"notif_{job_id}_{notification_type}",
            job_id=job_id,
            customer_name=customer_name,
            customer_phone=customer_phone,
            technician_name=technician_name,
            eta_minutes=eta_minutes,
            message=message,
            sent_at=datetime.now(timezone.utc).isoformat(),
            status="pending",
            notification_type=notification_type
        )

        # Send SMS
        result = await self._send_sms(customer_phone, message)
        notification.status = "sent" if result.get("success") else "failed"
        self.notifications.append(notification)

        logger.info(f"ETA notification sent to {customer_name}: {notification_type} ({notification.status})")
        return {
            "success": result.get("success", False),
            "notification": asdict(notification),
            "mock": self.mock
        }

    async def _send_sms(self, to: str, body: str) -> Dict:
        """Send SMS via Telnyx."""
        if self.mock:
            logger.info(f"[MOCK] SMS to {to}: {body}")
            return {"success": True, "mock": True, "message_id": f"mock_{datetime.now().timestamp()}"}

        if not self.telnyx_api_key:
            return {"success": False, "error": "Telnyx API key not configured"}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    "https://api.telnyx.com/v2/messages",
                    headers={
                        "Authorization": f"Bearer {self.telnyx_api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "from": self.telnyx_phone,
                        "to": to,
                        "text": body
                    }
                )
                if resp.status_code in (200, 201):
                    data = resp.json()
                    return {"success": True, "message_id": data.get("data", {}).get("id", "")}
                return {"success": False, "error": f"API error: {resp.status_code}"}
        except Exception as e:
            logger.error(f"SMS send error: {e}")
            return {"success": False, "error": str(e)}

    async def send_dispatch_notifications(
        self,
        routes: Dict[str, List[RouteStop]],
        technician_map: Dict[str, Technician],
        job_customer_map: Dict[str, Dict]  # job_id -> {customer_name, customer_phone, ...}
    ) -> List[Dict]:
        """Send ETA notifications for all jobs in routes."""
        results = []
        for tech_id, stops in routes.items():
            tech = technician_map.get(tech_id)
            if not tech:
                continue

            for i, stop in enumerate(stops):
                customer_info = job_customer_map.get(stop.job_id, {})
                if not customer_info.get("customer_phone"):
                    continue

                # Calculate cumulative ETA
                eta_minutes = sum(s.travel_minutes for s in stops[:i+1])

                result = await self.send_eta_notification(
                    job_id=stop.job_id,
                    customer_name=customer_info.get("customer_name", "Customer"),
                    customer_phone=customer_info["customer_phone"],
                    technician_name=tech.name,
                    eta_minutes=eta_minutes,
                    notification_type="eta_update"
                )
                results.append(result)

        return results

    async def send_on_my_way(
        self,
        job_id: str,
        customer_name: str,
        customer_phone: str,
        technician_name: str,
        eta_minutes: int
    ) -> Dict:
        """Send 'technician is on the way' notification."""
        return await self.send_eta_notification(
            job_id=job_id,
            customer_name=customer_name,
            customer_phone=customer_phone,
            technician_name=technician_name,
            eta_minutes=eta_minutes,
            notification_type="on_my_way"
        )

    async def send_arrived_notification(
        self,
        job_id: str,
        customer_name: str,
        customer_phone: str,
        technician_name: str
    ) -> Dict:
        """Send 'technician has arrived' notification."""
        return await self.send_eta_notification(
            job_id=job_id,
            customer_name=customer_name,
            customer_phone=customer_phone,
            technician_name=technician_name,
            eta_minutes=0,
            notification_type="arrived"
        )

    async def send_completed_notification(
        self,
        job_id: str,
        customer_name: str,
        customer_phone: str,
        technician_name: str
    ) -> Dict:
        """Send 'job completed' notification."""
        return await self.send_eta_notification(
            job_id=job_id,
            customer_name=customer_name,
            customer_phone=customer_phone,
            technician_name=technician_name,
            eta_minutes=0,
            notification_type="completed"
        )

    def get_notification_history(self, job_id: str = None) -> List[Dict]:
        """Get notification history, optionally filtered by job."""
        notifs = self.notifications
        if job_id:
            notifs = [n for n in notifs if n.job_id == job_id]
        return [asdict(n) for n in notifs]


# ============================================================================
# ENHANCED ROUTER WITH NOTIFICATIONS
# ============================================================================

class RouterWithNotifications(HybridRouter):
    """Route optimizer with integrated customer notifications."""

    def __init__(self):
        super().__init__()
        self.notification_service = CustomerNotificationService()

    async def optimize_and_notify(
        self,
        technicians: List[Technician],
        jobs: List[JobWithCustomer],
        depot: Tuple[float, float] = (0.0, 0.0),
        profile: str = "urban",
        send_notifications: bool = True
    ) -> Dict:
        """Optimize routes and send ETA notifications."""
        # Optimize routes
        routes = await self.optimize_routes(technicians, jobs, depot, profile)

        # Calculate savings
        savings = self.estimate_savings(routes)

        # Build maps
        tech_map = {t.id: t for t in technicians}
        job_customer_map = {
            j.id: {
                "customer_name": j.customer_name,
                "customer_phone": j.customer_phone,
                "customer_email": j.customer_email,
                "notify_on_dispatch": j.notify_on_dispatch
            }
            for j in jobs
        }

        # Send notifications
        notifications = []
        if send_notifications:
            notifications = await self.notification_service.send_dispatch_notifications(
                routes, tech_map, job_customer_map
            )

        return {
            "routes": {k: [asdict(s) for s in v] for k, v in routes.items()},
            "savings": savings,
            "notifications_sent": len([n for n in notifications if n.get("success")]),
            "notifications": notifications
        }
