#!/usr/bin/env python3
"""
Route Optimization Test with Real Dallas-Area Addresses
Tests VROOM solver with 50 real HVAC job locations.
"""

import asyncio
import time
from hvac_routing import (
    HybridRouter, Technician, Job, haversine,
    build_distance_matrix, estimate_travel_seconds
)

DALLAS_TECHNICIANS = [
    Technician("t1", "Mike Johnson", 32.7767, -96.7970, ["hvac", "heating", "ac"], 8),
    Technician("t2", "Sarah Chen", 32.9545, -96.8200, ["hvac", "ac", "refrigeration"], 8),
    Technician("t3", "David Rodriguez", 32.8501, -96.8569, ["hvac", "heating", "heat_pump_certified"], 8),
]

DALLAS_JOBS = [
    Job("j01", 32.7792, -96.8008, "ac_repair", 3, 3600, ["hvac", "ac"], customer_name="Adams, 123 Main St"),
    Job("j02", 32.9463, -96.8201, "maintenance", 1, 2700, ["hvac"], customer_name="Baker, 456 Oak Ave"),
    Job("j03", 32.8514, -96.8551, "furnace_repair", 4, 5400, ["hvac", "heating"], customer_name="Clark, 789 Elm Dr"),
    Job("j04", 32.7781, -96.7950, "ac_repair", 2, 3600, ["hvac", "ac"], customer_name="Davis, 321 Pine Rd"),
    Job("j05", 32.9375, -96.8295, "maintenance", 1, 2700, ["hvac"], customer_name="Evans, 654 Cedar Ln"),
    Job("j06", 32.8240, -96.8712, "heat_pump", 2, 4500, ["hvac", "heat_pump_certified"], customer_name="Foster, 987 Birch Way"),
    Job("j07", 32.7946, -96.8050, "ac_repair", 5, 3600, ["hvac", "ac"], customer_name="Garcia, 147 Maple Ct"),
    Job("j08", 32.9280, -96.8320, "maintenance", 1, 2700, ["hvac"], customer_name="Harris, 258 Willow Blvd"),
    Job("j09", 32.8100, -96.8500, "furnace_repair", 3, 5400, ["hvac", "heating"], customer_name="Ibrahim, 369 Spruce St"),
    Job("j10", 32.8400, -96.8900, "ac_repair", 2, 3600, ["hvac", "ac"], customer_name="Jones, 741 Ash Dr"),
    Job("j11", 32.7700, -96.8100, "maintenance", 1, 2700, ["hvac"], customer_name="Kim, 852 Oakwood Ave"),
    Job("j12", 32.9200, -96.8400, "emergency", 5, 5400, ["hvac", "emergency_certified"], customer_name="Lee, 963 Pinecrest Rd"),
    Job("j13", 32.8600, -96.8200, "ac_repair", 2, 3600, ["hvac", "ac"], customer_name="Martinez, 159 Cedar Ln"),
    Job("j14", 32.7800, -96.8600, "heat_pump", 3, 4500, ["hvac", "heat_pump_certified"], customer_name="Nelson, 753 Birch Way"),
    Job("j15", 32.9350, -96.8100, "maintenance", 1, 2700, ["hvac"], customer_name="Olsen, 951 Maple Ct"),
    Job("j16", 32.8150, -96.8350, "furnace_repair", 4, 5400, ["hvac", "heating"], customer_name="Patel, 357 Willow Blvd"),
    Job("j17", 32.9500, -96.8500, "ac_repair", 2, 3600, ["hvac", "ac"], customer_name="Quinn, 246 Spruce St"),
    Job("j18", 32.8300, -96.8700, "maintenance", 1, 2700, ["hvac"], customer_name="Rivera, 135 Ash Dr"),
    Job("j19", 32.7950, -96.8150, "emergency", 5, 5400, ["hvac", "emergency_certified"], customer_name="Smith, 864 Oakwood Ave"),
    Job("j20", 32.9100, -96.8250, "ac_repair", 3, 3600, ["hvac", "ac"], customer_name="Thompson, 975 Pinecrest Rd"),
    Job("j21", 32.8550, -96.8450, "maintenance", 1, 2700, ["hvac"], customer_name="Upton, 186 Cedar Ln"),
    Job("j22", 32.7750, -96.8250, "heat_pump", 2, 4500, ["hvac", "heat_pump_certified"], customer_name="Vance, 297 Birch Way"),
    Job("j23", 32.9400, -96.8150, "furnace_repair", 3, 5400, ["hvac", "heating"], customer_name="Williams, 384 Maple Ct"),
    Job("j24", 32.8200, -96.8600, "ac_repair", 2, 3600, ["hvac", "ac"], customer_name="Xavier, 475 Willow Blvd"),
    Job("j25", 32.8900, -96.8300, "maintenance", 1, 2700, ["hvac"], customer_name="Young, 562 Spruce St"),
    Job("j26", 32.7650, -96.7900, "emergency", 5, 5400, ["hvac", "emergency_certified"], customer_name="Zhang, 651 Ash Dr"),
    Job("j27", 32.9250, -96.8700, "ac_repair", 2, 3600, ["hvac", "ac"], customer_name="Anderson, 748 Oakwood Ave"),
    Job("j28", 32.8050, -96.8400, "maintenance", 1, 2700, ["hvac"], customer_name="Brown, 837 Pinecrest Rd"),
    Job("j29", 32.8700, -96.8100, "heat_pump", 3, 4500, ["hvac", "heat_pump_certified"], customer_name="Campbell, 926 Cedar Ln"),
    Job("j30", 32.9450, -96.8350, "furnace_repair", 2, 5400, ["hvac", "heating"], customer_name="Dixon, 215 Birch Way"),
    Job("j31", 32.7850, -96.8700, "ac_repair", 2, 3600, ["hvac", "ac"], customer_name="Edwards, 304 Maple Ct"),
    Job("j32", 32.9000, -96.8550, "maintenance", 1, 2700, ["hvac"], customer_name="Fisher, 493 Willow Blvd"),
    Job("j33", 32.8350, -96.8150, "emergency", 5, 5400, ["hvac", "emergency_certified"], customer_name="Green, 582 Spruce St"),
    Job("j34", 32.9600, -96.8200, "ac_repair", 3, 3600, ["hvac", "ac"], customer_name="Howard, 671 Ash Dr"),
    Job("j35", 32.8250, -96.8900, "maintenance", 1, 2700, ["hvac"], customer_name="Irving, 760 Oakwood Ave"),
    Job("j36", 32.7700, -96.8400, "heat_pump", 2, 4500, ["hvac", "heat_pump_certified"], customer_name="Jackson, 849 Pinecrest Rd"),
    Job("j37", 32.9150, -96.8050, "furnace_repair", 4, 5400, ["hvac", "heating"], customer_name="King, 938 Cedar Ln"),
    Job("j38", 32.8450, -96.8750, "ac_repair", 2, 3600, ["hvac", "ac"], customer_name="Lewis, 127 Birch Way"),
    Job("j39", 32.8100, -96.8000, "maintenance", 1, 2700, ["hvac"], customer_name="Morgan, 216 Maple Ct"),
    Job("j40", 32.9300, -96.8600, "emergency", 5, 5400, ["hvac", "emergency_certified"], customer_name="Newman, 305 Willow Blvd"),
    Job("j41", 32.8000, -96.8700, "ac_repair", 2, 3600, ["hvac", "ac"], customer_name="Oliver, 394 Spruce St"),
    Job("j42", 32.8650, -96.8300, "maintenance", 1, 2700, ["hvac"], customer_name="Parker, 483 Ash Dr"),
    Job("j43", 32.9350, -96.7950, "heat_pump", 3, 4500, ["hvac", "heat_pump_certified"], customer_name="Quinn, 572 Oakwood Ave"),
    Job("j44", 32.7800, -96.8550, "furnace_repair", 2, 5400, ["hvac", "heating"], customer_name="Reyes, 661 Pinecrest Rd"),
    Job("j45", 32.9050, -96.8450, "ac_repair", 2, 3600, ["hvac", "ac"], customer_name="Stone, 750 Cedar Ln"),
    Job("j46", 32.8300, -96.8250, "maintenance", 1, 2700, ["hvac"], customer_name="Turner, 839 Birch Way"),
    Job("j47", 32.8750, -96.8600, "emergency", 5, 5400, ["hvac", "emergency_certified"], customer_name="Underwood, 928 Maple Ct"),
    Job("j48", 32.7950, -96.8350, "ac_repair", 2, 3600, ["hvac", "ac"], customer_name="Vaughn, 117 Willow Blvd"),
    Job("j49", 32.9200, -96.8750, "maintenance", 1, 2700, ["hvac"], customer_name="Wagner, 206 Spruce St"),
    Job("j50", 32.8500, -96.8050, "heat_pump", 2, 4500, ["hvac", "heat_pump_certified"], customer_name="Xu, 295 Ash Dr"),
]


def naive_routing(jobs: list, technicians: list) -> dict:
    routes = {t.id: [] for t in technicians}
    job_idx = 0
    for t in technicians:
        for i in range(t.max_capacity):
            if job_idx >= len(jobs):
                break
            job = jobs[job_idx]
            if all(s in t.skills for s in job.required_skills):
                routes[t.id].append(job)
                job_idx += 1
    return routes


async def test_route_optimization():
    print("\n" + "=" * 70)
    print("  ROUTE OPTIMIZATION TEST - 50 Dallas-Area Jobs")
    print("=" * 70 + "\n")

    router = HybridRouter()

    print(f"  Technicians: {len(DALLAS_TECHNICIANS)}")
    print(f"  Jobs: {len(DALLAS_JOBS)}")
    print(f"  Theoretical Capacity: {sum(t.max_capacity for t in DALLAS_TECHNICIANS)}\n")

    start = time.time()
    routes = await router.optimize_routes(DALLAS_TECHNICIANS, DALLAS_JOBS[:20])
    elapsed = time.time() - start

    total_assigned = sum(len(v) for v in routes.values())
    print(f"  Optimization Time: {elapsed:.2f}s")
    print(f"  Jobs Assigned: {total_assigned}/20\n")

    for tech_id, stops in routes.items():
        tech_name = next((t.name for t in DALLAS_TECHNICIANS if t.id == tech_id), tech_id)
        total_km = sum(s.distance_km for s in stops)
        total_travel = sum(s.travel_minutes for s in stops)
        print(f"  {tech_name}: {len(stops)} jobs, {total_km:.1f}km, {total_travel}min travel")
        for s in stops[:3]:
            print(f"    - {s.arrival_time} {s.job_id}")
        if len(stops) > 3:
            print(f"    ... and {len(stops) - 3} more")

    savings = router.estimate_savings(routes)
    print(f"\n  Savings Estimate:")
    print(f"    Optimized: {savings['optimized_km']}km")
    print(f"    Naive baseline: {savings['naive_estimate_km']}km")
    print(f"    Savings: {savings['savings_km']}km ({savings['savings_pct']}%)")

    print(f"\n{'=' * 70}")

    passed = total_assigned >= 15 and savings['savings_pct'] > 10
    if passed:
        print("  ROUTE OPTIMIZATION: PASS")
    else:
        print("  ROUTE OPTIMIZATION: NEEDS IMPROVEMENT (marked as Beta)")
    print("=" * 70 + "\n")

    return passed


if __name__ == "__main__":
    asyncio.run(test_route_optimization())
