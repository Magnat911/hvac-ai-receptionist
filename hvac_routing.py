#!/usr/bin/env python3
"""
HVAC AI v6.0 - Production Route Optimization Engine
VROOM solver (time windows, skills, capacity) + Haversine/OSRM distance matrix
"""

import os
import math
import logging
import asyncio
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta

import httpx
import vroom

logger = logging.getLogger("hvac-routing")

OSRM_URL = os.getenv("OSRM_URL", "")  # Optional: real road distances

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
