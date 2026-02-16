import { useState, useEffect, useRef } from "react";

// ─── MOCK DATA ENGINE ─────────────────────────────────────────────
const MOCK_CALLS = [
  { id: "c001", time: "7:42 AM", from: "+1 (214) 555-0147", name: "Sarah Mitchell", type: "Emergency", priority: "CRITICAL", summary: "Gas smell near furnace — AI instructed evacuation + 911", status: "resolved", aiHandled: true, duration: "0:34", transcript: "Caller reported strong gas odor near basement furnace. AI triggered CRITICAL protocol: instructed immediate evacuation, advised calling 911, dispatched Mike R. as emergency backup." },
  { id: "c002", time: "8:15 AM", from: "+1 (972) 555-0283", name: "James Cooper", type: "No Heat", priority: "HIGH", summary: "Furnace out, 44°F inside, elderly parent — dispatched Mike R.", status: "dispatched", aiHandled: true, duration: "1:12", transcript: "Caller reported furnace stopped overnight. Indoor temp 44°F. Elderly mother (82) in home. AI classified HIGH priority with vulnerable occupant, auto-dispatched nearest heating-certified tech." },
  { id: "c003", time: "8:51 AM", from: "+1 (469) 555-0391", name: "Linda Torres", type: "Scheduling", priority: "LOW", summary: "Annual AC tune-up — booked Thursday 2-4 PM with Carlos D.", status: "booked", aiHandled: true, duration: "0:48", transcript: "Routine maintenance request for central AC unit. AI offered available Thursday afternoon slot, confirmed with customer via SMS." },
  { id: "c004", time: "9:23 AM", from: "+1 (817) 555-0172", name: "Robert Chang", type: "Repair", priority: "MEDIUM", summary: "AC blowing warm air — scheduled same-day PM with Carlos D.", status: "booked", aiHandled: true, duration: "1:05", transcript: "AC running but not cooling. No emergency indicators. AI scheduled same-day afternoon visit, sent confirmation SMS to customer." },
  { id: "c005", time: "9:58 AM", from: "+1 (214) 555-0445", name: "Maria Gonzalez", type: "Pricing", priority: "LOW", summary: "Asked about duct cleaning cost — quoted $299-499, offered booking", status: "quoted", aiHandled: true, duration: "0:38", transcript: "Customer inquired about duct cleaning pricing. AI provided range from knowledge base and offered to schedule. Customer said she'd call back." },
  { id: "c006", time: "10:14 AM", from: "+1 (972) 555-0528", name: "Unknown Caller", type: "Escalated", priority: "MEDIUM", summary: "Complex warranty question — transferred to office", status: "escalated", aiHandled: false, duration: "0:22", transcript: "Caller asked about warranty coverage for a compressor replacement from 2023. AI confidence below 80% threshold — escalated to human dispatcher." },
  { id: "c007", time: "10:45 AM", from: "+1 (469) 555-0663", name: "David Park", type: "Emergency", priority: "HIGH", summary: "No AC, 98°F inside, pregnant wife — emergency dispatched", status: "dispatched", aiHandled: true, duration: "0:52", transcript: "AC failure with indoor temp 98°F. Pregnant wife reported. AI classified HIGH priority with vulnerable occupant, dispatched nearest AC-certified tech." },
  { id: "c008", time: "11:02 AM", from: "+1 (214) 555-0719", name: "Jennifer Walsh", type: "Scheduling", priority: "LOW", summary: "Filter replacement — booked Friday 9 AM with Ana S.", status: "booked", aiHandled: true, duration: "0:31", transcript: "Routine filter replacement request. AI checked technician availability and booked earliest morning slot." },
];

const MOCK_TECHS = [
  { id: "t1", name: "Mike Rodriguez", status: "on-job", phone: "(214) 555-0801", skills: ["Heating", "Gas", "Emergency"], jobs: 3, currentJob: "7142 Oak Lawn Ave — No Heat Emergency", eta: "On site", avatar: "MR" },
  { id: "t2", name: "Carlos Delgado", status: "driving", phone: "(972) 555-0802", skills: ["AC", "Refrigeration", "Install"], jobs: 4, currentJob: "En route → 3891 Elm St", eta: "12 min", avatar: "CD" },
  { id: "t3", name: "Ana Sanchez", status: "available", phone: "(469) 555-0803", skills: ["Maintenance", "Ductwork", "Filters"], jobs: 2, currentJob: "—", eta: "Available", avatar: "AS" },
];

const MOCK_INVENTORY_ALERTS = [
  { part: "R-410A Refrigerant 25lb", stock: 2, reorder: 3, sku: "REF-001", epa: true },
  { part: "Run Capacitor 45/5 MFD", stock: 4, reorder: 5, sku: "CAP-001", epa: false },
  { part: "Compressor 3-Ton", stock: 1, reorder: 2, sku: "CMP-001", epa: false },
];

const STATS = { callsToday: 8, aiHandled: 7, emergencies: 2, booked: 3, avgResponse: "1.4s", satisfaction: 4.7, missedCalls: 0, revenueRecovered: 2850 };

// ─── PRIORITY / STATUS STYLING ─────────────────────────────────────
const priorityConfig = {
  CRITICAL: { bg: "bg-red-50", border: "border-red-200", text: "text-red-700", badge: "bg-red-600", dot: "bg-red-500" },
  HIGH: { bg: "bg-amber-50", border: "border-amber-200", text: "text-amber-700", badge: "bg-amber-500", dot: "bg-amber-500" },
  MEDIUM: { bg: "bg-blue-50", border: "border-blue-200", text: "text-blue-700", badge: "bg-blue-500", dot: "bg-blue-500" },
  LOW: { bg: "bg-emerald-50", border: "border-emerald-200", text: "text-emerald-700", badge: "bg-emerald-500", dot: "bg-emerald-500" },
};

const statusConfig = {
  "on-job": { bg: "bg-red-100", text: "text-red-700", label: "On Job" },
  driving: { bg: "bg-amber-100", text: "text-amber-700", label: "Driving" },
  available: { bg: "bg-emerald-100", text: "text-emerald-700", label: "Available" },
};

// ─── ICON COMPONENTS ───────────────────────────────────────────────
const PhoneIcon = () => <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/></svg>;
const AlertIcon = () => <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>;
const TruckIcon = () => <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 18V6a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v11a1 1 0 0 0 1 1h2"/><path d="M15 18h2a1 1 0 0 0 1-1v-3.65a1 1 0 0 0-.22-.624l-3.48-4.35A1 1 0 0 0 13.52 8H14"/><circle cx="17" cy="18" r="2"/><circle cx="7" cy="18" r="2"/></svg>;
const BoxIcon = () => <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="m3.3 7 8.7 5 8.7-5"/><path d="M12 22V12"/></svg>;
const CheckIcon = () => <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>;
const ClockIcon = () => <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>;
const ChevIcon = ({ open }) => <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ transform: open ? "rotate(180deg)" : "rotate(0deg)", transition: "transform 200ms" }}><polyline points="6 9 12 15 18 9"/></svg>;
const DollarIcon = () => <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>;
const ShieldIcon = () => <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>;

// ─── STAT CARD ─────────────────────────────────────────────────────
function StatCard({ icon, label, value, sub, accent }) {
  return (
    <div className="bg-white rounded-xl border border-gray-100 p-4 flex flex-col gap-1" style={{ boxShadow: "0 1px 3px rgba(0,0,0,0.04)" }}>
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-gray-400 uppercase tracking-wide">{label}</span>
        <span className={`${accent || "text-gray-400"}`}>{icon}</span>
      </div>
      <span className="text-2xl font-bold text-gray-900" style={{ fontFamily: "'DM Sans', sans-serif" }}>{value}</span>
      {sub && <span className="text-xs text-gray-400">{sub}</span>}
    </div>
  );
}

// ─── CALL ROW ──────────────────────────────────────────────────────
function CallRow({ call, expanded, onToggle }) {
  const cfg = priorityConfig[call.priority];
  return (
    <div className={`border-l-4 ${cfg.border} ${expanded ? cfg.bg : "bg-white hover:bg-gray-50"} transition-colors`} style={{ borderLeftColor: call.priority === "CRITICAL" ? "#dc2626" : call.priority === "HIGH" ? "#f59e0b" : call.priority === "MEDIUM" ? "#3b82f6" : "#10b981" }}>
      <button onClick={onToggle} className="w-full text-left px-4 py-3 flex items-center gap-3">
        <span className="text-xs text-gray-400 font-mono w-16 shrink-0">{call.time}</span>
        <span className={`text-xs font-semibold px-2 py-0.5 rounded-full text-white ${cfg.badge} shrink-0`}>{call.priority}</span>
        <span className="text-sm font-medium text-gray-800 shrink-0 w-32 truncate">{call.name}</span>
        <span className="text-sm text-gray-500 truncate flex-1">{call.summary}</span>
        <div className="flex items-center gap-2 shrink-0">
          {call.aiHandled ? (
            <span className="text-xs bg-emerald-100 text-emerald-700 px-2 py-0.5 rounded-full flex items-center gap-1"><CheckIcon /> AI</span>
          ) : (
            <span className="text-xs bg-orange-100 text-orange-700 px-2 py-0.5 rounded-full">Escalated</span>
          )}
          <ChevIcon open={expanded} />
        </div>
      </button>
      {expanded && (
        <div className="px-4 pb-4 pt-0">
          <div className="bg-white rounded-lg border border-gray-100 p-4 text-sm text-gray-600 leading-relaxed" style={{ boxShadow: "inset 0 1px 2px rgba(0,0,0,0.04)" }}>
            <div className="flex gap-4 mb-3 text-xs text-gray-400">
              <span>From: <span className="text-gray-600 font-mono">{call.from}</span></span>
              <span>Duration: <span className="text-gray-600">{call.duration}</span></span>
              <span>Type: <span className="text-gray-600">{call.type}</span></span>
            </div>
            <p className="text-gray-700">{call.transcript}</p>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── TECH CARD ─────────────────────────────────────────────────────
function TechCard({ tech }) {
  const s = statusConfig[tech.status];
  return (
    <div className="bg-white rounded-xl border border-gray-100 p-4" style={{ boxShadow: "0 1px 3px rgba(0,0,0,0.04)" }}>
      <div className="flex items-center gap-3 mb-3">
        <div className="w-10 h-10 rounded-full bg-gray-800 text-white flex items-center justify-center text-sm font-bold" style={{ fontFamily: "'DM Sans', sans-serif" }}>{tech.avatar}</div>
        <div className="flex-1">
          <div className="font-semibold text-gray-800 text-sm">{tech.name}</div>
          <div className="text-xs text-gray-400">{tech.skills.join(" · ")}</div>
        </div>
        <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${s.bg} ${s.text}`}>{s.label}</span>
      </div>
      <div className="text-xs text-gray-500 space-y-1">
        <div className="flex justify-between"><span>Current</span><span className="text-gray-700 font-medium truncate ml-2">{tech.currentJob}</span></div>
        <div className="flex justify-between"><span>ETA</span><span className="text-gray-700 font-medium">{tech.eta}</span></div>
        <div className="flex justify-between"><span>Jobs today</span><span className="text-gray-700 font-medium">{tech.jobs} assigned</span></div>
      </div>
    </div>
  );
}

// ─── MAIN DASHBOARD ────────────────────────────────────────────────
export default function HVACDashboard() {
  const [activeTab, setActiveTab] = useState("overview");
  const [expandedCall, setExpandedCall] = useState(null);
  const [currentTime, setCurrentTime] = useState(new Date());
  const [liveCallCount, setLiveCallCount] = useState(8);

  useEffect(() => {
    const t = setInterval(() => setCurrentTime(new Date()), 60000);
    return () => clearInterval(t);
  }, []);

  // Simulate live call coming in
  useEffect(() => {
    const t = setTimeout(() => setLiveCallCount(9), 15000);
    return () => clearTimeout(t);
  }, []);

  const tabs = [
    { id: "overview", label: "Overview" },
    { id: "calls", label: "Calls" },
    { id: "techs", label: "Technicians" },
    { id: "inventory", label: "Inventory" },
  ];

  return (
    <div className="min-h-screen" style={{ background: "linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%)", fontFamily: "'DM Sans', system-ui, sans-serif" }}>
      <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap" rel="stylesheet" />

      {/* ── HEADER ── */}
      <header className="bg-white border-b border-gray-100 px-6 py-3" style={{ boxShadow: "0 1px 3px rgba(0,0,0,0.03)" }}>
        <div className="flex items-center justify-between max-w-7xl mx-auto">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gray-900 flex items-center justify-center">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z"/><path d="M8 12h8M12 8v8" strokeLinecap="round"/></svg>
            </div>
            <div>
              <h1 className="text-base font-bold text-gray-900 leading-tight">Comfort Air HVAC</h1>
              <p className="text-xs text-gray-400">AI Receptionist — Active</p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-1.5">
              <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></div>
              <span className="text-xs font-medium text-emerald-600">System Online</span>
            </div>
            <span className="text-xs text-gray-400 font-mono">
              {currentTime.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" })} · {currentTime.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })}
            </span>
          </div>
        </div>
      </header>

      {/* ── TABS ── */}
      <nav className="bg-white border-b border-gray-100 px-6">
        <div className="flex gap-0 max-w-7xl mx-auto">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.id
                  ? "border-gray-900 text-gray-900"
                  : "border-transparent text-gray-400 hover:text-gray-600"
              }`}
            >
              {tab.label}
              {tab.id === "calls" && liveCallCount > 8 && (
                <span className="ml-1.5 w-2 h-2 inline-block rounded-full bg-red-500 animate-pulse"></span>
              )}
            </button>
          ))}
        </div>
      </nav>

      <main className="max-w-7xl mx-auto px-6 py-6">
        {/* ── OVERVIEW TAB ── */}
        {activeTab === "overview" && (
          <div className="space-y-6">
            {/* Stats Grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <StatCard icon={<PhoneIcon />} label="Calls Today" value={liveCallCount} sub={`${STATS.missedCalls} missed`} accent="text-blue-500" />
              <StatCard icon={<CheckIcon />} label="AI Handled" value={`${STATS.aiHandled}/${STATS.callsToday}`} sub="87.5% automation" accent="text-emerald-500" />
              <StatCard icon={<AlertIcon />} label="Emergencies" value={STATS.emergencies} sub="All resolved safely" accent="text-red-500" />
              <StatCard icon={<DollarIcon />} label="Revenue Saved" value={`$${STATS.revenueRecovered.toLocaleString()}`} sub="From captured calls" accent="text-amber-500" />
            </div>

            {/* Two Column: Recent Calls + Techs */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Recent Calls */}
              <div className="lg:col-span-2 bg-white rounded-xl border border-gray-100 overflow-hidden" style={{ boxShadow: "0 1px 3px rgba(0,0,0,0.04)" }}>
                <div className="px-4 py-3 border-b border-gray-50 flex items-center justify-between">
                  <h2 className="text-sm font-semibold text-gray-800">Recent Calls</h2>
                  <button onClick={() => setActiveTab("calls")} className="text-xs text-blue-500 hover:text-blue-700 font-medium">View all →</button>
                </div>
                <div className="divide-y divide-gray-50">
                  {MOCK_CALLS.slice(0, 5).map(call => (
                    <CallRow key={call.id} call={call} expanded={expandedCall === call.id} onToggle={() => setExpandedCall(expandedCall === call.id ? null : call.id)} />
                  ))}
                </div>
              </div>

              {/* Right Column */}
              <div className="space-y-6">
                {/* Technician Status */}
                <div className="bg-white rounded-xl border border-gray-100 p-4" style={{ boxShadow: "0 1px 3px rgba(0,0,0,0.04)" }}>
                  <h2 className="text-sm font-semibold text-gray-800 mb-3">Technician Status</h2>
                  <div className="space-y-3">
                    {MOCK_TECHS.map(tech => {
                      const s = statusConfig[tech.status];
                      return (
                        <div key={tech.id} className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded-full bg-gray-800 text-white flex items-center justify-center text-xs font-bold">{tech.avatar}</div>
                          <div className="flex-1 min-w-0">
                            <div className="text-sm font-medium text-gray-800 truncate">{tech.name}</div>
                            <div className="text-xs text-gray-400 truncate">{tech.currentJob}</div>
                          </div>
                          <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${s.bg} ${s.text} shrink-0`}>{s.label}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Inventory Alerts */}
                <div className="bg-white rounded-xl border border-gray-100 p-4" style={{ boxShadow: "0 1px 3px rgba(0,0,0,0.04)" }}>
                  <h2 className="text-sm font-semibold text-gray-800 mb-3 flex items-center gap-2">
                    <BoxIcon /> Low Stock Alerts
                    <span className="ml-auto bg-amber-100 text-amber-700 text-xs font-bold px-2 py-0.5 rounded-full">{MOCK_INVENTORY_ALERTS.length}</span>
                  </h2>
                  <div className="space-y-2">
                    {MOCK_INVENTORY_ALERTS.map((item, i) => (
                      <div key={i} className="flex items-center justify-between py-2 border-b border-gray-50 last:border-0">
                        <div>
                          <div className="text-sm text-gray-700 font-medium">{item.part}</div>
                          <div className="text-xs text-gray-400">{item.sku}{item.epa && <span className="ml-1 text-red-500 font-semibold">EPA</span>}</div>
                        </div>
                        <div className="text-right">
                          <div className={`text-sm font-bold ${item.stock <= 2 ? "text-red-600" : "text-amber-600"}`}>{item.stock} left</div>
                          <div className="text-xs text-gray-400">min {item.reorder}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Safety Score */}
                <div className="bg-white rounded-xl border border-gray-100 p-4" style={{ boxShadow: "0 1px 3px rgba(0,0,0,0.04)" }}>
                  <h2 className="text-sm font-semibold text-gray-800 mb-3 flex items-center gap-2"><ShieldIcon /> Safety Score</h2>
                  <div className="flex items-end gap-3">
                    <span className="text-4xl font-bold text-emerald-600" style={{ fontFamily: "'DM Sans', sans-serif" }}>100%</span>
                    <div className="text-xs text-gray-400 pb-1.5">
                      <div>0 missed emergencies</div>
                      <div>0 safety violations</div>
                      <div>2 evacuations triggered</div>
                    </div>
                  </div>
                  <div className="mt-3 h-2 bg-gray-100 rounded-full overflow-hidden">
                    <div className="h-full bg-emerald-500 rounded-full" style={{ width: "100%" }}></div>
                  </div>
                </div>
              </div>
            </div>

            {/* Today's Performance Bar */}
            <div className="bg-white rounded-xl border border-gray-100 p-4" style={{ boxShadow: "0 1px 3px rgba(0,0,0,0.04)" }}>
              <h2 className="text-sm font-semibold text-gray-800 mb-4">Today's Performance</h2>
              <div className="grid grid-cols-2 md:grid-cols-5 gap-6">
                {[
                  { label: "Avg Response", value: STATS.avgResponse, bar: 95, color: "bg-emerald-500" },
                  { label: "AI Automation", value: "87.5%", bar: 87.5, color: "bg-blue-500" },
                  { label: "Satisfaction", value: `${STATS.satisfaction}/5`, bar: 94, color: "bg-amber-500" },
                  { label: "Missed Calls", value: "0", bar: 100, color: "bg-emerald-500" },
                  { label: "Escalation Rate", value: "12.5%", bar: 87.5, color: "bg-blue-500" },
                ].map((m, i) => (
                  <div key={i}>
                    <div className="flex justify-between items-baseline mb-1">
                      <span className="text-xs text-gray-400">{m.label}</span>
                      <span className="text-sm font-bold text-gray-800">{m.value}</span>
                    </div>
                    <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                      <div className={`h-full ${m.color} rounded-full transition-all duration-1000`} style={{ width: `${m.bar}%` }}></div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ── CALLS TAB ── */}
        {activeTab === "calls" && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold text-gray-800">All Calls — Today</h2>
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-400">{MOCK_CALLS.length} calls</span>
                <span className="text-xs bg-emerald-100 text-emerald-700 px-2 py-0.5 rounded-full font-medium">{MOCK_CALLS.filter(c => c.aiHandled).length} AI-handled</span>
                <span className="text-xs bg-orange-100 text-orange-700 px-2 py-0.5 rounded-full font-medium">{MOCK_CALLS.filter(c => !c.aiHandled).length} escalated</span>
              </div>
            </div>
            <div className="bg-white rounded-xl border border-gray-100 overflow-hidden divide-y divide-gray-50" style={{ boxShadow: "0 1px 3px rgba(0,0,0,0.04)" }}>
              {MOCK_CALLS.map(call => (
                <CallRow key={call.id} call={call} expanded={expandedCall === call.id} onToggle={() => setExpandedCall(expandedCall === call.id ? null : call.id)} />
              ))}
            </div>
          </div>
        )}

        {/* ── TECHNICIANS TAB ── */}
        {activeTab === "techs" && (
          <div className="space-y-4">
            <h2 className="text-lg font-bold text-gray-800">Technician Fleet</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {MOCK_TECHS.map(tech => <TechCard key={tech.id} tech={tech} />)}
            </div>

            {/* Route Summary */}
            <div className="bg-white rounded-xl border border-gray-100 p-5" style={{ boxShadow: "0 1px 3px rgba(0,0,0,0.04)" }}>
              <h3 className="text-sm font-semibold text-gray-800 mb-4">Today's Route Summary</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {MOCK_TECHS.map(tech => (
                  <div key={tech.id} className="space-y-2">
                    <div className="font-medium text-sm text-gray-800">{tech.name}</div>
                    {[...Array(tech.jobs)].map((_, j) => (
                      <div key={j} className="flex items-center gap-2 text-xs">
                        <div className="w-5 h-5 rounded-full bg-gray-100 text-gray-500 flex items-center justify-center font-bold text-xs">{j + 1}</div>
                        <div className="flex-1 h-px bg-gray-200"></div>
                        <span className="text-gray-500">
                          {j === 0 ? "8:00" : j === 1 ? "10:00" : j === 2 ? "1:00 PM" : "3:30 PM"}
                        </span>
                        <span className={`px-1.5 py-0.5 rounded text-xs ${j === 0 && tech.status === "on-job" ? "bg-blue-100 text-blue-700 font-medium" : "bg-gray-100 text-gray-500"}`}>
                          {j === 0 && tech.status === "on-job" ? "Current" : j < (tech.status === "on-job" ? 0 : 1) ? "Done" : "Queued"}
                        </span>
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ── INVENTORY TAB ── */}
        {activeTab === "inventory" && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold text-gray-800">Inventory Status</h2>
              <span className="text-xs bg-amber-100 text-amber-700 px-3 py-1 rounded-full font-medium">{MOCK_INVENTORY_ALERTS.length} items need reorder</span>
            </div>

            {/* Full Inventory Table */}
            <div className="bg-white rounded-xl border border-gray-100 overflow-hidden" style={{ boxShadow: "0 1px 3px rgba(0,0,0,0.04)" }}>
              <table className="w-full">
                <thead>
                  <tr className="bg-gray-50 border-b border-gray-100">
                    <th className="text-left text-xs font-semibold text-gray-500 px-4 py-2.5">Part</th>
                    <th className="text-left text-xs font-semibold text-gray-500 px-4 py-2.5">SKU</th>
                    <th className="text-center text-xs font-semibold text-gray-500 px-4 py-2.5">Stock</th>
                    <th className="text-center text-xs font-semibold text-gray-500 px-4 py-2.5">Reorder At</th>
                    <th className="text-center text-xs font-semibold text-gray-500 px-4 py-2.5">Status</th>
                    <th className="text-right text-xs font-semibold text-gray-500 px-4 py-2.5">Unit Cost</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {[
                    { name: "Standard Air Filter 16x25x1", sku: "FLT-001", stock: 50, reorder: 10, cost: "$12.99", epa: false },
                    { name: "HEPA Filter 20x25x4", sku: "FLT-002", stock: 20, reorder: 5, cost: "$34.99", epa: false },
                    { name: "Run Capacitor 45/5 MFD", sku: "CAP-001", stock: 4, reorder: 5, cost: "$18.50", epa: false },
                    { name: "Start Capacitor 88-106 MFD", sku: "CAP-002", stock: 10, reorder: 3, cost: "$22.00", epa: false },
                    { name: "Condenser Fan Motor 1/4 HP", sku: "MOT-001", stock: 8, reorder: 3, cost: "$89.99", epa: false },
                    { name: "Programmable Thermostat", sku: "THR-001", stock: 12, reorder: 4, cost: "$49.99", epa: false },
                    { name: "R-410A Refrigerant 25lb", sku: "REF-001", stock: 2, reorder: 3, cost: "$149.99", epa: true },
                    { name: "Compressor 3-Ton", sku: "CMP-001", stock: 1, reorder: 2, cost: "$599.99", epa: false },
                    { name: 'Flex Duct 6" x 25ft', sku: "DUC-001", stock: 20, reorder: 5, cost: "$29.99", epa: false },
                    { name: "Hot Surface Ignitor", sku: "IGN-001", stock: 10, reorder: 3, cost: "$24.99", epa: false },
                  ].map((item, i) => {
                    const low = item.stock <= item.reorder;
                    const critical = item.stock <= Math.floor(item.reorder / 2);
                    return (
                      <tr key={i} className={critical ? "bg-red-50" : low ? "bg-amber-50" : ""}>
                        <td className="px-4 py-3 text-sm font-medium text-gray-800">
                          {item.name}
                          {item.epa && <span className="ml-2 text-xs bg-red-100 text-red-700 px-1.5 py-0.5 rounded font-semibold">EPA 608</span>}
                        </td>
                        <td className="px-4 py-3 text-xs font-mono text-gray-400">{item.sku}</td>
                        <td className={`px-4 py-3 text-sm text-center font-bold ${critical ? "text-red-600" : low ? "text-amber-600" : "text-gray-700"}`}>{item.stock}</td>
                        <td className="px-4 py-3 text-sm text-center text-gray-400">{item.reorder}</td>
                        <td className="px-4 py-3 text-center">
                          {critical ? (
                            <span className="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded-full font-medium">Critical</span>
                          ) : low ? (
                            <span className="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full font-medium">Low</span>
                          ) : (
                            <span className="text-xs bg-emerald-100 text-emerald-700 px-2 py-0.5 rounded-full font-medium">OK</span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-sm text-right text-gray-600">{item.cost}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </main>

      {/* ── FOOTER ── */}
      <footer className="border-t border-gray-100 bg-white px-6 py-3 mt-8">
        <div className="max-w-7xl mx-auto flex items-center justify-between text-xs text-gray-400">
          <span>HVAC AI Receptionist v5.0</span>
          <div className="flex items-center gap-4">
            <span className="flex items-center gap-1"><ClockIcon /> Avg latency: 142ms</span>
            <span className="flex items-center gap-1"><ShieldIcon /> 5-layer safety active</span>
            <span className="flex items-center gap-1"><div className="w-1.5 h-1.5 rounded-full bg-emerald-400"></div> All systems operational</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
