-- ══════════════════════════════════════════════════════════════
--  Cricket Dashboard — Access Control Schema
--  Run in: Supabase → SQL Editor → New Query
--
--  IMPORTANT: These tables replace the old Supabase Auth system.
--  No auth.users dependency. No RLS on these tables (app-level
--  control only, since we are no longer using Supabase Auth).
-- ══════════════════════════════════════════════════════════════


-- ── 1. ALLOWED USERS ─────────────────────────────────────────
--  Email is the primary key and the only identity token.
--  Admin adds/approves users here. If is_active = false,
--  the user is blocked even if their email is in the table.

CREATE TABLE IF NOT EXISTS allowed_users (
    email      TEXT        PRIMARY KEY,
    name       TEXT        NOT NULL,
    phone      TEXT,
    role       TEXT        NOT NULL DEFAULT 'viewer'
                           CHECK (role IN ('admin','editor','viewer')),
    is_active  BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- ── 2. ACCESS REQUESTS ───────────────────────────────────────
--  Anyone who submits the login form with an unknown email lands
--  here. Admin reviews and can approve → inserts into allowed_users.

CREATE TABLE IF NOT EXISTS access_requests (
    id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    name       TEXT        NOT NULL,
    email      TEXT        NOT NULL,
    phone      TEXT,
    status     TEXT        NOT NULL DEFAULT 'pending'
                           CHECK (status IN ('pending','approved','rejected')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_requests_email  ON access_requests (email);
CREATE INDEX IF NOT EXISTS idx_requests_status ON access_requests (status);


-- ── 3. DISABLE RLS (we use app-level auth now) ───────────────
--  The anon key is used for all DB calls.
--  Enable RLS only if you later add row-level restrictions.

ALTER TABLE allowed_users   DISABLE ROW LEVEL SECURITY;
ALTER TABLE access_requests DISABLE ROW LEVEL SECURITY;

-- Also disable RLS on existing cricket tables so the anon key
-- can read/write them without the old auth.users policies.
ALTER TABLE events DISABLE ROW LEVEL SECURITY;
ALTER TABLE teams  DISABLE ROW LEVEL SECURITY;
ALTER TABLE squad  DISABLE ROW LEVEL SECURITY;

-- Drop old auth.users-dependent policies if they exist
DROP POLICY IF EXISTS "allow_all_events"        ON events;
DROP POLICY IF EXISTS "allow_all_teams"         ON teams;
DROP POLICY IF EXISTS "allow_all_squad"         ON squad;
DROP POLICY IF EXISTS "auth_read_events"        ON events;
DROP POLICY IF EXISTS "editors_write_events"    ON events;
DROP POLICY IF EXISTS "editors_update_events"   ON events;
DROP POLICY IF EXISTS "admins_delete_events"    ON events;
DROP POLICY IF EXISTS "auth_read_teams"         ON teams;
DROP POLICY IF EXISTS "editors_write_teams"     ON teams;
DROP POLICY IF EXISTS "editors_update_teams"    ON teams;
DROP POLICY IF EXISTS "admins_delete_teams"     ON teams;
DROP POLICY IF EXISTS "auth_read_squad"         ON squad;
DROP POLICY IF EXISTS "editors_write_squad"     ON squad;
DROP POLICY IF EXISTS "editors_update_squad"    ON squad;
DROP POLICY IF EXISTS "admins_delete_squad"     ON squad;


-- ── 4. SEED YOUR FIRST ADMIN ────────────────────────────────
--  Replace with your real name and email before running.

INSERT INTO allowed_users (email, name, phone, role, is_active)
VALUES ('admin@yourcompany.com', 'Admin Name', '', 'admin', TRUE)
ON CONFLICT (email) DO NOTHING;


-- ══════════════════════════════════════════════════════════════
--  DONE. Tables created:
--    allowed_users   — approved staff (email PK, role, is_active)
--    access_requests — pending requests from unknown emails
-- ══════════════════════════════════════════════════════════════
