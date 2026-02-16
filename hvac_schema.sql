-- HVAC AI Receptionist v5.0 - Database Schema
-- Core tables always created | pgvector & EPA optional

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
-- CREATE EXTENSION IF NOT EXISTS "vector";  -- Uncomment if USE_PGVECTOR=1

-- ============================================================================
-- Companies & Users
-- ============================================================================

CREATE TABLE IF NOT EXISTS companies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    phone VARCHAR(20),
    email VARCHAR(255) NOT NULL,
    city VARCHAR(100) NOT NULL,
    state VARCHAR(2) NOT NULL,
    timezone VARCHAR(50) DEFAULT 'America/Chicago',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role VARCHAR(20) DEFAULT 'owner', -- owner, dispatcher, technician
    name VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    last_login TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_company ON users(company_id);

CREATE TABLE IF NOT EXISTS technicians (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    phone VARCHAR(20),
    email VARCHAR(255),
    skills TEXT[] DEFAULT '{}',
    max_capacity INTEGER DEFAULT 8,
    home_lat DECIMAL(10, 8),
    home_lon DECIMAL(11, 8),
    epa_cert_number VARCHAR(50),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS customers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    phone VARCHAR(20) NOT NULL,
    email VARCHAR(255),
    address TEXT,
    city VARCHAR(100),
    state VARCHAR(2),
    lat DECIMAL(10, 8),
    lon DECIMAL(11, 8),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- Calls & Conversations
-- ============================================================================

CREATE TABLE IF NOT EXISTS calls (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id VARCHAR(100) UNIQUE NOT NULL,
    company_id UUID REFERENCES companies(id),
    customer_id UUID REFERENCES customers(id),
    from_number VARCHAR(20),
    channel VARCHAR(20) DEFAULT 'web',  -- web, phone, sms
    started_at TIMESTAMPTZ DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    transcript TEXT,
    ai_response TEXT,
    llm_confidence DECIMAL(4, 3),
    is_emergency BOOLEAN DEFAULT FALSE,
    emergency_type VARCHAR(50),
    priority VARCHAR(20),
    fallback_triggered BOOLEAN DEFAULT FALSE,
    sms_sent BOOLEAN DEFAULT FALSE,
    latency_ms INTEGER
);

-- ============================================================================
-- Appointments & Routes
-- ============================================================================

CREATE TABLE IF NOT EXISTS appointments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID REFERENCES companies(id),
    customer_id UUID REFERENCES customers(id),
    technician_id UUID REFERENCES technicians(id),
    call_id UUID REFERENCES calls(id),
    scheduled_date DATE NOT NULL,
    scheduled_time_start TIME NOT NULL,
    scheduled_time_end TIME,
    service_type VARCHAR(50),
    priority INTEGER DEFAULT 1,
    status VARCHAR(20) DEFAULT 'scheduled',
    address TEXT,
    lat DECIMAL(10, 8),
    lon DECIMAL(11, 8),
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- Inventory
-- ============================================================================

CREATE TABLE IF NOT EXISTS inventory_parts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID REFERENCES companies(id),
    sku VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    category VARCHAR(50),
    quantity_on_hand INTEGER DEFAULT 0,
    reorder_point INTEGER DEFAULT 5,
    unit_cost DECIMAL(10, 2) DEFAULT 0.00,
    location VARCHAR(100),
    epa_regulated BOOLEAN DEFAULT FALSE,
    requires_certification VARCHAR(100),
    UNIQUE(company_id, sku)
);

CREATE TABLE IF NOT EXISTS part_usage (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    part_id UUID REFERENCES inventory_parts(id),
    job_id UUID REFERENCES appointments(id),
    technician_id UUID REFERENCES technicians(id),
    quantity_used INTEGER NOT NULL,
    recorded_by VARCHAR(255) NOT NULL,
    recorded_at TIMESTAMPTZ DEFAULT NOW(),
    notes TEXT
);

-- ============================================================================
-- Knowledge Base
-- ============================================================================

CREATE TABLE IF NOT EXISTS knowledge_documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID REFERENCES companies(id),
    doc_key VARCHAR(100) NOT NULL,
    title VARCHAR(255),
    content TEXT NOT NULL,
    category VARCHAR(50),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(company_id, doc_key)
);

CREATE INDEX IF NOT EXISTS idx_knowledge_search ON knowledge_documents
    USING gin(to_tsvector('english', content));

-- ============================================================================
-- Indexes
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_calls_session ON calls(session_id);
CREATE INDEX IF NOT EXISTS idx_calls_company ON calls(company_id);
CREATE INDEX IF NOT EXISTS idx_calls_emergency ON calls(is_emergency) WHERE is_emergency = TRUE;
CREATE INDEX IF NOT EXISTS idx_appointments_date ON appointments(scheduled_date);
CREATE INDEX IF NOT EXISTS idx_inventory_company ON inventory_parts(company_id);

-- ============================================================================
-- Seed Data
-- ============================================================================

INSERT INTO companies (name, phone, email, city, state)
VALUES ('Demo HVAC', '+15550100', 'demo@hvac-ai.com', 'Chicago', 'IL')
ON CONFLICT DO NOTHING;

INSERT INTO knowledge_documents (company_id, doc_key, title, content, category)
SELECT id, 'emergency_no_heat', 'Emergency: No Heat',
       'No heat in cold weather is an emergency. Schedule immediately. Check for vulnerable occupants.', 'emergency'
FROM companies WHERE name = 'Demo HVAC'
ON CONFLICT DO NOTHING;

INSERT INTO knowledge_documents (company_id, doc_key, title, content, category)
SELECT id, 'scheduling', 'Appointment Scheduling',
       'We offer same-day emergency, next-day standard, and flexible maintenance scheduling.', 'general'
FROM companies WHERE name = 'Demo HVAC'
ON CONFLICT DO NOTHING;
