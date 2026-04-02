-- ══════════════════════════════════════════════════════════════
--  Cricket Availability Dashboard v2 — Supabase Schema
--  Run this ENTIRE file in: Supabase → SQL Editor → New Query
-- ══════════════════════════════════════════════════════════════


-- ── 1. USER ROLES ────────────────────────────────────────────
--  Maps Supabase auth users to app roles.
--  Roles:  admin  → full access (add / edit / delete)
--          editor → can add & edit events, squads
--          viewer → read-only (calendar & search only)
CREATE TABLE IF NOT EXISTS user_roles (
    id         BIGSERIAL   PRIMARY KEY,
    user_id    UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    email      TEXT        NOT NULL,
    role       TEXT        NOT NULL DEFAULT 'viewer'
                           CHECK (role IN ('admin','editor','viewer')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id)
);


-- ── 2. EVENTS ────────────────────────────────────────────────
--  category : International | Domestic | League
--  country  : replaces venue — where the event is hosted
--  gender   : Male | Female | Mixed
CREATE TABLE IF NOT EXISTS events (
    id          BIGSERIAL   PRIMARY KEY,
    event_name  TEXT        NOT NULL UNIQUE,
    event_type  TEXT        NOT NULL CHECK (event_type IN ('match','series','tournament')),
    category    TEXT        NOT NULL DEFAULT 'International'
                            CHECK (category IN ('International','Domestic','League')),
    format      TEXT        NOT NULL,
    start_date  DATE        NOT NULL,
    end_date    DATE        NOT NULL,
    country     TEXT        NOT NULL,
    gender      TEXT        NOT NULL CHECK (gender IN ('Male','Female','Mixed')),
    notes       TEXT,
    created_by  UUID        REFERENCES auth.users(id),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT  chk_event_dates CHECK (end_date >= start_date)
);


-- ── 3. TEAMS ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS teams (
    id          BIGSERIAL   PRIMARY KEY,
    event_name  TEXT        NOT NULL REFERENCES events(event_name) ON DELETE CASCADE,
    team_name   TEXT        NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (event_name, team_name)
);


-- ── 4. SQUAD ─────────────────────────────────────────────────
--  Denormalised: one row per player × event × team.
CREATE TABLE IF NOT EXISTS squad (
    id          BIGSERIAL   PRIMARY KEY,
    player_name TEXT        NOT NULL,
    event_name  TEXT        NOT NULL REFERENCES events(event_name) ON DELETE CASCADE,
    event_type  TEXT        NOT NULL,
    category    TEXT        NOT NULL,
    format      TEXT        NOT NULL,
    start_date  DATE        NOT NULL,
    end_date    DATE        NOT NULL,
    team        TEXT        NOT NULL,
    gender      TEXT        NOT NULL,
    country     TEXT        NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (player_name, event_name, team)
);


-- ── 5. INDEXES ───────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_events_dates    ON events (start_date, end_date);
CREATE INDEX IF NOT EXISTS idx_events_gender   ON events (gender);
CREATE INDEX IF NOT EXISTS idx_events_category ON events (category);
CREATE INDEX IF NOT EXISTS idx_squad_player    ON squad  (player_name);
CREATE INDEX IF NOT EXISTS idx_squad_event     ON squad  (event_name);
CREATE INDEX IF NOT EXISTS idx_squad_dates     ON squad  (start_date, end_date);


-- ── 6. ROW-LEVEL SECURITY ────────────────────────────────────

ALTER TABLE user_roles ENABLE ROW LEVEL SECURITY;
ALTER TABLE events     ENABLE ROW LEVEL SECURITY;
ALTER TABLE teams      ENABLE ROW LEVEL SECURITY;
ALTER TABLE squad      ENABLE ROW LEVEL SECURITY;


-- user_roles: only admins can manage roles; users can see their own
CREATE POLICY "users_see_own_role"
    ON user_roles FOR SELECT
    TO authenticated
    USING (user_id = auth.uid());

CREATE POLICY "admins_manage_roles"
    ON user_roles FOR ALL
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM user_roles ur
            WHERE ur.user_id = auth.uid() AND ur.role = 'admin'
        )
    );


-- events: everyone (authenticated) can read
CREATE POLICY "auth_read_events"
    ON events FOR SELECT
    TO authenticated USING (true);

-- events: only admin/editor can insert/update/delete
CREATE POLICY "editors_write_events"
    ON events FOR INSERT
    TO authenticated
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM user_roles ur
            WHERE ur.user_id = auth.uid()
              AND ur.role IN ('admin','editor')
        )
    );

CREATE POLICY "editors_update_events"
    ON events FOR UPDATE
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM user_roles ur
            WHERE ur.user_id = auth.uid()
              AND ur.role IN ('admin','editor')
        )
    );

CREATE POLICY "admins_delete_events"
    ON events FOR DELETE
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM user_roles ur
            WHERE ur.user_id = auth.uid()
              AND ur.role = 'admin'
        )
    );


-- teams: same pattern as events
CREATE POLICY "auth_read_teams"   ON teams FOR SELECT TO authenticated USING (true);
CREATE POLICY "editors_write_teams" ON teams FOR INSERT TO authenticated
    WITH CHECK (EXISTS (SELECT 1 FROM user_roles ur WHERE ur.user_id=auth.uid() AND ur.role IN ('admin','editor')));
CREATE POLICY "editors_update_teams" ON teams FOR UPDATE TO authenticated
    USING (EXISTS (SELECT 1 FROM user_roles ur WHERE ur.user_id=auth.uid() AND ur.role IN ('admin','editor')));
CREATE POLICY "admins_delete_teams" ON teams FOR DELETE TO authenticated
    USING (EXISTS (SELECT 1 FROM user_roles ur WHERE ur.user_id=auth.uid() AND ur.role='admin'));

-- squad: same pattern
CREATE POLICY "auth_read_squad"   ON squad FOR SELECT TO authenticated USING (true);
CREATE POLICY "editors_write_squad" ON squad FOR INSERT TO authenticated
    WITH CHECK (EXISTS (SELECT 1 FROM user_roles ur WHERE ur.user_id=auth.uid() AND ur.role IN ('admin','editor')));
CREATE POLICY "editors_update_squad" ON squad FOR UPDATE TO authenticated
    USING (EXISTS (SELECT 1 FROM user_roles ur WHERE ur.user_id=auth.uid() AND ur.role IN ('admin','editor')));
CREATE POLICY "admins_delete_squad" ON squad FOR DELETE TO authenticated
    USING (EXISTS (SELECT 1 FROM user_roles ur WHERE ur.user_id=auth.uid() AND ur.role='admin'));


-- ── 7. HELPER FUNCTION — get current user role ───────────────
CREATE OR REPLACE FUNCTION get_my_role()
RETURNS TEXT
LANGUAGE sql STABLE
AS $$
    SELECT role FROM user_roles WHERE user_id = auth.uid() LIMIT 1;
$$;


-- ══════════════════════════════════════════════════════════════
--  AFTER RUNNING THIS SCRIPT
--  ─────────────────────────────────────────────────────────────
--  1. In Supabase Dashboard → Authentication → Providers → Google
--     Enable Google OAuth and paste your Google Client ID + Secret.
--
--  2. Also enable "Email" provider so staff can log in with email
--     + password (no Google account needed).
--
--  3. Invite your first admin:
--     a. Go to Authentication → Users → Invite user  (enter their email)
--     b. After they confirm, run this to make them admin:
--        INSERT INTO user_roles (user_id, email, role)
--        SELECT id, email, 'admin'
--        FROM auth.users
--        WHERE email = 'admin@yourcompany.com';
-- ══════════════════════════════════════════════════════════════
