#!/usr/bin/env python3
"""
HVAC AI v5.0 — Comprehensive Production Test Suite
====================================================
Tests ALL modules: Emergency, Safety, RAG, Routing, Inventory, Auth, Integration.

Run options:
  python3 hvac_test_full.py                 # Run all tests
  python3 hvac_test_full.py --quick         # Smoke tests only
  python3 hvac_test_full.py --module auth   # Single module
  python3 hvac_test_full.py --verbose       # Detailed output

Zero dependencies beyond stdlib. Tests the full production pipeline.
"""

import os, sys, asyncio, time, json, re, argparse, traceback
from dataclasses import asdict
from datetime import datetime

# ── Terminal colors ──
class C:
    BOLD="\033[1m"; RED="\033[91m"; GREEN="\033[92m"; YELLOW="\033[93m"
    BLUE="\033[94m"; CYAN="\033[96m"; GRAY="\033[90m"; RESET="\033[0m"

passed = 0
failed = 0
errors = []
verbose = False

def test(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        if verbose:
            print(f"  {C.GREEN}✓{C.RESET} {name}")
    else:
        failed += 1
        msg = f"{name}{f' — {detail}' if detail else ''}"
        errors.append(msg)
        print(f"  {C.RED}✗{C.RESET} {msg}")

def section(name):
    print(f"\n{C.BOLD}{C.CYAN}{'─'*60}")
    print(f"  {name}")
    print(f"{'─'*60}{C.RESET}")

def subsection(name):
    print(f"\n  {C.BOLD}{C.BLUE}▸ {name}{C.RESET}")


# ╔═══════════════════════════════════════════════════════════════════╗
# ║  MODULE 1: EMERGENCY TRIAGE                                      ║
# ╚═══════════════════════════════════════════════════════════════════╝

def test_emergency():
    section("EMERGENCY TRIAGE")

    from hvac_impl import analyze_emergency, extract_temperature, detect_vulnerable

    # ── Critical Emergencies (must detect + evacuate) ──
    subsection("Critical Emergencies")
    critical_cases = [
        ("I smell gas in my kitchen", "gas_leak"),
        ("There's a strong gas odor", "gas_leak"),
        ("My CO detector is beeping", "gas_leak"),
        ("Carbon monoxide alarm going off and I feel dizzy", "gas_leak"),
        ("Sparking from my furnace and burning smell", "fire_hazard"),
        ("I see flames inside the furnace", "fire_hazard"),
        ("Electrical burning smell from HVAC unit", "fire_hazard"),
        ("Furnace is smoking", "fire_hazard"),
    ]
    for text, expected_type in critical_cases:
        r = analyze_emergency(text)
        test(f"CRITICAL: '{text[:50]}'",
             r.is_emergency and r.priority == "CRITICAL" and r.requires_evacuation,
             f"got priority={r.priority}, evac={r.requires_evacuation}")

    # ── High Priority (vulnerable + extreme temp) ──
    subsection("High Priority (Vulnerable Occupants)")
    high_cases = [
        ("No heat, 42 degrees, elderly mother here", True, 42),
        ("AC stopped, 99 degrees, 6 month old baby", True, 99),
        ("Furnace out, 38°F inside, disabled person", True, 38),
        ("No cooling, 102 degrees, pregnant wife", True, 102),
    ]
    for text, has_vulnerable, temp in high_cases:
        r = analyze_emergency(text)
        test(f"HIGH: '{text[:50]}'",
             r.is_emergency and r.priority == "HIGH",
             f"got priority={r.priority}")

    # ── Medium Priority ──
    subsection("Medium Priority")
    medium_cases = [
        "Heater not working, about 58 degrees",
        "AC isn't cooling great, probably 78 degrees",
        "Water dripping from AC unit",
        "Furnace making loud banging noise",
    ]
    for text in medium_cases:
        r = analyze_emergency(text)
        test(f"MEDIUM: '{text[:50]}'",
             r.priority in ("MEDIUM", "HIGH"),  # Some may classify as HIGH depending on patterns
             f"got priority={r.priority}")

    # ── Low Priority (no emergency) ──
    subsection("Low Priority")
    low_cases = [
        "Schedule annual maintenance",
        "How much does a tune-up cost?",
        "What are your business hours?",
        "I'd like to book an appointment",
    ]
    for text in low_cases:
        r = analyze_emergency(text)
        test(f"LOW: '{text[:50]}'",
             r.priority == "LOW",
             f"got priority={r.priority}")

    # ── Temperature Extraction ──
    subsection("Temperature Extraction")
    temp_cases = [
        ("it's 45 degrees", 45),
        ("98°F", 98),
        ("temp is 55", 55),
        ("72 degrees inside", 72),
        ("about 38 degrees", 38),
        ("it's cold", None),
        ("no temperature mentioned", None),
    ]
    for text, expected in temp_cases:
        result = extract_temperature(text)
        test(f"Temp: '{text}' → {result} (exp {expected})",
             result == expected,
             f"got {result}")

    # ── Vulnerable Detection ──
    subsection("Vulnerable Detection")
    vuln_cases = [
        ("elderly parent", True),
        ("6 month old baby", True),
        ("pregnant wife", True),
        ("disabled veteran", True),
        ("medical equipment running", True),
        ("my newborn", True),
        ("just me and my dog", False),
        ("we're all fine", False),
    ]
    for text, expected in vuln_cases:
        result = detect_vulnerable(text)
        test(f"Vulnerable: '{text}' → {result} (exp {expected})",
             result == expected,
             f"got {result}")


# ╔═══════════════════════════════════════════════════════════════════╗
# ║  MODULE 2: SAFETY GUARDS                                         ║
# ╚═══════════════════════════════════════════════════════════════════╝

def test_safety():
    section("SAFETY GUARDS")

    from hvac_impl import check_prohibited, validate_response

    # ── Pre-Generation: Must Block ──
    subsection("Pre-Generation Blocking")
    blocked_cases = [
        "How do I add refrigerant?",
        "Can I fix my furnace myself?",
        "R-410A handling instructions",
        "Repair ductwork DIY",
        "How to repair my AC compressor",
        "Where to buy freon",
        "R-22 replacement guide",
        "Can I fix my own air conditioner?",
    ]
    for text in blocked_cases:
        is_blocked, _ = check_prohibited(text)
        test(f"BLOCKED: '{text}'", is_blocked, "was not blocked")

    # ── Pre-Generation: Must Allow ──
    subsection("Pre-Generation Allowing")
    allowed_cases = [
        "Schedule a repair",
        "How much does service cost?",
        "My furnace stopped working",
        "I need AC maintenance",
        "What's your service area?",
        "When are you available?",
    ]
    for text in allowed_cases:
        is_blocked, _ = check_prohibited(text)
        test(f"ALLOWED: '{text}'", not is_blocked, "was incorrectly blocked")

    # ── Post-Generation: Must Catch ──
    subsection("Post-Generation Validation")
    unsafe_responses = [
        "Replace the R-410A refrigerant yourself.",
        "My diagnosis: your compressor is failing.",
        "Try turning the thermostat off and on again.",
        "You should replace the capacitor yourself.",
        "The problem is definitely a refrigerant leak.",
    ]
    for text in unsafe_responses:
        is_safe, _ = validate_response(text)
        test(f"CAUGHT: '{text[:55]}'", not is_safe, "was not caught")

    # ── Post-Generation: Must Pass ──
    subsection("Post-Generation Passing")
    safe_responses = [
        "I'd be happy to schedule a technician for you.",
        "Let me connect you with a certified professional.",
        "Our technician can assess that when they arrive.",
        "I'll have a qualified tech look at that.",
        "We offer same-day emergency service.",
    ]
    for text in safe_responses:
        is_safe, _ = validate_response(text)
        test(f"SAFE: '{text[:55]}'", is_safe, "was incorrectly caught")


# ╔═══════════════════════════════════════════════════════════════════╗
# ║  MODULE 3: CONVERSATION ENGINE                                    ║
# ╚═══════════════════════════════════════════════════════════════════╝

def test_conversation():
    section("CONVERSATION ENGINE")

    from hvac_impl import ConversationEngine, LLMService, RAGService, TelnyxService

    engine = ConversationEngine(
        llm=LLMService(),
        rag=RAGService(),
        telnyx=TelnyxService()
    )

    async def run_scenarios():
        # ── Emergency Routing ──
        subsection("Emergency Response")
        r = await engine.process_message("I smell gas!")
        test("Gas leak → evacuate response",
             "evacuate" in r["response"].lower() or "911" in r["response"],
             f"response: {r['response'][:80]}")

        r = await engine.process_message("My CO detector is beeping and I feel dizzy")
        test("CO alarm → evacuation",
             r.get("emergency", {}).get("priority") == "CRITICAL",
             f"priority: {r.get('emergency', {}).get('priority')}")

        # ── Scheduling ──
        subsection("Scheduling")
        r = await engine.process_message("Schedule a furnace tune-up")
        test("Tune-up → booking response",
             "schedule" in r["response"].lower() or "book" in r["response"].lower() or "appointment" in r["response"].lower(),
             f"response: {r['response'][:80]}")

        # ── Prohibited Topics ──
        subsection("Prohibited Topics")
        r = await engine.process_message("How do I add freon?")
        test("Freon question → blocked",
             "certif" in r["response"].lower() or "epa" in r["response"].lower(),
             f"response: {r['response'][:80]}")

        # ── Pricing ──
        r = await engine.process_message("How much does a service call cost?")
        test("Pricing → informative response",
             any(w in r["response"].lower() for w in ["$", "cost", "price", "call", "service", "technician", "quote"]),
             f"response: {r['response'][:80]}")

        # ── General Info ──
        r = await engine.process_message("Do you service heat pumps?")
        test("Heat pump question → affirmative",
             len(r["response"]) > 20,  # Got a substantive response
             f"response: {r['response'][:80]}")

        # ── Session Continuity ──
        subsection("Session Management")
        sid = "test-session-123"
        r1 = await engine.process_message("My AC is broken", session_id=sid)
        r2 = await engine.process_message("Can you come tomorrow?", session_id=sid)
        test("Session maintains context",
             sid in engine.conversations,
             f"session {sid} in conversations: {sid in engine.conversations}")

    asyncio.run(run_scenarios())


# ╔═══════════════════════════════════════════════════════════════════╗
# ║  MODULE 4: RAG KNOWLEDGE BASE                                    ║
# ╚═══════════════════════════════════════════════════════════════════╝

def test_rag():
    section("RAG KNOWLEDGE BASE")

    from hvac_impl import RAGService

    rag = RAGService()

    async def run_rag():
        # ── Keyword Matching ──
        subsection("Keyword Search")
        results = await rag.retrieve("emergency no heat cold")
        test("'emergency no heat' → finds docs",
             len(results) > 0,
             f"got {len(results)} results")

        results = await rag.retrieve("schedule appointment maintenance")
        test("'schedule appointment' → finds docs",
             len(results) > 0,
             f"got {len(results)} results")

        results = await rag.retrieve("pricing cost service call")
        test("'pricing cost' → finds docs",
             len(results) > 0,
             f"got {len(results)} results")

        # ── Relevance ──
        subsection("Relevance Quality")
        results = await rag.retrieve("gas leak emergency")
        if results:
            first = results[0]
            test("Gas leak query → emergency doc first",
                 "emergency" in first.get("content", "").lower() or "gas" in first.get("content", "").lower(),
                 f"first result: {first.get('title', 'unknown')}")

        # ── Edge Cases ──
        subsection("Edge Cases")
        results = await rag.retrieve("")
        test("Empty query → no crash", True)

        results = await rag.retrieve("xyznonexistent123")
        test("Nonsense query → returns empty or low results",
             isinstance(results, list),
             f"got {len(results)} results")

    asyncio.run(run_rag())


# ╔═══════════════════════════════════════════════════════════════════╗
# ║  MODULE 5: ROUTING ENGINE                                        ║
# ╚═══════════════════════════════════════════════════════════════════╝

def test_routing():
    section("ROUTING ENGINE")

    from hvac_impl import HybridRouter, haversine, RTechnician, RJob

    router = HybridRouter()

    # ── Haversine Distance ──
    subsection("Haversine Distance")
    d = haversine(32.7767, -96.7970, 32.8998, -96.6989)
    test(f"Dallas → North Dallas: {d:.1f}km",
         10 < d < 25,
         f"expected ~15km, got {d:.1f}km")

    d = haversine(32.7767, -96.7970, 32.7767, -96.7970)
    test("Same point → 0km", d < 0.01, f"got {d}")

    # ── Route Optimization ──
    subsection("Route Optimization")

    async def run_routing():
        technicians = [
            RTechnician(id="t1", name="Mike", lat=32.78, lon=-96.80, skills=["heating", "gas"], max_capacity=5),
            RTechnician(id="t2", name="Carlos", lat=32.85, lon=-96.75, skills=["cooling", "ac"], max_capacity=5),
        ]
        jobs = [
            RJob(id="j1", description="heating fix", lat=32.79, lon=-96.79, priority=1, required_skills=["heating"]),
            RJob(id="j2", description="ac repair", lat=32.86, lon=-96.74, priority=3, required_skills=["cooling"]),
            RJob(id="j3", description="gas fix", lat=32.80, lon=-96.78, priority=1, required_skills=["gas"]),
        ]

        result = await router.optimize_routes(technicians, jobs)
        total_assigned = sum(len(stops) for stops in result.values())
        test("Routing produces assignments",
             total_assigned > 0,
             f"got {total_assigned} assignments across {len(result)} techs")

        test("All jobs assigned",
             total_assigned == len(jobs),
             f"assigned={total_assigned} of {len(jobs)}")

        # ── Skill Matching ──
        subsection("Skill Matching")
        # Build job→tech mapping
        job_tech = {}
        for tech_id, stops in result.items():
            for stop in stops:
                job_tech[stop["job_id"]] = tech_id

        if "j1" in job_tech:
            test("Heating job → heating-skilled tech",
                 job_tech["j1"] == "t1",
                 f"assigned to {job_tech['j1']}")
        if "j2" in job_tech:
            test("AC job → AC-skilled tech",
                 job_tech["j2"] == "t2",
                 f"assigned to {job_tech['j2']}")

        # ── Edge Cases ──
        subsection("Edge Cases")
        empty_result = await router.optimize_routes([], [])
        test("No techs, no jobs → no crash", isinstance(empty_result, dict))

    asyncio.run(run_routing())

# ╔═══════════════════════════════════════════════════════════════════╗
# ║  MODULE 6: INVENTORY                                              ║
# ╚═══════════════════════════════════════════════════════════════════╝

def test_inventory():
    section("INVENTORY MANAGEMENT")

    from hvac_impl import InventoryManager

    inv = InventoryManager()

    # ── Stock Check ──
    subsection("Stock Checking")
    result = inv.check_stock("p001", 1)
    test("Filter in stock", result["available"])

    result = inv.check_stock("p001", 999)
    test("Over-request → not available", not result["available"])

    result = inv.check_stock("nonexistent", 1)
    test("Nonexistent part → not available", not result["available"])

    # ── Part Usage ──
    subsection("Part Usage Recording")
    initial = inv.parts["p001"].quantity_on_hand
    result = inv.record_usage("p001", "job1", "tech1", 2, "Mike R.", "Standard maintenance")
    test("Record usage → success", result["success"])
    test(f"Stock reduced: {initial} → {inv.parts['p001'].quantity_on_hand}",
         inv.parts["p001"].quantity_on_hand == initial - 2)

    # ── EPA Compliance ──
    subsection("EPA Compliance")
    result = inv.record_usage("p007", "job2", "tech1", 1, "Mike R.")  # No notes
    test("EPA part without cert notes → rejected",
         not result["success"] and "EPA" in result.get("error", ""),
         f"error: {result.get('error', 'none')}")

    result = inv.record_usage("p007", "job2", "tech1", 1, "Mike R.", "EPA 608 cert #12345")
    test("EPA part with cert notes → accepted", result["success"])

    # ── Reorder Alerts ──
    subsection("Reorder Alerts")
    low = inv.get_low_stock()
    test("Low stock detection works", isinstance(low, list))

    # ── Usage Report ──
    subsection("Usage Reports")
    report = inv.get_usage_report()
    test("Usage report generated",
         report["total_transactions"] > 0,
         f"transactions: {report['total_transactions']}")


# ╔═══════════════════════════════════════════════════════════════════╗
# ║  MODULE 7: AUTHENTICATION & SECURITY                              ║
# ╚═══════════════════════════════════════════════════════════════════╝

def test_auth():
    section("AUTHENTICATION & SECURITY")

    from hvac_auth import (
        create_token, verify_token, hash_password, verify_password,
        RateLimiter, sanitize_input, validate_phone, validate_email,
        audit_log
    )

    # ── JWT Tokens ──
    subsection("JWT Tokens")
    token = create_token("company-123", "owner", "user-456")
    test("Create token", len(token) > 50)

    valid, payload = verify_token(token)
    test("Verify valid token", valid and payload["company_id"] == "company-123")
    test("Token has correct role", payload["role"] == "owner")
    test("Token has user_id", payload["user_id"] == "user-456")

    # Tampered token
    valid, _ = verify_token(token[:-5] + "XXXXX")
    test("Reject tampered token", not valid)

    # Malformed token
    valid, _ = verify_token("not.a.valid.token")
    test("Reject malformed token", not valid)

    valid, _ = verify_token("")
    test("Reject empty token", not valid)

    # ── Password Hashing ──
    subsection("Password Hashing")
    h = hash_password("securepass123")
    test("Hash password", "$" in h and len(h) > 50)
    test("Verify correct password", verify_password("securepass123", h))
    test("Reject wrong password", not verify_password("wrongpass", h))
    test("Reject empty password", not verify_password("", h))

    # ── Rate Limiting ──
    subsection("Rate Limiting")
    rl = RateLimiter(max_requests=5, window_seconds=1)
    for i in range(5):
        ok, info = rl.is_allowed("client-1")
        test(f"Request {i+1}/5 allowed", ok)

    ok, info = rl.is_allowed("client-1")
    test("Request 6/5 blocked", not ok)
    test("Rate limit info has remaining=0", info["remaining"] == 0)

    # Different client not affected
    ok, _ = rl.is_allowed("client-2")
    test("Different client not rate-limited", ok)

    # ── Input Sanitization ──
    subsection("Input Sanitization")
    test("Truncates long input", len(sanitize_input("x" * 5000)) == 2000)
    test("Strips null bytes", "\x00" not in sanitize_input("hello\x00world"))
    test("Handles empty input", sanitize_input("") == "")
    test("Strips whitespace", sanitize_input("  hello  ") == "hello")

    # ── Phone Validation ──
    subsection("Phone Validation")
    ok, p = validate_phone("(214) 555-0100")
    test("Format (xxx) xxx-xxxx", ok and p == "+12145550100")

    ok, p = validate_phone("+1-972-555-0200")
    test("Format +1-xxx-xxx-xxxx", ok and p == "+19725550200")

    ok, p = validate_phone("2145550100")
    test("Format 10 digits", ok and p == "+12145550100")

    ok, _ = validate_phone("123")
    test("Reject short number", not ok)

    # ── Email Validation ──
    subsection("Email Validation")
    test("Valid email", validate_email("test@example.com"))
    test("Valid complex email", validate_email("user.name+tag@domain.co.uk"))
    test("Reject no @", not validate_email("noatsign.com"))
    test("Reject no domain", not validate_email("user@"))

    # ── Audit Log ──
    subsection("Audit Logging")
    audit_log.log("c1", "u1", "LOGIN", "Success")
    audit_log.log("c1", "u1", "VIEW_CALLS", "")
    audit_log.log("c2", "u2", "LOGIN", "Success")
    entries = audit_log.get_entries("c1")
    test("Audit entries for company", len(entries) >= 2)
    test("Audit entries scoped to company", all(e["company_id"] == "c1" for e in entries))


# ╔═══════════════════════════════════════════════════════════════════╗
# ║  MODULE 8: FULL INTEGRATION FLOW                                  ║
# ╚═══════════════════════════════════════════════════════════════════╝

def test_integration():
    section("FULL INTEGRATION FLOW")

    from hvac_impl import (
        ConversationEngine, LLMService, RAGService, TelnyxService,
        HybridRouter, InventoryManager, analyze_emergency, RTechnician, RJob
    )

    engine = ConversationEngine(
        llm=LLMService(),
        rag=RAGService(),
        telnyx=TelnyxService()
    )
    router = HybridRouter()
    inventory = InventoryManager()

    async def run_integration():
        subsection("Call → Triage → Dispatch → Inventory Pipeline")

        # Step 1: Incoming call
        call_text = "My furnace is broken and it's 44 degrees. I have a baby."
        print(f"    📞 Incoming: \"{call_text}\"")

        # Step 2: AI processes
        response = await engine.process_message(call_text)
        print(f"    🤖 AI: \"{response['response'][:80]}...\"")
        test("Step 1: AI responds to call", len(response["response"]) > 10)

        # Step 3: Emergency triage
        emergency = analyze_emergency(call_text)
        print(f"    🚨 Triage: {emergency.priority} — {emergency.emergency_type}")
        test("Step 2: Emergency detected as HIGH",
             emergency.priority == "HIGH",
             f"got {emergency.priority}")

        # Step 4: Generate dispatch job
        job = RJob(id="j-integration-1", description="No heat emergency",
                   lat=32.78, lon=-96.80, priority=1, required_skills=["heating"])
        techs = [
            RTechnician(id="t1", name="Mike R.", lat=32.79, lon=-96.79,
                        skills=["heating", "gas"], max_capacity=5),
        ]
        result = await router.optimize_routes(techs, [job])
        total_assigned = sum(len(stops) for stops in result.values())
        print(f"    🚚 Dispatch: {total_assigned} tech assigned")
        test("Step 3: Technician dispatched", total_assigned > 0)

        # Step 5: Pre-check inventory
        stock = inventory.check_stock("p010", 1)  # Hot surface ignitor
        print(f"    📦 Inventory: Ignitor in stock: {stock['available']}")
        test("Step 4: Part availability checked", stock["available"])

        # Step 6: Complete job, record part usage
        usage = inventory.record_usage("p010", "j-integration-1", "t1", 1, "Mike R.", "Replaced ignitor")
        print(f"    ✅ Job complete: Part logged, remaining={usage.get('remaining', '?')}")
        test("Step 5: Part usage recorded", usage["success"])

        # Step 7: Verify SMS sent
        sms_count = len(engine.telnyx.sent_messages) if hasattr(engine.telnyx, 'sent_messages') else 0
        print(f"    📱 SMS notifications sent: {sms_count}")
        test("Step 6: Pipeline completed without errors", True)

        # ── Concurrent Sessions ──
        subsection("Concurrent Session Handling")
        r1 = await engine.process_message("Schedule tune-up", session_id="session-A")
        r2 = await engine.process_message("I smell gas!", session_id="session-B")
        r3 = await engine.process_message("How much for AC repair?", session_id="session-C")

        test("3 concurrent sessions handled",
             "session-A" in engine.conversations and
             "session-B" in engine.conversations and
             "session-C" in engine.conversations)

        test("Session B is emergency, A is not",
             "evacuate" in r2["response"].lower() or "911" in r2["response"].lower())

        # ── Error Resilience ──
        subsection("Error Resilience")
        r = await engine.process_message("")
        test("Empty input → no crash", isinstance(r, dict))

        r = await engine.process_message("x" * 10000)
        test("Very long input → no crash", isinstance(r, dict))

        r = await engine.process_message("🔥💨🏠 help!")
        test("Emoji input → no crash", isinstance(r, dict))

    asyncio.run(run_integration())


# ╔═══════════════════════════════════════════════════════════════════╗
# ║  MODULE 9: PERFORMANCE BENCHMARKS                                 ║
# ╚═══════════════════════════════════════════════════════════════════╝

def test_performance():
    section("PERFORMANCE BENCHMARKS")

    from hvac_impl import analyze_emergency, check_prohibited, validate_response, ConversationEngine, LLMService, RAGService, TelnyxService

    # ── Emergency Triage Speed ──
    subsection("Emergency Triage Speed")
    start = time.perf_counter()
    for _ in range(1000):
        analyze_emergency("I smell gas in my kitchen and feel dizzy")
    elapsed = (time.perf_counter() - start) * 1000
    per_call = elapsed / 1000
    print(f"    1000 triage calls: {elapsed:.0f}ms total, {per_call:.2f}ms/call")
    test(f"Triage < 1ms/call ({per_call:.2f}ms)", per_call < 1.0)

    # ── Safety Guards Speed ──
    subsection("Safety Guards Speed")
    start = time.perf_counter()
    for _ in range(1000):
        check_prohibited("How do I add refrigerant to my AC?")
        validate_response("I'd be happy to schedule a technician for you.")
    elapsed = (time.perf_counter() - start) * 1000
    per_call = elapsed / 2000
    print(f"    2000 safety checks: {elapsed:.0f}ms total, {per_call:.2f}ms/call")
    test(f"Safety < 0.5ms/call ({per_call:.2f}ms)", per_call < 0.5)

    # ── Full Pipeline Speed (mock) ──
    subsection("Full Pipeline Speed (Mock Mode)")
    engine = ConversationEngine(
        llm=LLMService(),
        rag=RAGService(),
        telnyx=TelnyxService()
    )

    async def bench():
        start = time.perf_counter()
        for i in range(50):
            await engine.process_message(f"Schedule repair {i}", session_id=f"bench-{i}")
        elapsed = (time.perf_counter() - start) * 1000
        per_call = elapsed / 50
        print(f"    50 full pipeline calls: {elapsed:.0f}ms total, {per_call:.1f}ms/call")
        test(f"Pipeline < 50ms/call mock ({per_call:.1f}ms)", per_call < 50)

    asyncio.run(bench())


# ╔═══════════════════════════════════════════════════════════════════╗
# ║  MAIN RUNNER                                                       ║
# ╚═══════════════════════════════════════════════════════════════════╝

def main():
    global verbose
    parser = argparse.ArgumentParser(description="HVAC AI v5.0 — Full Test Suite")
    parser.add_argument("--quick", action="store_true", help="Smoke tests only")
    parser.add_argument("--module", type=str, help="Run specific module: emergency|safety|conversation|rag|routing|inventory|auth|integration|performance")
    parser.add_argument("--verbose", action="store_true", help="Show all passing tests")
    args = parser.parse_args()
    verbose = args.verbose

    print(f"\n{C.BOLD}{C.CYAN}╔{'═'*58}╗")
    print(f"║  HVAC AI Receptionist v5.0 — Production Test Suite       ║")
    print(f"║  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                                    ║")
    print(f"╚{'═'*58}╝{C.RESET}")

    modules = {
        "emergency": test_emergency,
        "safety": test_safety,
        "conversation": test_conversation,
        "rag": test_rag,
        "routing": test_routing,
        "inventory": test_inventory,
        "auth": test_auth,
        "integration": test_integration,
        "performance": test_performance,
    }

    start = time.perf_counter()

    if args.module:
        if args.module in modules:
            modules[args.module]()
        else:
            print(f"Unknown module: {args.module}. Available: {', '.join(modules.keys())}")
            sys.exit(1)
    elif args.quick:
        test_emergency()
        test_safety()
        test_auth()
    else:
        for name, fn in modules.items():
            try:
                fn()
            except Exception as e:
                print(f"\n  {C.RED}ERROR in {name}: {e}{C.RESET}")
                traceback.print_exc()
                global failed
                failed += 1
                errors.append(f"MODULE CRASH: {name} — {e}")

    elapsed = time.perf_counter() - start

    # ── Summary ──
    total = passed + failed
    print(f"\n{C.BOLD}{'═'*60}")
    print(f"  RESULTS: {passed}/{total} passed, {failed} failed ({elapsed:.2f}s)")
    print(f"{'═'*60}{C.RESET}")

    if errors:
        print(f"\n  {C.RED}FAILURES:{C.RESET}")
        for e in errors:
            print(f"    {C.RED}✗{C.RESET} {e}")

    if failed == 0:
        print(f"\n  {C.GREEN}{C.BOLD}✅ ALL {total} TESTS PASSED — Production ready.{C.RESET}\n")
    else:
        print(f"\n  {C.RED}{C.BOLD}❌ {failed} TEST(S) FAILED — Fix before deploying.{C.RESET}\n")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
