-- ─────────────────────────────────────────────────────────────────────────────
-- Dastak Database Schema for Supabase (PostgreSQL)
-- Strictly implements AGENTS.md §5 (Data model) and §2 (Non-negotiables)
-- ─────────────────────────────────────────────────────────────────────────────

-- Enable pgcrypto / uuid if needed
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ─── 1. ZONES ────────────────────────────────────────────────────────────────
-- Karachi priority flood zones: Johar, Gulshan, Surjani, Lyari, Gujjar, Korangi, DHA
CREATE TABLE IF NOT EXISTS zones (
    id TEXT PRIMARY KEY,                       -- e.g. 'gulshan', 'surjani', 'lyari'
    name TEXT NOT NULL,                        -- e.g. 'Gulshan-e-Iqbal'
    risk_level TEXT DEFAULT 'normal',          -- 'normal' | 'elevated' | 'critical'
    boundary_geojson JSONB,                    -- GeoJSON polygon/multipolygon
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── 2. PEOPLE ───────────────────────────────────────────────────────────────
-- A person we know about. Created on first contact, registered or not.
CREATE TABLE IF NOT EXISTS people (
    id BIGSERIAL PRIMARY KEY,
    phone TEXT UNIQUE NOT NULL,                -- Normalized (923xxxxxxxxx), no +, no leading zero
    first_name TEXT,
    zone_id TEXT REFERENCES zones(id) ON DELETE SET NULL,
    lat DOUBLE PRECISION,
    lng DOUBLE PRECISION,
    is_registered BOOLEAN DEFAULT FALSE,       -- Registered via web portal
    wants_alerts BOOLEAN DEFAULT FALSE,
    person_vuln JSONB DEFAULT '{}'::jsonb,     -- {"elderly": bool, "alone": bool, "floor": "ground", ...}
    window_open_until TIMESTAMPTZ,             -- ISO8601, 24h WhatsApp window expiration
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_people_phone ON people(phone);
CREATE INDEX IF NOT EXISTS idx_people_zone ON people(zone_id);

-- ─── 3. INCIDENTS ────────────────────────────────────────────────────────────
-- A real-world situation. Reports merge into it.
CREATE TABLE IF NOT EXISTS incidents (
    id BIGSERIAL PRIMARY KEY,
    category TEXT NOT NULL,                    -- flood | fire | medical | trapped | structural | other
    lat DOUBLE PRECISION,
    lng DOUBLE PRECISION,
    zone_id TEXT REFERENCES zones(id) ON DELETE SET NULL,
    location_known BOOLEAN DEFAULT FALSE,
    report_count INT DEFAULT 1,
    confidence DOUBLE PRECISION DEFAULT 0.6,
    urgency DOUBLE PRECISION DEFAULT 0.5,
    priority_score DOUBLE PRECISION DEFAULT 0.0,
    status TEXT DEFAULT 'open',                -- 'open' | 'active' | 'resolved' | 'closed'
    dispatch_status TEXT DEFAULT 'none',       -- 'none' | 'offered' | 'accepted' | 'on_way' | 'arrived' | 'confirmed' | 'closed' | 'reopened'
    reopened BOOLEAN DEFAULT FALSE,
    reopen_reason TEXT,
    first_report_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_update_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents(status);
CREATE INDEX IF NOT EXISTS idx_incidents_zone ON incidents(zone_id);

-- ─── 4. REPORTS ──────────────────────────────────────────────────────────────
-- One inbound report. Multiple reports merge into one incident.
CREATE TABLE IF NOT EXISTS reports (
    id BIGSERIAL PRIMARY KEY,
    person_id BIGINT REFERENCES people(id) ON DELETE SET NULL,
    incident_id BIGINT REFERENCES incidents(id) ON DELETE SET NULL,
    raw_text TEXT,
    source TEXT NOT NULL DEFAULT 'whatsapp',   -- 'whatsapp' | 'web'
    source_factor DOUBLE PRECISION NOT NULL DEFAULT 1.0, -- whatsapp 1.0, web 0.7
    category TEXT,                             -- flood | fire | medical | trapped | other
    lat DOUBLE PRECISION,
    lng DOUBLE PRECISION,
    zone_id TEXT REFERENCES zones(id) ON DELETE SET NULL,
    location_known BOOLEAN DEFAULT FALSE,
    extraction JSONB DEFAULT '{}'::jsonb,      -- Raw structured output from extract_report
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reports_incident ON reports(incident_id);
CREATE INDEX IF NOT EXISTS idx_reports_person ON reports(person_id);

-- ─── 5. CASES ────────────────────────────────────────────────────────────────
-- Coordinator-facing unit of work. One per incident in this prototype.
CREATE TABLE IF NOT EXISTS cases (
    id BIGSERIAL PRIMARY KEY,
    incident_id BIGINT REFERENCES incidents(id) ON DELETE CASCADE,
    person_id BIGINT REFERENCES people(id) ON DELETE SET NULL,
    priority_score DOUBLE PRECISION DEFAULT 0.0,
    reason TEXT,                               -- Plain-language justification shown to judges & coordinators
    vuln_summary TEXT,
    protocol_path JSONB DEFAULT '[]'::jsonb,   -- Array of protocol nodes traversed
    status TEXT DEFAULT 'proposed',            -- 'proposed' | 'approved' | 'rejected' | 'resolved'
    dispatch_status TEXT DEFAULT 'none',       -- none | offered | accepted | on_way | arrived | confirmed | closed | reopened
    reopened BOOLEAN DEFAULT FALSE,
    reopen_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_cases_status ON cases(status);
CREATE INDEX IF NOT EXISTS idx_cases_dispatch_status ON cases(dispatch_status);
CREATE INDEX IF NOT EXISTS idx_cases_priority ON cases(priority_score DESC);

-- ─── 6. EVENTS ───────────────────────────────────────────────────────────────
-- Immutable audit log for SSE and replay slider. Every state change goes through emit().
CREATE TABLE IF NOT EXISTS events (
    id BIGSERIAL PRIMARY KEY,
    type TEXT NOT NULL,                        -- ReportReceived, CaseApproved, VolunteerAccepted, etc.
    case_id BIGINT REFERENCES cases(id) ON DELETE SET NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_events_type ON events(type);
CREATE INDEX IF NOT EXISTS idx_events_case_id ON events(case_id);
CREATE INDEX IF NOT EXISTS idx_events_created_at ON events(created_at);

-- ─── 7. VOLUNTEERS ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS volunteers (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    phone TEXT NOT NULL,                       -- Normalized (923xxxxxxxxx); multiple demo rows may share one
    zone_ids JSONB NOT NULL DEFAULT '[]'::jsonb, -- e.g. ["gulshan", "johar"]
    capabilities JSONB NOT NULL DEFAULT '[]'::jsonb, -- ["foot", "car", "boat", "first_aid"]
    lat DOUBLE PRECISION,
    lng DOUBLE PRECISION,
    status TEXT DEFAULT 'off_duty',            -- 'off_duty' | 'on_duty' | 'busy'
    window_open_until TIMESTAMPTZ,
    is_demo BOOLEAN DEFAULT TRUE,              -- Demo volunteers labelled as simulated in UI
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_volunteers_phone ON volunteers(phone);
CREATE INDEX IF NOT EXISTS idx_volunteers_status ON volunteers(status);

-- ─── 8. DISPATCHES ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dispatches (
    id BIGSERIAL PRIMARY KEY,
    case_id BIGINT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    volunteer_id BIGINT NOT NULL REFERENCES volunteers(id) ON DELETE CASCADE,
    ring INT NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'offered',    -- offered | accepted | on_way | arrived | done | declined | expired
    offered_at TIMESTAMPTZ DEFAULT NOW(),
    accepted_at TIMESTAMPTZ,
    arrived_at TIMESTAMPTZ,
    done_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_dispatches_case ON dispatches(case_id);
CREATE INDEX IF NOT EXISTS idx_dispatches_volunteer ON dispatches(volunteer_id);
CREATE INDEX IF NOT EXISTS idx_dispatches_status ON dispatches(status);

-- ─── 9. RESPONDER LINKS ──────────────────────────────────────────────────────
-- Unguessable tokenized links for official emergency service / NGO desk handoffs.
CREATE TABLE IF NOT EXISTS responder_links (
    token TEXT PRIMARY KEY,                    -- Unguessable urlsafe token
    case_id BIGINT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    target_label TEXT,                         -- e.g. 'Edhi Ambulance Central Desk'
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL
);

-- ─── 10. MOCK OUTBOX ─────────────────────────────────────────────────────────
-- Stores outbound messages when MOCK_MODE=1 or for message audit
CREATE TABLE IF NOT EXISTS mock_outbox (
    id BIGSERIAL PRIMARY KEY,
    to_phone TEXT NOT NULL,
    text TEXT NOT NULL,
    status TEXT DEFAULT 'sent',
    sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mock_outbox_phone ON mock_outbox(to_phone);
