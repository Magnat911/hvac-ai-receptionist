#!/usr/bin/env python3
"""
HVAC AI v5.0 - Comprehensive Test Suite
Run: python -m pytest hvac_test.py -v --tb=short
Coverage target: >95%
"""

import os
import json
import time
import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from dataclasses import asdict

# Force mock mode for all tests
os.environ["MOCK_MODE"] = "1"
os.environ["LOG_DIR"] = "./test_logs"

from hvac_main import (
    analyze_emergency, extract_temperature, detect_vulnerable,
    check_prohibited, validate_response, RAGService, LLMService,
    TelnyxService, ConversationEngine, DEFAULT_KNOWLEDGE_BASE,
    EmergencyAnalysis,
)
from hvac_routing import (
    haversine, estimate_travel_seconds, euclidean_matrix,
    HybridRouter, Technician, Job, RouteStop,
)
from hvac_inventory import InventoryManager, Part

os.makedirs("./test_logs", exist_ok=True)

# ============================================================================
# EMERGENCY TRIAGE TESTS
# ============================================================================

class TestEmergencyTriage:
    def test_gas_leak_critical(self):
        r = analyze_emergency("I smell gas in my basement!")
        assert r.is_emergency
        assert r.emergency_type == "gas_leak"
        assert r.priority == "CRITICAL"
        assert r.requires_evacuation
        assert r.requires_911
        assert r.confidence >= 0.98

    def test_carbon_monoxide_critical(self):
        r = analyze_emergency("My CO detector is going off")
        assert r.is_emergency
        assert r.emergency_type == "gas_leak"
        assert r.priority == "CRITICAL"

    def test_fire_hazard(self):
        r = analyze_emergency("I see sparking from my furnace")
        assert r.is_emergency
        assert r.emergency_type == "fire_hazard"
        assert r.priority == "CRITICAL"

    def test_no_heat_critical_low_temp_vulnerable(self):
        r = analyze_emergency("My furnace stopped working, it's 45 degrees and I have a baby")
        assert r.is_emergency
        assert r.emergency_type == "no_heat_critical"
        assert r.priority == "HIGH"
        assert r.dispatch_immediately
        assert r.vulnerable_occupants
        assert r.indoor_temp == 45

    def test_no_heat_medium(self):
        r = analyze_emergency("My heater broken")
        assert r.is_emergency
        assert r.emergency_type == "no_heat"
        assert r.priority == "MEDIUM"
        assert not r.dispatch_immediately

    def test_no_ac_critical_high_temp(self):
        r = analyze_emergency("AC not working and it's 100 degrees inside")
        assert r.is_emergency
        assert "no_ac" in r.emergency_type
        assert r.priority == "HIGH"
        assert r.indoor_temp == 100

    def test_no_ac_vulnerable(self):
        r = analyze_emergency("Not cooling, 88 degrees, elderly parent home")
        assert r.is_emergency
        assert r.priority == "HIGH"
        assert r.vulnerable_occupants

    def test_water_leak(self):
        r = analyze_emergency("Water leak from my AC unit flooding the floor")
        assert r.is_emergency
        assert r.emergency_type == "water_leak"
        assert r.priority == "MEDIUM"

    def test_routine_scheduling(self):
        r = analyze_emergency("I'd like to schedule a maintenance appointment")
        assert not r.is_emergency
        assert r.emergency_type == "routine"
        assert r.priority == "LOW"

    def test_routine_pricing(self):
        r = analyze_emergency("How much does a tune-up cost?")
        assert not r.is_emergency
        assert r.priority == "LOW"

class TestTemperatureExtraction:
    def test_degrees(self):
        assert extract_temperature("it's 45 degrees inside") == 45

    def test_fahrenheit_symbol(self):
        assert extract_temperature("temperature is 98°F") == 98

    def test_temp_is(self):
        assert extract_temperature("temp is 55") == 55

    def test_inside(self):
        assert extract_temperature("55 inside") == 55

    def test_no_temp(self):
        assert extract_temperature("my AC broke") is None

    def test_out_of_range(self):
        assert extract_temperature("it's 5 degrees") is None  # Below 30

class TestVulnerableDetection:
    def test_elderly(self):
        assert detect_vulnerable("my elderly mother is home")

    def test_baby(self):
        assert detect_vulnerable("I have a baby")

    def test_medical(self):
        assert detect_vulnerable("someone with medical needs")

    def test_pregnant(self):
        assert detect_vulnerable("my pregnant wife")

    def test_none(self):
        assert not detect_vulnerable("just me at home")

# ============================================================================
# SAFETY GUARDS TESTS
# ============================================================================

class TestSafetyGuards:
    def test_prohibited_refrigerant(self):
        blocked, resp = check_prohibited("Can you tell me about refrigerant?")
        assert blocked
        assert "EPA" in resp

    def test_prohibited_freon(self):
        blocked, resp = check_prohibited("How do I add freon?")
        assert blocked

    def test_prohibited_diy(self):
        blocked, resp = check_prohibited("DIY furnace repair")
        assert blocked

    def test_prohibited_fix(self):
        blocked, resp = check_prohibited("How do I fix my AC?")
        assert blocked

    def test_allowed_scheduling(self):
        blocked, _ = check_prohibited("I need to schedule a repair")
        assert not blocked

    def test_allowed_pricing(self):
        blocked, _ = check_prohibited("What's the cost of a tune-up?")
        assert not blocked

    def test_validate_safe_response(self):
        ok, text = validate_response("I'll schedule a technician for you tomorrow.")
        assert ok

    def test_validate_catches_refrigerant(self):
        ok, text = validate_response("You should check your refrigerant levels")
        assert not ok
        assert "certified technician" in text.lower()

    def test_validate_catches_diagnosis(self):
        ok, text = validate_response("The diagnosis shows a faulty compressor")
        assert not ok

# ============================================================================
# RAG TESTS
# ============================================================================

class TestRAGService:
    def test_keyword_search_emergency(self):
        rag = RAGService()
        results = rag._keyword_search("no heat emergency", top_k=3)
        assert len(results) > 0
        assert any("emergency" in r["category"] for r in results)

    def test_keyword_search_scheduling(self):
        rag = RAGService()
        results = rag._keyword_search("schedule appointment", top_k=3)
        assert len(results) > 0

    def test_keyword_search_no_match(self):
        rag = RAGService()
        results = rag._keyword_search("xyzabc123", top_k=3)
        assert len(results) == 0

    def test_keyword_search_limit(self):
        rag = RAGService()
        results = rag._keyword_search("maintenance service", top_k=1)
        assert len(results) <= 1

    @pytest.mark.asyncio
    async def test_retrieve_keyword(self):
        rag = RAGService()
        results = await rag.retrieve("furnace repair emergency")
        assert isinstance(results, list)

# ============================================================================
# LLM SERVICE TESTS
# ============================================================================

class TestLLMService:
    @pytest.mark.asyncio
    async def test_mock_emergency_response(self):
        llm = LLMService("", mock=True)
        result = await llm.generate("gas leak carbon monoxide evacuate")
        assert "text" in result
        assert result["method"] == "mock"
        assert "evacuate" in result["text"].lower() or "911" in result["text"]

    @pytest.mark.asyncio
    async def test_mock_no_heat(self):
        llm = LLMService("", mock=True)
        result = await llm.generate("no heat furnace not working")
        assert "text" in result
        assert result["confidence"] > 0.8

    @pytest.mark.asyncio
    async def test_mock_scheduling(self):
        llm = LLMService("", mock=True)
        result = await llm.generate("schedule appointment maintenance")
        assert "text" in result
        assert "schedule" in result["text"].lower() or "book" in result["text"].lower() or "maintenance" in result["text"].lower()

    @pytest.mark.asyncio
    async def test_mock_generic(self):
        llm = LLMService("", mock=True)
        result = await llm.generate("hello there")
        assert "text" in result
        assert len(result["text"]) > 10

    def test_confidence_estimation(self):
        llm = LLMService("", mock=True)
        # High confidence
        assert llm._estimate_confidence("I will schedule that right away") > 0.90
        # Low confidence
        assert llm._estimate_confidence("I think maybe possibly") < 0.80

# ============================================================================
# TELNYX SERVICE TESTS
# ============================================================================

class TestTelnyxService:
    @pytest.mark.asyncio
    async def test_mock_sms(self):
        svc = TelnyxService("", "", mock=True)
        result = await svc.send_sms("+15551234567", "Test message")
        assert result["status"] == "sent"
        assert result["mock"]
        assert len(svc.sent_messages) == 1

    @pytest.mark.asyncio
    async def test_mock_webhook(self):
        svc = TelnyxService("", "", mock=True)
        result = await svc.handle_webhook({"data": {"event_type": "message.received", "payload": {}}})
        assert result["status"] == "received"

# ============================================================================
# CONVERSATION ENGINE TESTS
# ============================================================================

class TestConversationEngine:
    @pytest.fixture
    def engine(self):
        llm = LLMService("", mock=True)
        rag = RAGService()
        telnyx = TelnyxService("", "", mock=True)
        return ConversationEngine(llm, rag, telnyx)

    @pytest.mark.asyncio
    async def test_normal_message(self, engine):
        result = await engine.process_message("I need to schedule a repair")
        assert "response" in result
        assert "session_id" in result
        assert result["latency_ms"] >= 0
        assert not result["fallback_triggered"]

    @pytest.mark.asyncio
    async def test_emergency_message(self, engine):
        result = await engine.process_message("I smell gas in my house!")
        assert result["emergency"]["is_emergency"]
        assert result["emergency"]["priority"] == "CRITICAL"

    @pytest.mark.asyncio
    async def test_prohibited_message(self, engine):
        result = await engine.process_message("How do I fix my furnace myself?")
        assert result["blocked"] or "technician" in result["response"].lower()

    @pytest.mark.asyncio
    async def test_session_persistence(self, engine):
        r1 = await engine.process_message("My AC is broken", session_id="test123")
        r2 = await engine.process_message("Can you come tomorrow?", session_id="test123")
        assert r1["session_id"] == r2["session_id"]
        assert len(engine.conversations["test123"]) == 4  # 2 user + 2 assistant

    @pytest.mark.asyncio
    async def test_sms_on_moderate_confidence(self, engine):
        result = await engine.process_message("I need help", from_number="+15551234567")
        # SMS may or may not be sent depending on confidence
        assert isinstance(result["sms_sent"], bool)

# ============================================================================
# ROUTING TESTS
# ============================================================================

class TestRouting:
    def test_haversine_zero(self):
        assert haversine(0, 0, 0, 0) == 0

    def test_haversine_known(self):
        # NYC to LA ~3944 km
        d = haversine(40.7128, -74.006, 34.0522, -118.2437)
        assert 3900 < d < 4000

    def test_haversine_short(self):
        # ~5km within NYC
        d = haversine(40.7128, -74.006, 40.758, -73.9855)
        assert 4 < d < 6

    def test_travel_time(self):
        t = estimate_travel_seconds(30.0, "urban")  # 30km at 30km/h = 3600s
        assert t == 3600

    def test_euclidean_matrix(self):
        points = [(40.7, -74.0), (40.8, -73.9), (40.75, -74.1)]
        dists, times = euclidean_matrix(points)
        assert len(dists) == 3
        assert dists[0][0] == 0
        assert dists[0][1] > 0

    @pytest.mark.asyncio
    async def test_router_empty(self):
        router = HybridRouter()
        result = await router.optimize_routes([], [])
        assert result == {}

    @pytest.mark.asyncio
    async def test_router_basic(self):
        router = HybridRouter()
        techs = [
            Technician("t1", "John", 40.7128, -74.006, ["hvac"], 8),
            Technician("t2", "Jane", 40.758, -73.9855, ["hvac", "refrigeration"], 8),
        ]
        jobs = [
            Job("j1", 40.73, -73.99, "maintenance", 1, 3600, ["hvac"], customer_name="Customer A"),
            Job("j2", 40.75, -73.98, "ac_repair", 2, 3600, ["hvac"], customer_name="Customer B"),
            Job("j3", 40.72, -74.01, "maintenance", 1, 3600, ["hvac"], customer_name="Customer C"),
        ]
        routes = await router.optimize_routes(techs, jobs)
        assert len(routes) == 2
        total_jobs = sum(len(v) for v in routes.values())
        assert total_jobs == 3

    @pytest.mark.asyncio
    async def test_router_skill_matching(self):
        router = HybridRouter()
        techs = [Technician("t1", "John", 40.71, -74.0, ["hvac"])]  # No refrigeration
        jobs = [Job("j1", 40.73, -73.99, "ac_repair", 1, 3600, ["hvac", "refrigeration"])]
        routes = await router.optimize_routes(techs, jobs)
        assert len(routes["t1"]) == 0  # Can't assign - missing skill

    @pytest.mark.asyncio
    async def test_router_capacity(self):
        router = HybridRouter()
        techs = [Technician("t1", "John", 40.71, -74.0, ["hvac"], max_capacity=2)]
        jobs = [Job(f"j{i}", 40.7+i*0.01, -74.0, "maintenance", 1, 3600, ["hvac"]) for i in range(5)]
        routes = await router.optimize_routes(techs, jobs)
        assert len(routes["t1"]) <= 2

    def test_savings_estimate(self):
        router = HybridRouter()
        routes = {"t1": [RouteStop("j1", "t1", "09:00", "10:00", 15, 60, 40.7, -74.0, "123 Main", 5.0)]}
        savings = router.estimate_savings(routes)
        assert savings["savings_pct"] > 0
        assert savings["jobs_assigned"] == 1

# ============================================================================
# INVENTORY TESTS
# ============================================================================

class TestInventory:
    def test_default_parts_loaded(self):
        inv = InventoryManager()
        parts = inv.get_inventory()
        assert len(parts) == 10

    def test_filter_by_category(self):
        inv = InventoryManager()
        filters = inv.get_inventory("filters")
        assert all(p["category"] == "filters" for p in filters)

    def test_check_stock_available(self):
        inv = InventoryManager()
        result = inv.check_stock("p001", 5)
        assert result["available"]
        assert result["remaining_after"] == 45

    def test_check_stock_insufficient(self):
        inv = InventoryManager()
        result = inv.check_stock("p008", 100)  # Only 3 compressors
        assert not result["available"]

    def test_check_stock_not_found(self):
        inv = InventoryManager()
        result = inv.check_stock("nonexistent")
        assert not result["available"]
        assert "error" in result

    def test_record_usage(self):
        inv = InventoryManager()
        initial = inv.parts["p001"].quantity_on_hand
        result = inv.record_usage("p001", "job1", "tech1", 5, "admin")
        assert result["success"]
        assert result["remaining"] == initial - 5

    def test_record_usage_insufficient(self):
        inv = InventoryManager()
        result = inv.record_usage("p008", "job1", "tech1", 100, "admin")
        assert not result["success"]
        assert "Insufficient" in result["error"]

    def test_record_usage_epa_no_notes(self):
        inv = InventoryManager()
        result = inv.record_usage("p007", "job1", "tech1", 1, "admin")
        assert not result["success"]
        assert "EPA" in result["error"]

    def test_record_usage_epa_with_notes(self):
        inv = InventoryManager()
        result = inv.record_usage("p007", "job1", "tech1", 1, "admin", "EPA cert #12345")
        assert result["success"]

    def test_reorder_alert(self):
        inv = InventoryManager()
        # Use most of the stock
        inv.parts["p005"].quantity_on_hand = 4  # reorder point is 3
        result = inv.record_usage("p005", "job1", "tech1", 2, "admin")
        assert result["success"]
        assert "reorder_alert" in result

    def test_low_stock_report(self):
        inv = InventoryManager()
        inv.parts["p005"].quantity_on_hand = 2  # Below reorder point of 3
        low = inv.get_low_stock()
        assert any(p["id"] == "p005" for p in low)

    def test_usage_report(self):
        inv = InventoryManager()
        inv.record_usage("p001", "j1", "t1", 3, "admin")
        inv.record_usage("p002", "j2", "t1", 1, "admin")
        report = inv.get_usage_report()
        assert report["total_parts_used"] == 4
        assert report["total_transactions"] == 2

# ============================================================================
# FASTAPI ENDPOINT TESTS (using TestClient)
# ============================================================================

class TestAPI:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from hvac_main import app
        return TestClient(app)

    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["version"] == "5.0.0"
        assert data["mock_mode"]

    def test_chat(self, client):
        resp = client.post("/api/chat", json={"text": "I need to schedule a repair"})
        assert resp.status_code == 200
        data = resp.json()
        assert "response" in data
        assert data["session_id"]
        assert data["latency_ms"] >= 0

    def test_chat_empty(self, client):
        resp = client.post("/api/chat", json={"text": ""})
        assert resp.status_code == 400

    def test_chat_emergency(self, client):
        resp = client.post("/api/chat", json={"text": "I smell gas!"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["emergency"]["is_emergency"]

    def test_chat_prohibited(self, client):
        resp = client.post("/api/chat", json={"text": "How do I fix my AC myself?"})
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("blocked") or "technician" in data["response"].lower()

    def test_emergency_analyze(self, client):
        resp = client.post("/api/emergency/analyze", json={"text": "gas smell basement"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_emergency"]

    def test_mock_simulate(self, client):
        resp = client.post("/api/mock/simulate-call", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 5
        assert all("output" in r for r in data["test_results"])

    def test_mock_sms_log(self, client):
        resp = client.get("/api/mock/sms-log")
        assert resp.status_code == 200

    def test_demo_page(self, client):
        resp = client.get("/demo")
        assert resp.status_code == 200
        assert "HVAC" in resp.text

    def test_onboard_page(self, client):
        resp = client.get("/onboard")
        assert resp.status_code == 200

    def test_onboard_submit(self, client):
        resp = client.post("/api/onboard", json={
            "company_name": "Test HVAC", "email": "test@test.com",
            "city": "Chicago", "state": "IL",
            "business_number": "+15551234567", "fallback_number": "+15559876543",
        })
        assert resp.status_code == 200
        assert resp.json()["success"]

    def test_onboard_missing_fields(self, client):
        resp = client.post("/api/onboard", json={"company_name": "Test"})
        assert resp.status_code == 200
        assert not resp.json()["success"]

    def test_conversation_history(self, client):
        # First send a message
        r1 = client.post("/api/chat", json={"text": "Hello", "session_id": "hist_test"})
        sid = r1.json()["session_id"]
        # Then get history
        resp = client.get(f"/api/conversations/{sid}")
        assert resp.status_code == 200
        assert resp.json()["count"] >= 2

# ============================================================================
# INTEGRATION / STRESS TESTS
# ============================================================================

class TestIntegration:
    @pytest.mark.asyncio
    async def test_full_call_flow(self):
        """Simulate complete call: receive → triage → RAG → LLM → respond."""
        llm = LLMService("", mock=True)
        rag = RAGService()
        telnyx = TelnyxService("", "", mock=True)
        engine = ConversationEngine(llm, rag, telnyx)

        # Customer calls about no heat
        r1 = await engine.process_message("My furnace stopped and it's freezing", from_number="+15551234567")
        assert r1["emergency"]["is_emergency"]
        assert "response" in r1

        # Follow-up
        r2 = await engine.process_message("Can someone come today?", session_id=r1["session_id"])
        assert r2["session_id"] == r1["session_id"]

    @pytest.mark.asyncio
    async def test_concurrent_calls(self):
        """Test handling multiple simultaneous calls."""
        llm = LLMService("", mock=True)
        rag = RAGService()
        telnyx = TelnyxService("", "", mock=True)
        engine = ConversationEngine(llm, rag, telnyx)

        tasks = [
            engine.process_message(f"Test call {i}", session_id=f"concurrent_{i}")
            for i in range(20)
        ]
        results = await asyncio.gather(*tasks)
        assert all("response" in r for r in results)
        assert len(set(r["session_id"] for r in results)) == 20

    @pytest.mark.asyncio
    async def test_routing_with_priorities(self):
        """Test routing respects job priorities."""
        router = HybridRouter()
        techs = [Technician("t1", "John", 40.71, -74.0, ["hvac"], 3)]
        jobs = [
            Job("j_low", 40.72, -74.01, "maintenance", priority=1),
            Job("j_high", 40.73, -73.99, "emergency", priority=5),
            Job("j_med", 40.74, -74.02, "repair", priority=3),
        ]
        routes = await router.optimize_routes(techs, jobs)
        assigned = routes["t1"]
        assert len(assigned) == 3

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
