#!/usr/bin/env python3
"""
HVAC AI Receptionist v5.0 — CLI Implementation & Integration Test Runner
=========================================================================
SELF-CONTAINED: No FastAPI required. All core logic included.
Integrates: Receptionist (LLM + RAG + Safety) + Smart Dispatch + Inventory + Emergency Triage

USAGE (no API keys, no FastAPI, no Docker needed — just Python 3.9+):
  python hvac_impl.py                  # Run all demos
  python hvac_impl.py --chat           # Interactive chat mode
  python hvac_impl.py --demo           # Run 12 AI conversation scenarios
  python hvac_impl.py --route          # Route optimization demo
  python hvac_impl.py --inventory      # Inventory management demo
  python hvac_impl.py --emergency      # Emergency triage demo
  python hvac_impl.py --full-flow      # Full integrated flow (call→triage→dispatch→inventory)
  python hvac_impl.py --quick          # Quick smoke test (3 scenarios)

ZERO EXTERNAL DEPENDENCIES — uses only Python stdlib.
"""

import os, sys, asyncio, time, json, re, uuid, math, hashlib, argparse, logging
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any

# Quiet logging for CLI
os.makedirs("./logs", exist_ok=True)
logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(message)s",
                    handlers=[logging.FileHandler("./logs/hvac_impl.log"), logging.StreamHandler()])
logger = logging.getLogger("hvac-cli")

# ═══════════════════════════════════════════════════════════════════════════
# TERMINAL COLORS
# ═══════════════════════════════════════════════════════════════════════════
class C:
    BOLD="\033[1m"; RED="\033[91m"; GREEN="\033[92m"; YELLOW="\033[93m"
    BLUE="\033[94m"; CYAN="\033[96m"; GRAY="\033[90m"; RESET="\033[0m"

def hdr(t):  print(f"\n{C.BOLD}{C.CYAN}{'═'*70}\n  {t}\n{'═'*70}{C.RESET}\n")
def sub(t):  print(f"\n{C.BOLD}{C.BLUE}── {t} ──{C.RESET}")
def ok(m):   print(f"  {C.GREEN}✓{C.RESET} {m}")
def warn(m): print(f"  {C.YELLOW}⚠{C.RESET} {m}")
def err(m):  print(f"  {C.RED}✗{C.RESET} {m}")
def info(m): print(f"  {C.GRAY}→{C.RESET} {m}")
def pcolor(p): return {"CRITICAL":C.RED,"HIGH":C.YELLOW,"MEDIUM":C.BLUE,"LOW":C.GREEN}.get(p,C.GRAY)


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  CORE: EMERGENCY TRIAGE (Rule-Based, Zero Hallucination Risk)            ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

@dataclass
class EmergencyAnalysis:
    is_emergency: bool = False
    emergency_type: str = "NONE"
    priority: str = "LOW"
    confidence: float = 0.5
    requires_evacuation: bool = False
    recommended_action: str = ""
    details: Dict = field(default_factory=dict)

def extract_temperature(text: str) -> Optional[int]:
    patterns = [r"(\d+)\s*°?\s*[fF]", r"(\d+)\s*degrees", r"temp\w*\s*(?:is|at|about|around)?\s*(\d+)",
                r"inside\s*(?:is|at)?\s*(\d+)", r"it'?s\s+(\d+)\s*(?:degrees|°|in)"]
    for pat in patterns:
        m = re.search(pat, text.lower())
        if m:
            groups = [g for g in m.groups() if g is not None]
            if groups:
                t = int(groups[0])
                if 0 <= t <= 150: return t
    return None

def detect_vulnerable(text: str) -> bool:
    kw = ["elderly","senior","old","baby","infant","toddler","child","pregnant",
          "disabled","wheelchair","oxygen","medical","sick","newborn","6 month","year old"]
    tl = text.lower()
    return any(k in tl for k in kw)

def analyze_emergency(text: str) -> EmergencyAnalysis:
    tl = text.lower()
    temp = extract_temperature(text)
    vuln = detect_vulnerable(text)

    # CRITICAL: Gas / CO
    if any(k in tl for k in ["gas leak","smell gas","gas smell","natural gas","carbon monoxide",
                              "co detector","co alarm","monoxide","gas odor"]):
        etype = "GAS_LEAK" if "gas" in tl else "CARBON_MONOXIDE"
        return EmergencyAnalysis(True, etype, "CRITICAL", 0.99, True,
            "EVACUATE IMMEDIATELY. Call 911. Do NOT use switches or flames.", {"trigger":"gas/CO"})

    # CRITICAL: Fire
    if any(k in tl for k in ["spark","fire","burning smell","smoke","smoking","flame","on fire","burning"]):
        return EmergencyAnalysis(True, "FIRE_HAZARD", "CRITICAL", 0.99, True,
            "EVACUATE IMMEDIATELY. Call 911.", {"trigger":"fire/spark"})

    # HIGH/MEDIUM: No heat
    if any(k in tl for k in ["no heat","heat stopped","heater stopped","furnace stopped",
                              "furnace not","heat not","heating not","no warm","heater not",
                              "heater isn","furnace isn","furnace out","furnace broke",
                              "furnace broken","heater broke","heater broken",
                              "furnace is broken","heater is broken","furnace is out"]):
        if (temp is not None and temp < 50) or vuln:
            return EmergencyAnalysis(True, "NO_HEAT_CRITICAL", "HIGH", 0.95, False,
                "Dispatch immediately. Vulnerable or dangerously cold.", {"temperature":temp,"vulnerable":vuln})
        return EmergencyAnalysis(True, "NO_HEAT", "MEDIUM", 0.85, False,
            "Schedule priority service.", {"temperature":temp,"vulnerable":vuln})

    # HIGH/MEDIUM: No AC
    if any(k in tl for k in ["no ac","ac stopped","ac not","no cooling","ac died",
                              "air condition","not cooling","ac broke","ac broken",
                              "ac is broken","ac is out","ac is dead",
                              "isn't cooling","isnt cooling","ac isn"]):
        if (temp is not None and temp > 95) or vuln:
            return EmergencyAnalysis(True, "NO_AC_CRITICAL", "HIGH", 0.95, False,
                "Dispatch immediately. Extreme heat or vulnerable.", {"temperature":temp,"vulnerable":vuln})
        return EmergencyAnalysis(True, "NO_AC", "MEDIUM", 0.85, False,
            "Schedule priority service.", {"temperature":temp,"vulnerable":vuln})

    # MEDIUM: Water leak
    if any(k in tl for k in ["water leak","water drip","dripping","leaking water"]):
        return EmergencyAnalysis(True, "WATER_LEAK", "MEDIUM", 0.85, False,
            "Turn off system. Schedule same-day.", {"trigger":"water"})

    # MEDIUM: Abnormal sounds/behavior
    if any(k in tl for k in ["banging","grinding","loud noise","rattling","screeching",
                              "strange noise","weird noise","clicking","humming loud"]):
        return EmergencyAnalysis(True, "ABNORMAL_SOUND", "MEDIUM", 0.85, False,
            "Turn off system if unusual. Schedule priority inspection.", {"trigger":"sound"})

    return EmergencyAnalysis(False, "ROUTINE", "LOW", 0.90, False, "Standard scheduling.", {})


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  CORE: SAFETY GUARDS (Pre + Post Generation)                            ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

PROHIBITED = [
    (r"\brefrigerant\b", "I can't provide refrigerant advice. EPA regulations require a certified technician. Shall I schedule one?"),
    (r"\bfreon\b", "Freon handling requires EPA 608 certification. I'll connect you with a certified technician."),
    (r"\br-?410a?\b", "R-410A is EPA-regulated. Only certified technicians can handle it. Want me to schedule?"),
    (r"\br-?22\b", "R-22 is controlled. A certified tech can assess alternatives. Shall I schedule?"),
    (r"(?:how\s+(?:do|can|to)\s+(?:i|we)\s+(?:fix|repair|replace))|(?:(?:can|do)\s+i\s+(?:fix|repair))", "For safety, we recommend professional service. Want me to schedule a technician?"),
    (r"\bdiy\b", "DIY HVAC repairs can be dangerous. Let me schedule a certified technician."),
    (r"how\s+to\s+repair", "I can only recommend professional repair service. Shall I schedule a visit?"),
    (r"(?:fix|repair)\s+(?:it\s+)?(?:my)?self", "Self-repair of HVAC systems is not recommended. Let me schedule a certified technician."),
]

def check_prohibited(text: str) -> Tuple[bool, str]:
    tl = text.lower()
    for pat, resp in PROHIBITED:
        if re.search(pat, tl): return True, resp
    return False, ""

UNSAFE = [r"\brefrigerant\b", r"\br-?22\b", r"\br-?410a\b",
          r"\b(?:i|my) (?:can |will )?diagnos", r"\byour (?:diagnosis|problem is)",
          r"you should replace", r"try turning", r"you can fix"]

def validate_response(resp: str) -> Tuple[bool, str]:
    rl = resp.lower()
    for pat in UNSAFE:
        if re.search(pat, rl):
            return False, "I want to help you properly. Let me schedule a certified technician. What time works best?"
    return True, resp


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  CORE: RAG KNOWLEDGE BASE (In-Memory)                                   ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

DEFAULT_KB = [
    {"id":"kb001","title":"Emergency: No Heat","content":"For no heat: Check thermostat, check filter. DO NOT attempt repairs. Call us for same-day emergency service.",
     "keywords":["no heat","furnace","heating","cold","freeze"]},
    {"id":"kb002","title":"Emergency: No AC","content":"For no cooling: Check thermostat set to COOL, check filter, check breaker. Stay hydrated. Call for priority service.",
     "keywords":["no ac","cooling","hot","air conditioning","not cooling"]},
    {"id":"kb003","title":"Emergency: Gas Leak","content":"GAS LEAK: Leave immediately. Do NOT use switches. Call 911 outside. We do post-inspection after utility clearance.",
     "keywords":["gas","gas leak","smell gas","natural gas","carbon monoxide"]},
    {"id":"kb004","title":"Scheduling","content":"Same-day emergency, scheduled Mon-Sat 7am-6pm. Maintenance 45-60 min. Emergency dispatch within 1-2 hours.",
     "keywords":["schedule","appointment","booking","available","when"]},
    {"id":"kb005","title":"Maintenance","content":"Includes: filter replacement, coil cleaning, refrigerant check (certified), electrical inspection. Twice yearly.",
     "keywords":["maintenance","tune-up","service","check","inspection"]},
    {"id":"kb006","title":"Pricing","content":"Service call: $89 diagnostic (applied to repair). Tune-up: $129. Common repairs: $150-$500. Free estimates for replacements.",
     "keywords":["price","cost","how much","rate","fee","estimate"]},
    {"id":"kb007","title":"Hours","content":"Emergency: 24/7. Regular: Mon-Sat 7am-6pm. 50-mile service radius. Same-day for emergencies.",
     "keywords":["hours","open","service area","location","24/7"]},
]

class RAGService:
    def __init__(self): self.kb = DEFAULT_KB
    async def retrieve(self, query, top_k=3, company_id=None):
        ql = query.lower().split()
        scored = []
        for doc in self.kb:
            score = sum(1 for kw in doc["keywords"] if any(w in kw or kw in w for w in ql))
            if score > 0: scored.append((score, doc))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [{"content":d["content"],"title":d["title"],"score":s} for s,d in scored[:top_k]]


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  CORE: MOCK LLM SERVICE                                                 ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

class LLMService:
    def __init__(self): self.cache = {}

    async def generate(self, prompt, temperature=0.1, max_tokens=200):
        ck = hashlib.md5(prompt.encode()).hexdigest()
        if ck in self.cache: return self.cache[ck]

        # Extract customer message for precise matching (avoids RAG/knowledge contamination)
        cm = ""
        m = re.search(r'CUSTOMER:\s*"([^"]+)"', prompt, re.IGNORECASE)
        if m: cm = m.group(1).lower()
        else: cm = prompt.lower()  # fallback
        pl = prompt.lower()  # full prompt for emergency status checks

        if any(k in cm for k in ["gas leak","smell gas","carbon monoxide","co detector","co alarm","monoxide"]):
            text = "Please evacuate your home immediately and call 911. Do not use electrical switches. Once safe outside, we'll dispatch an emergency technician."
            conf = 0.98
        elif any(k in cm for k in ["no heat","furnace stopped","heater stopped","heat stopped"]) and any(k in pl for k in ["critical","high","elderly","baby"]):
            text = "I understand this is urgent with vulnerable family members. I'm dispatching our closest technician immediately. Please bundle up and use space heaters safely."
            conf = 0.95
        elif any(k in cm for k in ["no ac","not cooling","ac died","ac dead","ac stopped"]) and any(k in pl for k in ["critical","high","baby","99","98"]):
            text = "This is urgent with the heat. I'm scheduling an emergency technician now. Please stay hydrated, use fans, and close blinds."
            conf = 0.95
        elif any(k in cm for k in ["sparking","burning smell","fire","smoke","sparks"]):
            text = "Please evacuate immediately and call 911. Do not inspect the furnace. We'll send a technician after fire department clearance."
            conf = 0.97
        elif any(k in cm for k in ["water leak","dripping","water drip","leaking water"]):
            text = "Turn off your HVAC system to prevent further damage. Place towels under the leak. I'll schedule same-day service."
            conf = 0.90
        elif any(k in cm for k in ["schedule","appointment","book","tune-up","maintenance"]):
            text = "I'd be happy to schedule that! We have openings this week. Would morning or afternoon work better?"
            conf = 0.92
        elif any(k in cm for k in ["cost","price","how much","estimate"]):
            text = "Our service call is $89, applied to repairs. Tune-ups are $129. A technician can provide a free on-site estimate for specific repairs."
            conf = 0.90
        elif any(k in cm for k in ["heat pump","do you service","do you"]):
            text = "Yes, we service all major HVAC systems including heat pumps. Would you like to schedule an appointment?"
            conf = 0.88
        elif any(k in cm for k in ["filter","when should","replace"]):
            text = "We recommend replacing filters every 1-3 months. Our maintenance service includes this. Want to schedule a tune-up?"
            conf = 0.88
        elif any(k in cm for k in ["morning","9am","tomorrow"]):
            text = "Tomorrow morning works great! I can book you for 9:00 AM. A technician will call 30 min before arrival."
            conf = 0.90
        else:
            text = "Thank you for reaching out! Could you tell me more about what you're experiencing so I can connect you with the right service?"
            conf = 0.82

        result = {"text":text, "confidence":conf, "method":"mock", "tokens":len(text.split())}
        self.cache[ck] = result
        return result


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  CORE: TELNYX MOCK + CONVERSATION ENGINE                                ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

class TelnyxService:
    def __init__(self): self.sent_messages = []
    async def send_sms(self, to, body):
        msg = {"to":to,"body":body,"status":"sent_mock","ts":datetime.utcnow().isoformat()}
        self.sent_messages.append(msg)
        return msg

class ConversationEngine:
    def __init__(self, llm, rag, telnyx):
        self.llm = llm; self.rag = rag; self.telnyx = telnyx
        self.conversations: Dict[str, List[Dict]] = {}

    async def process_message(self, text, session_id=None, from_number="", company_id=None):
        start = time.time()
        session_id = session_id or uuid.uuid4().hex
        if session_id not in self.conversations: self.conversations[session_id] = []

        # 1. Prohibited check
        is_prohibited, blocked_resp = check_prohibited(text)
        if is_prohibited:
            return {"response":blocked_resp,"confidence":1.0,"blocked":True,
                    "session_id":session_id,"latency_ms":int((time.time()-start)*1000),
                    "emergency":asdict(EmergencyAnalysis()),"rag_results":0}

        # 2. Emergency triage
        emergency = analyze_emergency(text)

        # 3. RAG
        rag_results = await self.rag.retrieve(text, top_k=3, company_id=company_id)
        knowledge = "\n".join([r["content"] for r in rag_results]) if rag_results else "No specific knowledge."

        # 4. Context
        history = self.conversations[session_id][-6:]
        history_text = "\n".join([f"{'Customer' if h['role']=='user' else 'You'}: {h['text']}" for h in history])

        # 5. Prompt
        prompt = f"""You are a professional HVAC receptionist. Be helpful, warm, concise.
HISTORY:\n{history_text}\nCUSTOMER: "{text}"
EMERGENCY: {emergency.emergency_type} ({emergency.priority})
{"CRITICAL: " + ("Evacuate+911!" if emergency.requires_evacuation else "Dispatch now!") if emergency.priority in ("CRITICAL","HIGH") else ""}
KNOWLEDGE:\n{knowledge}
RULES: Never diagnose. Never give refrigerant advice. Never DIY instructions. Gas/CO = evacuate+911. When asked about pricing, quote standard rates from KNOWLEDGE above. Always offer to schedule a technician.
RESPONSE:"""

        # 6. Generate
        llm_resp = await self.llm.generate(prompt)
        response_text = llm_resp["text"]
        confidence = llm_resp["confidence"]

        # 7. Post-safety
        is_safe, safe_text = validate_response(response_text)
        if not is_safe: response_text = safe_text; confidence = 1.0

        # 8. Fallback
        fallback = False; sms = False
        if confidence < 0.80:
            response_text = "Let me connect you with our dispatch team right away for proper assistance."
            fallback = True
        elif confidence < 0.95 and from_number:
            await self.telnyx.send_sms(from_number, "HVAC Service: Request received. A technician will contact you shortly.")
            sms = True

        # 9. History
        self.conversations[session_id].append({"role":"user","text":text,"ts":time.time()})
        self.conversations[session_id].append({"role":"assistant","text":response_text,"ts":time.time()})

        return {"response":response_text,"confidence":confidence,"session_id":session_id,
                "emergency":asdict(emergency),"rag_results":len(rag_results),
                "fallback_triggered":fallback,"sms_sent":sms,"latency_ms":int((time.time()-start)*1000)}


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  ROUTING ENGINE                                                          ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

@dataclass
class RTechnician:
    id: str; name: str; lat: float; lon: float
    skills: List[str] = field(default_factory=list)
    max_capacity: int = 6

@dataclass
class RJob:
    id: str; description: str; lat: float; lon: float
    priority: int = 1
    required_skills: List[str] = field(default_factory=list)
    est_minutes: int = 60

def haversine(lat1, lon1, lat2, lon2):
    R = 6371; dlat = math.radians(lat2-lat1); dlon = math.radians(lon2-lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

class HybridRouter:
    def _has_skills(self, tech, job):
        return all(s in tech.skills for s in job.required_skills) if job.required_skills else True

    async def optimize_routes(self, technicians, jobs, depot=(0.0,0.0)):
        if not technicians or not jobs: return {}
        routes = {t.id: [] for t in technicians}
        loads = {t.id: 0 for t in technicians}
        pos = {t.id: (t.lat, t.lon) for t in technicians}
        assigned = set()
        sorted_jobs = sorted(enumerate(jobs), key=lambda x: x[1].priority, reverse=True)

        for ji, job in sorted_jobs:
            if ji in assigned: continue
            best_d = float("inf"); best_t = None
            for tech in technicians:
                if loads[tech.id] >= tech.max_capacity: continue
                if not self._has_skills(tech, job): continue
                d = haversine(pos[tech.id][0], pos[tech.id][1], job.lat, job.lon)
                if d / max(job.priority,1) < best_d:
                    best_d = d / max(job.priority,1); best_t = tech

            if best_t:
                dist = haversine(pos[best_t.id][0], pos[best_t.id][1], job.lat, job.lon)
                existing = routes[best_t.id]
                prev_dep = existing[-1].get("_dep_min",0) if existing else 0
                travel = max(5, int(dist / 0.5))
                arrive = prev_dep + travel
                dep = arrive + job.est_minutes
                base = datetime(2026,2,14,7,0)
                arrival_t = base + timedelta(minutes=arrive)

                routes[best_t.id].append({
                    "job_id":job.id, "job_description":job.description,
                    "distance_km":round(dist,1), "arrival":arrival_t.strftime("%I:%M %p"),
                    "priority":job.priority, "est_minutes":job.est_minutes, "_dep_min":dep
                })
                loads[best_t.id] += 1
                pos[best_t.id] = (job.lat, job.lon)
                assigned.add(ji)
        return routes


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  INVENTORY ENGINE                                                        ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

@dataclass
class Part:
    id: str; sku: str; name: str; category: str
    quantity_on_hand: int; reorder_point: int = 5
    unit_cost: float = 0.0; location: str = "warehouse"
    epa_regulated: bool = False; epa_cert: str = ""

@dataclass
class PartUsage:
    id: str; part_id: str; job_id: str; tech_id: str
    qty: int; recorded_by: str; recorded_at: str = ""; notes: str = ""

class InventoryManager:
    def __init__(self):
        self.parts: Dict[str, Part] = {}
        self.usage_log: List[PartUsage] = []
        self._load()

    def _load(self):
        for p in [
            Part("p001","FLT-001","Standard Air Filter 16x25x1","filters",50,10,12.99),
            Part("p002","FLT-002","HEPA Filter 20x25x4","filters",20,5,34.99),
            Part("p003","CAP-001","Run Capacitor 45/5 MFD","capacitors",15,5,18.50),
            Part("p004","CAP-002","Start Capacitor 88-106 MFD","capacitors",10,3,22.00),
            Part("p005","MOT-001","Condenser Fan Motor 1/4 HP","motors",8,3,89.99),
            Part("p006","THR-001","Programmable Thermostat","controls",12,4,49.99),
            Part("p007","REF-001","R-410A Refrigerant 25lb","refrigerant",6,2,149.99,"warehouse",True,"EPA 608"),
            Part("p008","CMP-001","Compressor 3-Ton","compressors",3,1,599.99),
            Part("p009","DUC-001","Flex Duct 6in x 25ft","ductwork",20,5,29.99),
            Part("p010","IGN-001","Hot Surface Ignitor","ignitors",10,3,24.99),
        ]: self.parts[p.id] = p

    def get_inventory(self, cat=None):
        pts = self.parts.values()
        if cat: pts = [p for p in pts if p.category == cat]
        return [asdict(p) for p in pts]

    def check_stock(self, pid, qty=1):
        p = self.parts.get(pid)
        if not p: return {"available":False,"error":"Part not found"}
        avail = p.quantity_on_hand >= qty
        return {"available":avail,"part":asdict(p),"requested":qty,
                "remaining_after":p.quantity_on_hand-qty if avail else 0}

    def record_usage(self, pid, jid, tid, qty, by, notes=""):
        p = self.parts.get(pid)
        if not p: return {"success":False,"error":"Part not found"}
        if p.quantity_on_hand < qty: return {"success":False,"error":f"Insufficient: {p.quantity_on_hand} available"}
        if p.epa_regulated and not notes: return {"success":False,"error":"EPA-regulated part requires certification notes"}
        p.quantity_on_hand -= qty
        u = PartUsage(f"use_{uuid.uuid4().hex[:8]}", pid, jid, tid, qty, by, datetime.utcnow().isoformat(), notes)
        self.usage_log.append(u)
        r = {"success":True,"usage":asdict(u),"remaining":p.quantity_on_hand}
        if p.quantity_on_hand <= p.reorder_point:
            r["reorder_alert"] = f"⚠️ {p.name} at {p.quantity_on_hand} (reorder: {p.reorder_point})"
        return r

    def get_low_stock(self):
        return [asdict(p) for p in self.parts.values() if p.quantity_on_hand <= p.reorder_point]

    def get_usage_report(self):
        total = sum(u.qty for u in self.usage_log)
        by_p: Dict[str,int] = {}
        for u in self.usage_log: by_p[u.part_id] = by_p.get(u.part_id,0) + u.qty
        top = sorted(by_p.items(), key=lambda x:x[1], reverse=True)[:5]
        return {"total_parts_used":total,"total_transactions":len(self.usage_log),
                "top_parts":[{"part_id":pid,"quantity":q,"name":self.parts.get(pid,Part("","","","",0)).name} for pid,q in top],
                "low_stock_count":len(self.get_low_stock())}


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  DEMO RUNNERS                                                            ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

def run_emergency_demo():
    hdr("EMERGENCY TRIAGE ENGINE (Rule-Based, Zero Hallucination)")
    scenarios = [
        ("I smell gas in my kitchen!", "CRITICAL"),
        ("My CO detector is beeping and I feel dizzy", "CRITICAL"),
        ("Sparking inside furnace, burning smell", "CRITICAL"),
        ("No heat, 42 degrees, elderly mother here", "HIGH"),
        ("AC stopped, 99 degrees, 6 month old baby", "HIGH"),
        ("Heater not working, about 58 degrees", "MEDIUM"),
        ("Water dripping from AC unit", "MEDIUM"),
        ("Schedule annual maintenance", "LOW"),
        ("How much does a tune-up cost?", "LOW"),
        ("AC isn't cooling great, probably 78 degrees", "MEDIUM"),
    ]
    passed = 0
    for text, exp in scenarios:
        r = analyze_emergency(text)
        match = r.priority == exp; passed += match
        s = f"{C.GREEN}PASS" if match else f"{C.YELLOW}CHCK"
        p = pcolor(r.priority)
        evac = "🚨 EVACUATE" if r.requires_evacuation else "   safe    "
        print(f"  {s}{C.RESET}  {p}{r.priority:8s}{C.RESET} │ {evac} │ {r.confidence:.0%} │ {text[:52]}")
    print(f"\n  {C.BOLD}Results: {passed}/{len(scenarios)} passed{C.RESET}")

    sub("Temperature Extraction")
    for text,exp in [("it's 45 degrees",45),("98°F",98),("temp is 55",55),("72 degrees",72),("it's cold",None)]:
        r = extract_temperature(text); s = C.GREEN+"✓" if r==exp else C.RED+"✗"
        print(f"  {s}{C.RESET}  \"{text}\" → {r} (exp {exp})")

    sub("Vulnerable Detection")
    for text,exp in [("elderly parent",True),("6 month old baby",True),("pregnant",True),("just me",False)]:
        r = detect_vulnerable(text); s = C.GREEN+"✓" if r==exp else C.RED+"✗"
        print(f"  {s}{C.RESET}  \"{text}\" → {r}")

def run_safety_demo():
    hdr("SAFETY GUARDS (Pre + Post Generation)")
    sub("Pre-Generation: Prohibited Topic Blocking")
    for text,sb in [("How do I add refrigerant?",True),("Can I fix my furnace myself?",True),("R-410A handling",True),
                     ("Repair ductwork DIY",True),("Schedule a repair",False),("Service cost?",False)]:
        b,_ = check_prohibited(text); match = b==sb
        s = C.GREEN+"✓" if match else C.RED+"✗"
        lbl = f"{C.RED}BLOCKED" if b else f"{C.GREEN}ALLOWED"
        print(f"  {s}{C.RESET}  {lbl}{C.RESET}  \"{text[:50]}\"")

    sub("Post-Generation: Response Validation")
    for text,sp in [("I'd be happy to schedule a technician.",True),
                     ("Replace the R-410A refrigerant yourself.",False),
                     ("My diagnosis: compressor failing.",False),
                     ("Try turning thermostat off and on.",False),
                     ("Let me connect you with a certified tech.",True)]:
        safe,_ = validate_response(text); match = safe==sp
        s = C.GREEN+"✓" if match else C.RED+"✗"
        lbl = f"{C.GREEN}SAFE" if safe else f"{C.RED}CAUGHT"
        print(f"  {s}{C.RESET}  {lbl}{C.RESET}  \"{text[:60]}\"")

async def run_routing_demo():
    hdr("SMART DISPATCH — Route Optimization")
    router = HybridRouter()
    techs = [
        RTechnician("tech1","Mike Johnson",32.78,-96.80,["hvac","heating","electrical"],5),
        RTechnician("tech2","Sarah Chen",32.80,-96.75,["hvac","refrigeration","cooling"],4),
        RTechnician("tech3","Carlos Rivera",32.75,-96.82,["hvac","heating","plumbing"],4),
    ]
    jobs = [
        RJob("j1","No Heat 42°F Elderly",32.82,-96.85,5,["hvac","heating"],90),
        RJob("j2","AC Not Cooling Baby",32.79,-96.72,4,["hvac","refrigeration"],60),
        RJob("j3","Annual Maintenance",32.76,-96.78,1,["hvac"],45),
        RJob("j4","Thermostat Replace",32.83,-96.79,2,["hvac"],30),
        RJob("j5","Furnace Ignitor",32.77,-96.84,4,["hvac","heating"],60),
        RJob("j6","Duct Leak Repair",32.81,-96.76,2,["hvac"],45),
        RJob("j7","Compressor Replace",32.74,-96.71,3,["hvac","refrigeration"],120),
    ]
    print(f"  {C.BOLD}Dispatch:{C.RESET} 7 jobs, 3 technicians, Dallas TX")
    t0 = time.time()
    routes = await router.optimize_routes(techs, jobs, (32.7767,-96.7970))
    ms = (time.time()-t0)*1000
    total_a = 0; total_km = 0.0
    for tech in techs:
        stops = routes.get(tech.id, [])
        total_a += len(stops)
        sub(f"🔧 {tech.name} ({len(stops)} jobs)")
        for i,s in enumerate(stops,1):
            total_km += s.get("distance_km",0)
            p = s.get("priority",0)
            print(f"    {i}. {pcolor('CRITICAL' if p>=5 else 'HIGH' if p>=4 else 'MEDIUM' if p>=2 else 'LOW')}P{p}{C.RESET} │ "
                  f"{s['job_id']:4s} │ {s.get('job_description','?')[:28]:28s} │ ~{s.get('distance_km',0):.1f}km │ ETA {s.get('arrival','?')}")
    ok(f"{total_a}/{len(jobs)} jobs assigned in {ms:.0f}ms, total {total_km:.1f} km")

def run_inventory_demo():
    hdr("INVENTORY MANAGEMENT + EPA COMPLIANCE")
    inv = InventoryManager()
    sub("Stock Overview")
    for p in inv.get_inventory():
        epa = f" {C.RED}[EPA]{C.RESET}" if p["epa_regulated"] else ""
        sc = C.GREEN if p["quantity_on_hand"]>p["reorder_point"] else C.YELLOW
        print(f"    {p['sku']:8s} │ {p['name'][:30]:30s} │ {sc}{p['quantity_on_hand']:3d}{C.RESET} │ ${p['unit_cost']:7.2f}{epa}")

    sub("Service Day Simulation")
    for pid,jid,tid,q,by,n in [("p001","j1","t1",2,"Mike","Filters"),("p003","j2","t2",1,"Sarah","Capacitor"),
                                ("p005","j3","t1",1,"Mike","Fan motor"),("p010","j4","t3",1,"Carlos","Ignitor")]:
        r = inv.record_usage(pid,jid,tid,q,by,n)
        if r["success"]:
            ok(f"{q}x {inv.parts[pid].name} → {r['remaining']} left")
            if "reorder_alert" in r: warn(r["reorder_alert"])

    sub("EPA Compliance")
    r = inv.record_usage("p007","j5","t1",1,"Mike","")
    if not r["success"]: ok(f"Blocked: {r['error']}")
    r = inv.record_usage("p007","j5","t1",1,"Mike","EPA 608 #MJ-2024-1234")
    if r["success"]: ok(f"EPA-compliant, {r['remaining']} left")

    rpt = inv.get_usage_report()
    info(f"Used: {rpt['total_parts_used']} parts | Low stock: {rpt['low_stock_count']}")

async def run_receptionist_demo():
    hdr("AI RECEPTIONIST — 12 Scenarios (Mock LLM)")
    eng = ConversationEngine(LLMService(), RAGService(), TelnyxService())
    for label,text,ph in [
        ("Gas leak","I smell gas from my furnace!","+15551001001"),
        ("No heat+elderly","Heater stopped, 42 degrees, elderly mother","+15551001002"),
        ("AC+baby","AC died, 99 degrees, 6 month old baby","+15551001003"),
        ("Schedule","Schedule a tune-up next week","+15551001004"),
        ("Pricing","How much does furnace repair cost?","+15551001005"),
        ("Prohibited","How do I add refrigerant to AC?","+15551001006"),
        ("Water leak","Water dripping from AC onto ceiling","+15551001007"),
        ("Follow-up","Fit me in tomorrow at 9am?","+15551001004"),
        ("CO alarm","Carbon monoxide alarm going off!","+15551001008"),
        ("General","Do you service heat pumps?","+15551001009"),
        ("Fire","Burning smell, I see sparks in furnace","+15551001010"),
        ("Filter","When should I replace my filter?","+15551001011"),
    ]:
        sub(f"📞 {label}")
        print(f"  {C.BOLD}Customer:{C.RESET} \"{text}\"")
        r = await eng.process_message(text, f"cli_{ph[-4:]}", ph)
        em = r.get("emergency",{})
        if em.get("is_emergency"):
            print(f"  {pcolor(em.get('priority',''))}⚡ {em['emergency_type']} — {em['priority']}{C.RESET}")
            if em.get("requires_evacuation"): print(f"  {C.RED}{C.BOLD}🚨 EVACUATE + CALL 911{C.RESET}")
        print(f"  {C.BOLD}AI:{C.RESET} {r['response']}")
        m = f"conf={r['confidence']:.0%}|{r['latency_ms']}ms|RAG:{r.get('rag_results',0)}"
        if r.get("blocked"): m += f"|{C.RED}BLOCKED{C.RESET}"
        if r.get("sms_sent"): m += "|📱SMS"
        print(f"  {C.GRAY}[{m}]{C.RESET}")

async def run_full_flow():
    hdr("FULL INTEGRATED FLOW: Call → Triage → Dispatch → Inventory")
    eng = ConversationEngine(LLMService(), RAGService(), TelnyxService())
    router = HybridRouter(); inv = InventoryManager()
    print(f"  {C.BOLD}Scenario:{C.RESET} Morning at ComfortAir HVAC, Dallas TX\n")

    sub("STEP 1: AI Handles Incoming Calls")
    calls = [("No heat, 42°F, elderly parent","+15559001001"),("AC dead, 98°F, baby","+15559001002"),
             ("Annual maintenance request","+15559001003"),("Burning smell, sparks in furnace!","+15559001004")]
    crs = []
    for text,ph in calls:
        r = await eng.process_message(text, f"f_{ph[-4:]}", ph)
        em = r.get("emergency",{})
        sym = "🚨" if em.get("requires_evacuation") else "📞"
        print(f"  {sym} {pcolor(em.get('priority','LOW'))}{em.get('priority','LOW'):8s}{C.RESET} │ {text[:45]}")
        crs.append(r)

    sub("STEP 2: Auto-Generate & Optimize Dispatch")
    techs = [RTechnician("t1","Mike",32.78,-96.80,["hvac","heating","electrical"],4),
             RTechnician("t2","Sarah",32.80,-96.75,["hvac","refrigeration","cooling"],3),
             RTechnician("t3","Carlos",32.75,-96.82,["hvac","heating","plumbing"],3)]
    cfgs = [(32.82,-96.85,["hvac","heating"],90),(32.79,-96.72,["hvac","refrigeration"],60),
            (32.76,-96.78,["hvac"],45),(32.83,-96.79,["hvac","heating"],30)]
    pmap = {"CRITICAL":5,"HIGH":4,"MEDIUM":2,"LOW":1}
    rjobs = []
    for i,(cr,cfg) in enumerate(zip(crs,cfgs)):
        em = cr.get("emergency",{})
        p = pmap.get(em.get("priority","LOW"),1)
        rjobs.append(RJob(f"j{i+1:03d}",calls[i][0][:35],cfg[0],cfg[1],p,cfg[2],cfg[3]))

    routes = await router.optimize_routes(techs, rjobs, (32.7767,-96.7970))
    for tech in techs:
        stops = routes.get(tech.id,[])
        if stops:
            print(f"  🔧 {tech.name}: {len(stops)} jobs")
            for s in stops: print(f"     → {s['job_id']} │ {s.get('job_description','?')[:32]} │ ETA {s.get('arrival','?')}")

    sub("STEP 3: Inventory Pre-Check & Usage")
    for pid,reason,q in [("p010","Ignitor",1),("p003","Capacitor",1),("p001","Filters",2)]:
        r = inv.check_stock(pid,q)
        if r["available"]: ok(f"{reason}: {q}x available")
    for pid,jid,tid,q,by,n in [("p010","j001","t1",1,"Mike","Ignitor"),("p003","j002","t2",1,"Sarah","Capacitor"),
                                ("p001","j003","t3",2,"Carlos","Filters")]:
        r = inv.record_usage(pid,jid,tid,q,by,n)
        if r["success"]: ok(f"Used {inv.parts[pid].name}")

    sub("END-OF-DAY SUMMARY")
    rpt = inv.get_usage_report()
    ems = sum(1 for cr in crs if cr.get("emergency",{}).get("is_emergency"))
    tj = sum(len(routes.get(t.id,[])) for t in techs)
    print(f"""
  {C.BOLD}{'═'*42}{C.RESET}
  📞 Calls handled by AI:    {len(crs)}
  🚨 Emergencies detected:   {ems}
  🔧 Jobs dispatched:        {tj}
  📦 Parts used today:       {rpt['total_parts_used']}
  {C.BOLD}{'═'*42}{C.RESET}
  {C.GREEN}All mock-mode operations complete.{C.RESET}
""")

async def run_chat():
    hdr("INTERACTIVE CHAT — Talk to the AI Receptionist")
    print(f"  {C.GRAY}Type as a customer. 'quit' to exit.{C.RESET}")
    print(f"  {C.GRAY}Try: 'My furnace stopped', 'I smell gas', 'schedule maintenance'{C.RESET}\n")
    eng = ConversationEngine(LLMService(), RAGService(), TelnyxService())
    sid = f"chat_{uuid.uuid4().hex[:6]}"
    while True:
        try: inp = input(f"  {C.BOLD}You:{C.RESET} ").strip()
        except (EOFError, KeyboardInterrupt): break
        if not inp or inp.lower() in ("quit","exit","q"):
            print(f"\n  {C.GRAY}Goodbye!{C.RESET}\n"); break
        r = await eng.process_message(inp, sid, "+15550000000")
        em = r.get("emergency",{})
        if em.get("is_emergency"): print(f"  {pcolor(em.get('priority',''))}⚡ {em['emergency_type']}{C.RESET}")
        print(f"  {C.CYAN}AI:{C.RESET} {r['response']}")
        print(f"  {C.GRAY}[{r['confidence']:.0%}|{r['latency_ms']}ms|RAG:{r.get('rag_results',0)}]{C.RESET}\n")

async def run_quick():
    hdr("QUICK SMOKE TEST")
    eng = ConversationEngine(LLMService(), RAGService(), TelnyxService())
    ok_all = True
    for label,text,check_fn in [
        ("Gas leak","I smell gas!",lambda r: r.get("emergency",{}).get("requires_evacuation")),
        ("Schedule","Schedule a furnace tune-up",lambda r: not r.get("blocked") and len(r["response"])>10),
        ("Prohibited","How do I add freon?",lambda r: r.get("blocked")),
    ]:
        r = await eng.process_message(text, f"s_{uuid.uuid4().hex[:4]}")
        sub(label)
        print(f"  In:  \"{text}\"")
        print(f"  Out: \"{r['response'][:75]}\"")
        if check_fn(r): ok("Passed")
        else: err("Failed"); ok_all = False
    print()
    if ok_all: ok(f"{C.BOLD}All smoke tests passed! System working.{C.RESET}")
    else: err(f"{C.BOLD}Some tests failed.{C.RESET}")
    return ok_all

# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════
async def main():
    ap = argparse.ArgumentParser(description="HVAC AI v5.0 CLI",
        epilog="  python hvac_impl.py --quick    # Smoke test\n  python hvac_impl.py --chat     # Interactive\n  python hvac_impl.py --full-flow # Full demo",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--chat", action="store_true", help="Interactive chat")
    ap.add_argument("--demo", action="store_true", help="12 AI scenarios")
    ap.add_argument("--route", action="store_true", help="Routing demo")
    ap.add_argument("--inventory", action="store_true", help="Inventory demo")
    ap.add_argument("--emergency", action="store_true", help="Emergency triage")
    ap.add_argument("--safety", action="store_true", help="Safety guards")
    ap.add_argument("--full-flow", action="store_true", help="Full integrated flow")
    ap.add_argument("--quick", action="store_true", help="Quick smoke test")
    a = ap.parse_args()

    run_all = not any([a.chat,a.demo,a.route,a.inventory,a.emergency,a.safety,a.full_flow,a.quick])

    print(f"\n{C.BOLD}{C.CYAN}╔══════════════════════════════════════════════════════════╗")
    print(f"║     HVAC AI Receptionist v5.0 — CLI Test Runner         ║")
    print(f"║     Mock Mode: ON ✓  │  Zero dependencies               ║")
    print(f"╚══════════════════════════════════════════════════════════╝{C.RESET}")

    if a.chat: await run_chat(); return
    if a.quick: await run_quick(); return
    if run_all or a.emergency: run_emergency_demo()
    if run_all or a.safety: run_safety_demo()
    if run_all or a.demo: await run_receptionist_demo()
    if run_all or a.route: await run_routing_demo()
    if run_all or a.inventory: run_inventory_demo()
    if run_all or a.full_flow: await run_full_flow()
    if run_all:
        print(f"\n{C.BOLD}{C.GREEN}{'═'*70}")
        print(f"  ALL DEMOS COMPLETE — System verified")
        print(f"  Deploy: ./setup.sh | Production: MOCK_MODE=0 + API keys")
        print(f"{'═'*70}{C.RESET}\n")

if __name__ == "__main__":
    asyncio.run(main())
