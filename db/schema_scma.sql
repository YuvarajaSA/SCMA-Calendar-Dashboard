-- ══════════════════════════════════════════════════════════════
--  SCMA Calendar Dashboard — Full Production Schema
--  Run in: Supabase → SQL Editor → New Query
--  Assumes schema_final.sql has already been run (profiles + RLS helpers exist)
-- ══════════════════════════════════════════════════════════════

-- ── Extend profiles: add timezone ────────────────────────────
ALTER TABLE public.profiles
    ADD COLUMN IF NOT EXISTS timezone TEXT NOT NULL DEFAULT 'UTC';

-- ── 1. LEAGUES ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.leagues (
    id          BIGSERIAL PRIMARY KEY,
    league_name TEXT NOT NULL UNIQUE,
    country     TEXT NOT NULL DEFAULT '',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── 2. EVENTS (tournaments / series) ─────────────────────────
-- Drop created_by UUID constraint if it referenced auth.users directly
-- to avoid issues on fresh installs
CREATE TABLE IF NOT EXISTS public.events (
    id          BIGSERIAL   PRIMARY KEY,
    league_id   BIGINT      REFERENCES public.leagues(id) ON DELETE SET NULL,
    event_name  TEXT        NOT NULL UNIQUE,
    event_type  TEXT        NOT NULL DEFAULT 'tournament'
                            CHECK (event_type IN ('series','tournament')),
    category    TEXT        NOT NULL DEFAULT 'International'
                            CHECK (category IN ('International','Domestic','League')),
    format      TEXT        NOT NULL DEFAULT 'T20',
    gender      TEXT        NOT NULL DEFAULT 'Male'
                            CHECK (gender IN ('Male','Female','Mixed')),
    country     TEXT        NOT NULL DEFAULT '',
    start_date  DATE        NOT NULL,
    end_date    DATE        NOT NULL,
    notes       TEXT        DEFAULT '',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_event_dates CHECK (end_date >= start_date)
);

CREATE INDEX IF NOT EXISTS idx_events_dates    ON public.events (start_date, end_date);
CREATE INDEX IF NOT EXISTS idx_events_gender   ON public.events (gender);
CREATE INDEX IF NOT EXISTS idx_events_category ON public.events (category);
CREATE INDEX IF NOT EXISTS idx_events_league   ON public.events (league_id);

-- ── 3. TEAMS ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.teams (
    id          BIGSERIAL PRIMARY KEY,
    event_id    BIGINT    REFERENCES public.events(id) ON DELETE CASCADE,
    event_name  TEXT      NOT NULL,   -- denormalised for fast reads
    team_name   TEXT      NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (event_name, team_name)
);

CREATE INDEX IF NOT EXISTS idx_teams_event_id ON public.teams (event_id);

-- ── 4. MATCHES ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.matches (
    id          BIGSERIAL PRIMARY KEY,
    event_id    BIGINT    NOT NULL REFERENCES public.events(id) ON DELETE CASCADE,
    match_name  TEXT      NOT NULL DEFAULT '',
    match_date  DATE      NOT NULL,
    team1_id    BIGINT    REFERENCES public.teams(id) ON DELETE SET NULL,
    team2_id    BIGINT    REFERENCES public.teams(id) ON DELETE SET NULL,
    venue       TEXT      DEFAULT '',
    notes       TEXT      DEFAULT '',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_matches_event   ON public.matches (event_id);
CREATE INDEX IF NOT EXISTS idx_matches_date    ON public.matches (match_date);

-- ── 5. PLAYERS ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.players (
    id          BIGSERIAL PRIMARY KEY,
    player_name TEXT NOT NULL UNIQUE,
    country     TEXT DEFAULT '',
    role        TEXT DEFAULT '',       -- batter / bowler / allrounder / wk
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── 6. SQUAD ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.squad (
    id          BIGSERIAL PRIMARY KEY,
    event_id    BIGINT    REFERENCES public.events(id)  ON DELETE CASCADE,
    team_id     BIGINT    REFERENCES public.teams(id)   ON DELETE CASCADE,
    player_id   BIGINT    REFERENCES public.players(id) ON DELETE CASCADE,
    -- legacy denormalised columns kept for backwards compatibility
    player_name TEXT      DEFAULT '',
    event_name  TEXT      DEFAULT '',
    event_type  TEXT      DEFAULT '',
    category    TEXT      DEFAULT '',
    format      TEXT      DEFAULT '',
    start_date  DATE,
    end_date    DATE,
    team        TEXT      DEFAULT '',
    gender      TEXT      DEFAULT '',
    country     TEXT      DEFAULT '',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (player_name, event_name, team)
);

CREATE INDEX IF NOT EXISTS idx_squad_event    ON public.squad (event_id);
CREATE INDEX IF NOT EXISTS idx_squad_player   ON public.squad (player_id);
CREATE INDEX IF NOT EXISTS idx_squad_dates    ON public.squad (start_date, end_date);

-- ── 7. REGISTRATIONS ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.registrations (
    id          BIGSERIAL PRIMARY KEY,
    event_id    BIGINT    NOT NULL REFERENCES public.events(id) ON DELETE CASCADE,
    start_date  DATE      NOT NULL,
    deadline    DATE      NOT NULL,
    created_by  UUID      REFERENCES auth.users(id) ON DELETE SET NULL,
    notes       TEXT      DEFAULT '',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_reg_dates CHECK (deadline >= start_date)
);

CREATE INDEX IF NOT EXISTS idx_reg_event ON public.registrations (event_id);
CREATE INDEX IF NOT EXISTS idx_reg_dates ON public.registrations (start_date, deadline);

-- ── 8. AUCTIONS ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.auctions (
    id              BIGSERIAL PRIMARY KEY,
    event_id        BIGINT    NOT NULL REFERENCES public.events(id) ON DELETE CASCADE,
    franchise_name  TEXT      NOT NULL DEFAULT '',
    auction_date    DATE      NOT NULL,
    location        TEXT      DEFAULT '',
    notes           TEXT      DEFAULT '',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_auctions_event ON public.auctions (event_id);
CREATE INDEX IF NOT EXISTS idx_auctions_date  ON public.auctions (auction_date);

-- ── 9. CLIENTS ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.clients (
    id          BIGSERIAL PRIMARY KEY,
    client_name TEXT NOT NULL,
    email       TEXT DEFAULT '',
    phone       TEXT DEFAULT '',
    country     TEXT DEFAULT '',
    citizenship TEXT DEFAULT '',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── 10. CLIENT ↔ PLAYER MAP ──────────────────────────────────
CREATE TABLE IF NOT EXISTS public.client_player_map (
    client_id   BIGINT NOT NULL REFERENCES public.clients(id)  ON DELETE CASCADE,
    player_id   BIGINT NOT NULL REFERENCES public.players(id)  ON DELETE CASCADE,
    PRIMARY KEY (client_id, player_id)
);

-- ── 11. CLIENT ↔ EVENT MAP ───────────────────────────────────
CREATE TABLE IF NOT EXISTS public.client_event_map (
    client_id   BIGINT NOT NULL REFERENCES public.clients(id)  ON DELETE CASCADE,
    event_id    BIGINT NOT NULL REFERENCES public.events(id)   ON DELETE CASCADE,
    PRIMARY KEY (client_id, event_id)
);

-- ── 12. TRAVEL PLANS ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.travel_plans (
    id              BIGSERIAL PRIMARY KEY,
    player_id       BIGINT    NOT NULL REFERENCES public.players(id) ON DELETE CASCADE,
    event_id        BIGINT    REFERENCES public.events(id)  ON DELETE SET NULL,
    departure_date  DATE,
    arrival_date    DATE,
    from_country    TEXT DEFAULT '',
    to_country      TEXT DEFAULT '',
    notes           TEXT DEFAULT '',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_travel_player ON public.travel_plans (player_id);
CREATE INDEX IF NOT EXISTS idx_travel_event  ON public.travel_plans (event_id);

-- ── 13. VISA STATUS ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.visa_status (
    id          BIGSERIAL PRIMARY KEY,
    player_id   BIGINT    NOT NULL REFERENCES public.players(id) ON DELETE CASCADE,
    country     TEXT      NOT NULL DEFAULT '',
    visa_type   TEXT      DEFAULT '',
    status      TEXT      NOT NULL DEFAULT 'pending'
                          CHECK (status IN ('pending','approved','rejected')),
    expiry_date DATE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_visa_player ON public.visa_status (player_id);

-- ── 14. PLAYER UNAVAILABILITY ────────────────────────────────
CREATE TABLE IF NOT EXISTS public.player_unavailability (
    id          BIGSERIAL PRIMARY KEY,
    player_id   BIGINT    NOT NULL REFERENCES public.players(id) ON DELETE CASCADE,
    start_date  DATE      NOT NULL,
    end_date    DATE      NOT NULL,
    reason      TEXT      DEFAULT '',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_unavail_dates CHECK (end_date >= start_date)
);

CREATE INDEX IF NOT EXISTS idx_unavail_player ON public.player_unavailability (player_id);
CREATE INDEX IF NOT EXISTS idx_unavail_dates  ON public.player_unavailability (start_date, end_date);

-- ── 15. NOTIFICATIONS ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.notifications (
    id           BIGSERIAL PRIMARY KEY,
    user_email   TEXT      NOT NULL,
    type         TEXT      NOT NULL
                           CHECK (type IN ('event_start','match_start','registration','auction')),
    entity_id    BIGINT    NOT NULL,
    entity_type  TEXT      NOT NULL
                           CHECK (entity_type IN ('event','match','registration','auction')),
    message      TEXT      NOT NULL DEFAULT '',
    status       TEXT      NOT NULL DEFAULT 'pending'
                           CHECK (status IN ('pending','sent','failed')),
    scheduled_at TIMESTAMPTZ NOT NULL,
    sent_at      TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- prevent duplicate notifications for same user + entity + type
    UNIQUE (user_email, type, entity_id, entity_type)
);

CREATE INDEX IF NOT EXISTS idx_notif_status    ON public.notifications (status);
CREATE INDEX IF NOT EXISTS idx_notif_scheduled ON public.notifications (scheduled_at);
CREATE INDEX IF NOT EXISTS idx_notif_email     ON public.notifications (user_email);

-- ── 16. ACTIVITY LOGS ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.activity_logs (
    id          BIGSERIAL PRIMARY KEY,
    user_id     UUID      REFERENCES auth.users(id) ON DELETE SET NULL,
    user_email  TEXT      DEFAULT '',
    action      TEXT      NOT NULL,    -- login / create / update / delete
    entity_type TEXT      DEFAULT '',  -- event / match / player / etc.
    entity_id   BIGINT,
    details     JSONB     DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_logs_user    ON public.activity_logs (user_id);
CREATE INDEX IF NOT EXISTS idx_logs_created ON public.activity_logs (created_at DESC);

-- ── RLS — new tables (approved users read, editors write) ─────
DO $$ DECLARE t TEXT;
BEGIN
  FOR t IN SELECT unnest(ARRAY[
      'leagues','matches','players','registrations','auctions',
      'clients','client_player_map','client_event_map',
      'travel_plans','visa_status','player_unavailability',
      'notifications','activity_logs'
  ]) LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);

    -- SELECT: approved users
    EXECUTE format(
      'CREATE POLICY "%s_select" ON public.%I FOR SELECT TO authenticated USING (public.auth_is_approved())',
      t, t
    );

    -- INSERT / UPDATE: editors + admins
    EXECUTE format(
      'CREATE POLICY "%s_insert" ON public.%I FOR INSERT TO authenticated WITH CHECK (public.auth_can_edit())',
      t, t
    );
    EXECUTE format(
      'CREATE POLICY "%s_update" ON public.%I FOR UPDATE TO authenticated USING (public.auth_can_edit())',
      t, t
    );

    -- DELETE: admins only
    EXECUTE format(
      'CREATE POLICY "%s_delete" ON public.%I FOR DELETE TO authenticated USING (public.auth_is_admin())',
      t, t
    );
  END LOOP;
END $$;

-- ══════════════════════════════════════════════════════════════
--  DONE. New tables created:
--  leagues, matches, players, registrations, auctions,
--  clients, client_player_map, client_event_map,
--  travel_plans, visa_status, player_unavailability,
--  notifications, activity_logs
--  profiles extended with: timezone
-- ══════════════════════════════════════════════════════════════
