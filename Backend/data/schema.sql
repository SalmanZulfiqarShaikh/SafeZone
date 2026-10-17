-- ─────────────────────────────────────────────────────────────────────────────
-- SafeZone Database Schema for Supabase (PostgreSQL)
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
    lat DOUBLE PRECISION,                      -- approximate centre, for ranking only
    lng DOUBLE PRECISION,                      -- never shown to a responder as a person's location
    volunteer_group TEXT,                      -- which volunteer covers this area ('a' | 'b')
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

-- ─── 9b. REGISTRATIONS ───────────────────────────────────────────────────────
-- Website sign-ups waiting for their WhatsApp handshake. Registration is the
-- optional alerts path, never the front door: anyone can message SafeZone with
-- no account and get the full help ladder.
--
-- No phone number is captured at the form. The number is whichever one sends
-- JOIN <code> -- the only one we can prove is reachable, and the only one Meta
-- lets us message afterwards.
CREATE TABLE IF NOT EXISTS registrations (
    code TEXT PRIMARY KEY,                     -- short, single use, expires
    first_name TEXT NOT NULL,
    zone_id TEXT REFERENCES zones(id),
    phone TEXT,                                -- filled in on redemption
    wants_alerts BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    redeemed_at TIMESTAMPTZ
);

-- Redemption looks a code up directly; this index serves the "which
-- registration belongs to this phone" lookup.
CREATE INDEX IF NOT EXISTS idx_registrations_phone ON registrations(phone);

-- ─── 9c. ZONE ALERTS ─────────────────────────────────────────────────────────
-- Which registered person has already been warned about which incident. The
-- unique index is the dedup rule: a second alert about the same event is worse
-- than a missed one, because alert fatigue is a safety failure.
CREATE TABLE IF NOT EXISTS zone_alerts (
    id BIGSERIAL PRIMARY KEY,
    incident_id BIGINT NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    person_id BIGINT NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    zone_id TEXT REFERENCES zones(id),
    sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_zone_alerts_incident_person
    ON zone_alerts(incident_id, person_id);

-- ─── 10. OUTBOX ──────────────────────────────────────────────────────────────
-- Every outbound message in both modes. This is the message audit log and the
-- primary debugging surface when the demo misbehaves.
-- Rename the old mock-only table first, so CREATE IF NOT EXISTS below does not
-- create an empty replacement alongside it.
DO $$
BEGIN
    IF to_regclass('public.mock_outbox') IS NOT NULL
       AND to_regclass('public.outbox') IS NULL THEN
        ALTER TABLE public.mock_outbox RENAME TO outbox;
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS outbox (
    id BIGSERIAL PRIMARY KEY,
    to_phone TEXT NOT NULL,
    text TEXT NOT NULL,
    status TEXT DEFAULT 'sent',
    mode TEXT NOT NULL DEFAULT 'mock',         -- 'mock' | 'live'
    suppressed_reason TEXT,                    -- why send_message() did not send
    sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Bring pre-existing outbox tables up to the current shape.
ALTER TABLE zones ADD COLUMN IF NOT EXISTS lat DOUBLE PRECISION;
ALTER TABLE zones ADD COLUMN IF NOT EXISTS lng DOUBLE PRECISION;
ALTER TABLE zones ADD COLUMN IF NOT EXISTS volunteer_group TEXT;

-- How we came by an incident's coordinates. 'pin' is exact and came from the
-- person; 'area' is an area centre we substituted so the case could be ranked
-- and offered at all. A responder is only ever shown a 'pin'.
ALTER TABLE incidents ADD COLUMN IF NOT EXISTS location_source TEXT;

ALTER TABLE outbox ADD COLUMN IF NOT EXISTS mode TEXT NOT NULL DEFAULT 'mock';
ALTER TABLE outbox ADD COLUMN IF NOT EXISTS suppressed_reason TEXT;

DROP INDEX IF EXISTS idx_mock_outbox_phone;
CREATE INDEX IF NOT EXISTS idx_outbox_phone ON outbox(to_phone);

-- ─── 11. CONSTRAINT HARDENING ────────────────────────────────────────────────
-- A typo in a status column otherwise writes an invalid value and the case
-- silently stalls with no error. DO blocks keep this re-runnable.
DO $$
BEGIN
    ALTER TABLE incidents ADD CONSTRAINT chk_incidents_status
        CHECK (status IN ('open', 'active', 'resolved', 'closed'));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    ALTER TABLE cases ADD CONSTRAINT chk_cases_status
        CHECK (status IN ('proposed', 'approved', 'rejected', 'resolved'));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    ALTER TABLE cases ADD CONSTRAINT chk_cases_dispatch_status
        CHECK (dispatch_status IN (
            'none', 'offered', 'accepted', 'on_way', 'arrived',
            'confirmed', 'closed', 'reopened'
        ));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    ALTER TABLE dispatches ADD CONSTRAINT chk_dispatches_status
        CHECK (status IN (
            'offered', 'accepted', 'on_way', 'arrived',
            'done', 'declined', 'expired'
        ));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    ALTER TABLE volunteers ADD CONSTRAINT chk_volunteers_status
        CHECK (status IN ('off_duty', 'on_duty', 'busy'));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    ALTER TABLE outbox ADD CONSTRAINT chk_outbox_mode
        CHECK (mode IN ('mock', 'live'));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- Re-escalation must never offer the same case to the same volunteer twice.
CREATE UNIQUE INDEX IF NOT EXISTS idx_dispatches_case_volunteer
    ON dispatches(case_id, volunteer_id);

-- The queue sorts on this.
CREATE INDEX IF NOT EXISTS idx_incidents_priority_score
    ON incidents(priority_score DESC);

-- ─── 12. ROW LEVEL SECURITY ──────────────────────────────────────────────────
-- Supabase exposes every table over PostgREST, and the anon key ships in
-- frontend code. RLS with zero policies blocks the anon key completely, while
-- the backend's service key bypasses RLS. All access goes through FastAPI;
-- nothing is read from the browser. Do not add policies without re-reading this.
ALTER TABLE zones            ENABLE ROW LEVEL SECURITY;
ALTER TABLE people           ENABLE ROW LEVEL SECURITY;
ALTER TABLE incidents        ENABLE ROW LEVEL SECURITY;
ALTER TABLE reports          ENABLE ROW LEVEL SECURITY;
ALTER TABLE cases            ENABLE ROW LEVEL SECURITY;
ALTER TABLE events           ENABLE ROW LEVEL SECURITY;
ALTER TABLE volunteers       ENABLE ROW LEVEL SECURITY;
ALTER TABLE dispatches       ENABLE ROW LEVEL SECURITY;
ALTER TABLE responder_links  ENABLE ROW LEVEL SECURITY;
ALTER TABLE outbox           ENABLE ROW LEVEL SECURITY;
ALTER TABLE registrations    ENABLE ROW LEVEL SECURITY;
ALTER TABLE zone_alerts      ENABLE ROW LEVEL SECURITY;
