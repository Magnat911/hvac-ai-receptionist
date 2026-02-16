"""
HVAC AI v5.0 - Load Tests
Run: locust -f locustfile.py --host=http://localhost:8000
"""
from locust import HttpUser, task, between
import random

SCENARIOS = [
    "My furnace stopped working and it's 45 degrees inside",
    "I smell gas in my basement!",
    "I need to schedule a maintenance tune-up",
    "My AC is not cooling and it's 95 degrees",
    "How much does a repair visit cost?",
    "Can someone come today for an emergency?",
    "I'd like to schedule an appointment for next week",
    "My thermostat isn't working properly",
    "The heat pump is making a strange noise",
    "I need a filter replacement",
]

class HVACUser(HttpUser):
    wait_time = between(1, 3)

    @task(5)
    def chat(self):
        self.client.post("/api/chat", json={
            "text": random.choice(SCENARIOS),
            "session_id": f"load_test_{random.randint(1, 1000)}",
        })

    @task(2)
    def health(self):
        self.client.get("/health")

    @task(1)
    def emergency_analyze(self):
        self.client.post("/api/emergency/analyze", json={
            "text": random.choice(SCENARIOS),
        })

    @task(1)
    def simulate_call(self):
        self.client.post("/api/mock/simulate-call", json={
            "scenarios": [random.choice(SCENARIOS)],
        })
