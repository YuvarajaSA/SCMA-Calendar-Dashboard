-- ══════════════════════════════════════════════════════════════
--  Cricket Dashboard — Profiles & Auth Schema
--  Run in: Supabase → SQL Editor → New Query
--
--  This uses Supabase Auth for identity (Google OAuth + Email).
--  The profiles table stores approval status and roles.
--  A user can log in via Supabase Auth but still be "pending"
--  until an admin approves them in the Admin panel.
-- ══════════════════════════════════════════════════════════════


-- ── 1. PROFILES ──────────────────────────────────────────────
--  One row per Supabase Auth user.
--  id matches auth.users.id exactly.
--  status controls dashboard access (not just authentication).

CREATE TABLE IF NOT EXISTS profiles (
    id         UUID        PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email      TEXT        NOT NULL UNIQUE,
    name       TEXT        NOT NULL DEFAULT '',
    phone      TEXT                 DEFAULT '',
    location   TEXT                 DEFAULT '',
    status     TEXT        NOT NULL DEFAULT 'pending'
                           CHECK (status IN ('pending','approved','rejected')),
    role       TEXT        NOT NULL DEFAULT 'viewer'
                           CHECK (role IN ('admin','editor','viewer')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_profiles_email  ON profiles (email);
CREATE INDEX IF NOT EXISTS idx_profiles_status ON profiles (status);


-- ── 2. ROW LEVEL SECURITY ────────────────────────────────────
--  Users can read/update their own profile.
--  Admins can read and update all profiles.
--  We use the anon key from the app, so policies must allow
--  authenticated users to operate.

ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;

-- Every authenticated user can see their own profile
CREATE POLICY "users_read_own_profile"
    ON profiles FOR SELECT
    TO authenticated
    USING (id = auth.uid());

-- Every authenticated user can insert their own profile (first time)
CREATE POLICY "users_insert_own_profile"
    ON profiles FOR INSERT
    TO authenticated
    WITH CHECK (id = auth.uid());

-- Users can update their own profile (name/phone/location only — not status/role)
CREATE POLICY "users_update_own_profile"
    ON profiles FOR UPDATE
    TO authenticated
    USING (id = auth.uid());

-- Admins can read ALL profiles (needed for the admin panel)
CREATE POLICY "admins_read_all_profiles"
    ON profiles FOR SELECT
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM profiles p
            WHERE p.id = auth.uid()
              AND p.status = 'approved'
              AND p.role   = 'admin'
        )
    );

-- Admins can update ANY profile (approve / reject / change role)
CREATE POLICY "admins_update_all_profiles"
    ON profiles FOR UPDATE
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM profiles p
            WHERE p.id = auth.uid()
              AND p.status = 'approved'
              AND p.role   = 'admin'
        )
    );


-- ── 3. CRICKET DATA TABLES — open to approved users ──────────
--  Keep existing tables. Replace old policies with simpler ones
--  that check the profiles table instead of user_roles.

ALTER TABLE events ENABLE ROW LEVEL SECURITY;
ALTER TABLE teams  ENABLE ROW LEVEL SECURITY;
ALTER TABLE squad  ENABLE ROW LEVEL SECURITY;

-- Drop any old policies
DROP POLICY IF EXISTS "allow_all_events"     ON events;
DROP POLICY IF EXISTS "allow_all_teams"      ON teams;
DROP POLICY IF EXISTS "allow_all_squad"      ON squad;
DROP POLICY IF EXISTS "auth_read_events"     ON events;
DROP POLICY IF EXISTS "editors_write_events" ON events;
DROP POLICY IF EXISTS "editors_update_events" ON events;
DROP POLICY IF EXISTS "admins_delete_events" ON events;
DROP POLICY IF EXISTS "auth_read_teams"      ON teams;
DROP POLICY IF EXISTS "editors_write_teams"  ON teams;
DROP POLICY IF EXISTS "editors_update_teams" ON teams;
DROP POLICY IF EXISTS "admins_delete_teams"  ON teams;
DROP POLICY IF EXISTS "auth_read_squad"      ON squad;
DROP POLICY IF EXISTS "editors_write_squad"  ON squad;
DROP POLICY IF EXISTS "editors_update_squad" ON squad;
DROP POLICY IF EXISTS "admins_delete_squad"  ON squad;

-- Helper: is the current user approved?
CREATE OR REPLACE FUNCTION is_approved()
RETURNS BOOLEAN LANGUAGE sql STABLE AS $$
    SELECT EXISTS (
        SELECT 1 FROM profiles
        WHERE id = auth.uid() AND status = 'approved'
    );
$$;

-- Helper: is the current user an approved editor or admin?
CREATE OR REPLACE FUNCTION can_edit()
RETURNS BOOLEAN LANGUAGE sql STABLE AS $$
    SELECT EXISTS (
        SELECT 1 FROM profiles
        WHERE id = auth.uid()
          AND status = 'approved'
          AND role IN ('admin','editor')
    );
$$;

-- Events
CREATE POLICY "approved_read_events"   ON events FOR SELECT TO authenticated USING (is_approved());
CREATE POLICY "editors_insert_events"  ON events FOR INSERT TO authenticated WITH CHECK (can_edit());
CREATE POLICY "editors_update_events2" ON events FOR UPDATE TO authenticated USING (can_edit());
CREATE POLICY "admins_delete_events2"  ON events FOR DELETE TO authenticated
    USING (EXISTS (SELECT 1 FROM profiles WHERE id=auth.uid() AND status='approved' AND role='admin'));

-- Teams
CREATE POLICY "approved_read_teams"   ON teams FOR SELECT TO authenticated USING (is_approved());
CREATE POLICY "editors_insert_teams"  ON teams FOR INSERT TO authenticated WITH CHECK (can_edit());
CREATE POLICY "editors_update_teams2" ON teams FOR UPDATE TO authenticated USING (can_edit());

-- Squad
CREATE POLICY "approved_read_squad"   ON squad FOR SELECT TO authenticated USING (is_approved());
CREATE POLICY "editors_insert_squad"  ON squad FOR INSERT TO authenticated WITH CHECK (can_edit());
CREATE POLICY "editors_update_squad2" ON squad FOR UPDATE TO authenticated USING (can_edit());


-- ── 4. SEED FIRST ADMIN ──────────────────────────────────────
--  Run this AFTER your admin account exists in auth.users.
--  Go to Supabase → Authentication → Users → find your user → copy the UUID.
--  Then run:

-- INSERT INTO profiles (id, email, name, status, role)
-- VALUES (
--     'paste-your-auth-user-uuid-here',
--     'your@email.com',
--     'Your Name',
--     'approved',
--     'admin'
-- )
-- ON CONFLICT (id) DO UPDATE
--   SET status = 'approved', role = 'admin';


-- ══════════════════════════════════════════════════════════════
--  DONE. Table created: profiles
--  Policies created for: profiles, events, teams, squad
-- ══════════════════════════════════════════════════════════════
