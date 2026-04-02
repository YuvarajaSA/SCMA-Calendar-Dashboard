-- ══════════════════════════════════════════════════════════════
--  Cricket Dashboard — schema_final.sql
--  Run in: Supabase → SQL Editor → New Query
--
--  ORDER:
--    1. Drop legacy tables (safe - IF EXISTS everywhere)
--    2. Drop old helper functions
--    3. Create profiles table
--    4. Create SECURITY DEFINER helper functions
--    5. Enable RLS + create policies on profiles
--    6. Enable RLS + create policies on events / teams / squad
-- ══════════════════════════════════════════════════════════════


-- ── STEP 1: DROP LEGACY TABLES ───────────────────────────────
-- These no longer exist in the new system.
-- CASCADE removes any policies/constraints attached to them.

DROP TABLE IF EXISTS user_roles      CASCADE;
DROP TABLE IF EXISTS allowed_users   CASCADE;
DROP TABLE IF EXISTS access_requests CASCADE;


-- ── STEP 2: DROP OLD HELPER FUNCTIONS ────────────────────────
-- The old versions queried profiles directly inside policies,
-- causing infinite recursion. Drop them before recreating.

DROP FUNCTION IF EXISTS is_approved() CASCADE;
DROP FUNCTION IF EXISTS is_admin()    CASCADE;
DROP FUNCTION IF EXISTS can_edit()    CASCADE;
DROP FUNCTION IF EXISTS auth_is_approved() CASCADE;
DROP FUNCTION IF EXISTS auth_is_admin()    CASCADE;
DROP FUNCTION IF EXISTS auth_can_edit()    CASCADE;


-- ── STEP 3: DROP OLD POLICIES ON DATA TABLES ─────────────────
-- Only attempt this if the tables already exist.
-- All use IF EXISTS so they are safe to run on a fresh DB.

DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'events' AND schemaname = 'public') THEN
    DROP POLICY IF EXISTS "allow_all_events"        ON public.events;
    DROP POLICY IF EXISTS "auth_read_events"         ON public.events;
    DROP POLICY IF EXISTS "editors_write_events"     ON public.events;
    DROP POLICY IF EXISTS "editors_update_events"    ON public.events;
    DROP POLICY IF EXISTS "editors_update_events2"   ON public.events;
    DROP POLICY IF EXISTS "admins_delete_events"     ON public.events;
    DROP POLICY IF EXISTS "admins_delete_events2"    ON public.events;
    DROP POLICY IF EXISTS "approved_read_events"     ON public.events;
    DROP POLICY IF EXISTS "editors_insert_events"    ON public.events;
    DROP POLICY IF EXISTS "events_select"            ON public.events;
    DROP POLICY IF EXISTS "events_insert"            ON public.events;
    DROP POLICY IF EXISTS "events_update"            ON public.events;
    DROP POLICY IF EXISTS "events_delete"            ON public.events;
  END IF;

  IF EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'teams' AND schemaname = 'public') THEN
    DROP POLICY IF EXISTS "allow_all_teams"          ON public.teams;
    DROP POLICY IF EXISTS "auth_read_teams"           ON public.teams;
    DROP POLICY IF EXISTS "editors_write_teams"       ON public.teams;
    DROP POLICY IF EXISTS "editors_update_teams"      ON public.teams;
    DROP POLICY IF EXISTS "editors_update_teams2"     ON public.teams;
    DROP POLICY IF EXISTS "admins_delete_teams"       ON public.teams;
    DROP POLICY IF EXISTS "approved_read_teams"       ON public.teams;
    DROP POLICY IF EXISTS "editors_insert_teams"      ON public.teams;
    DROP POLICY IF EXISTS "teams_select"              ON public.teams;
    DROP POLICY IF EXISTS "teams_insert"              ON public.teams;
    DROP POLICY IF EXISTS "teams_update"              ON public.teams;
    DROP POLICY IF EXISTS "teams_delete"              ON public.teams;
  END IF;

  IF EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'squad' AND schemaname = 'public') THEN
    DROP POLICY IF EXISTS "allow_all_squad"          ON public.squad;
    DROP POLICY IF EXISTS "auth_read_squad"           ON public.squad;
    DROP POLICY IF EXISTS "editors_write_squad"       ON public.squad;
    DROP POLICY IF EXISTS "editors_update_squad"      ON public.squad;
    DROP POLICY IF EXISTS "editors_update_squad2"     ON public.squad;
    DROP POLICY IF EXISTS "admins_delete_squad"       ON public.squad;
    DROP POLICY IF EXISTS "approved_read_squad"       ON public.squad;
    DROP POLICY IF EXISTS "editors_insert_squad"      ON public.squad;
    DROP POLICY IF EXISTS "squad_select"              ON public.squad;
    DROP POLICY IF EXISTS "squad_insert"              ON public.squad;
    DROP POLICY IF EXISTS "squad_update"              ON public.squad;
    DROP POLICY IF EXISTS "squad_delete"              ON public.squad;
  END IF;

  IF EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'profiles' AND schemaname = 'public') THEN
    DROP POLICY IF EXISTS "users_read_own_profile"    ON public.profiles;
    DROP POLICY IF EXISTS "users_insert_own_profile"  ON public.profiles;
    DROP POLICY IF EXISTS "users_update_own_profile"  ON public.profiles;
    DROP POLICY IF EXISTS "admins_read_all_profiles"  ON public.profiles;
    DROP POLICY IF EXISTS "admins_update_all_profiles" ON public.profiles;
    DROP POLICY IF EXISTS "profile_select_own"        ON public.profiles;
    DROP POLICY IF EXISTS "profile_select_admin"      ON public.profiles;
    DROP POLICY IF EXISTS "profile_insert_own"        ON public.profiles;
    DROP POLICY IF EXISTS "profile_update_own_safe"   ON public.profiles;
    DROP POLICY IF EXISTS "profile_update_admin"      ON public.profiles;
    DROP POLICY IF EXISTS "profile_delete_admin"      ON public.profiles;
  END IF;
END $$;


-- ── STEP 4: CREATE PROFILES TABLE ────────────────────────────

CREATE TABLE IF NOT EXISTS public.profiles (
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

CREATE INDEX IF NOT EXISTS idx_profiles_email  ON public.profiles (email);
CREATE INDEX IF NOT EXISTS idx_profiles_status ON public.profiles (status);


-- ── STEP 5: SECURITY DEFINER HELPER FUNCTIONS ─────────────────
--
--  SECURITY DEFINER means these run with postgres privileges,
--  bypassing RLS. This is the ONLY correct way to reference
--  the profiles table from within profiles policies without
--  causing infinite recursion.
--
--  set search_path = '' prevents schema injection.

CREATE OR REPLACE FUNCTION public.auth_is_approved()
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM   public.profiles
        WHERE  id     = auth.uid()
          AND  status = 'approved'
    );
$$;

CREATE OR REPLACE FUNCTION public.auth_is_admin()
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM   public.profiles
        WHERE  id     = auth.uid()
          AND  status = 'approved'
          AND  role   = 'admin'
    );
$$;

CREATE OR REPLACE FUNCTION public.auth_can_edit()
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM   public.profiles
        WHERE  id     = auth.uid()
          AND  status = 'approved'
          AND  role   IN ('admin', 'editor')
    );
$$;


-- ── STEP 6: PROFILES RLS ─────────────────────────────────────

ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

-- User reads their own row
CREATE POLICY "profile_select_own"
    ON public.profiles FOR SELECT
    TO authenticated
    USING (id = auth.uid());

-- Admin reads all rows (calls SECURITY DEFINER — no recursion)
CREATE POLICY "profile_select_admin"
    ON public.profiles FOR SELECT
    TO authenticated
    USING (public.auth_is_admin());

-- User inserts only their own row, forced to safe defaults
CREATE POLICY "profile_insert_own"
    ON public.profiles FOR INSERT
    TO authenticated
    WITH CHECK (
        id     = auth.uid()
        AND status = 'pending'
        AND role   = 'viewer'
    );

-- User updates ONLY name/phone/location on their own row.
-- WITH CHECK freezes status and role to their current DB values,
-- so a user cannot escalate their own role or self-approve.
CREATE POLICY "profile_update_own_safe"
    ON public.profiles FOR UPDATE
    TO authenticated
    USING  (id = auth.uid())
    WITH CHECK (
        id     = auth.uid()
        AND status = (SELECT p.status FROM public.profiles p WHERE p.id = auth.uid())
        AND role   = (SELECT p.role   FROM public.profiles p WHERE p.id = auth.uid())
    );

-- Admin updates any row (approve/reject/change role)
CREATE POLICY "profile_update_admin"
    ON public.profiles FOR UPDATE
    TO authenticated
    USING (public.auth_is_admin());

-- Admin deletes any row
CREATE POLICY "profile_delete_admin"
    ON public.profiles FOR DELETE
    TO authenticated
    USING (public.auth_is_admin());


-- ── STEP 7: EVENTS / TEAMS / SQUAD RLS ───────────────────────
--  Requires events, teams, squad tables to already exist.
--  These were created by your original schema. If they do not
--  exist yet, create them first (see original schema.sql).

ALTER TABLE public.events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.teams  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.squad  ENABLE ROW LEVEL SECURITY;

-- EVENTS
CREATE POLICY "events_select" ON public.events FOR SELECT TO authenticated
    USING (public.auth_is_approved());
CREATE POLICY "events_insert" ON public.events FOR INSERT TO authenticated
    WITH CHECK (public.auth_can_edit());
CREATE POLICY "events_update" ON public.events FOR UPDATE TO authenticated
    USING (public.auth_can_edit());
CREATE POLICY "events_delete" ON public.events FOR DELETE TO authenticated
    USING (public.auth_is_admin());

-- TEAMS
CREATE POLICY "teams_select" ON public.teams FOR SELECT TO authenticated
    USING (public.auth_is_approved());
CREATE POLICY "teams_insert" ON public.teams FOR INSERT TO authenticated
    WITH CHECK (public.auth_can_edit());
CREATE POLICY "teams_update" ON public.teams FOR UPDATE TO authenticated
    USING (public.auth_can_edit());
CREATE POLICY "teams_delete" ON public.teams FOR DELETE TO authenticated
    USING (public.auth_is_admin());

-- SQUAD
CREATE POLICY "squad_select" ON public.squad FOR SELECT TO authenticated
    USING (public.auth_is_approved());
CREATE POLICY "squad_insert" ON public.squad FOR INSERT TO authenticated
    WITH CHECK (public.auth_can_edit());
CREATE POLICY "squad_update" ON public.squad FOR UPDATE TO authenticated
    USING (public.auth_can_edit());
CREATE POLICY "squad_delete" ON public.squad FOR DELETE TO authenticated
    USING (public.auth_is_admin());


-- ══════════════════════════════════════════════════════════════
--  DONE. After running this:
--
--  Seed your admin account:
--  1. Log in to your app once (creates auth.users row)
--  2. Go to Supabase → Authentication → Users → copy your UUID
--  3. Run this (replace both values):
--
--  INSERT INTO public.profiles (id, email, name, status, role)
--  VALUES (
--      'your-auth-user-uuid-here',
--      'your@email.com',
--      'Your Name',
--      'approved',
--      'admin'
--  )
--  ON CONFLICT (id) DO UPDATE
--      SET status = 'approved', role = 'admin';
-- ══════════════════════════════════════════════════════════════
