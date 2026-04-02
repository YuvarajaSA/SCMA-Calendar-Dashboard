# app.py
# ══════════════════════════════════════════════════════════════
#  Cricket Availability Dashboard  v2
#
#  AUTH + PROFILE ROUTING (order is non-negotiable)
#  ──────────────────────────────────────────────────
#
#  1. handle_oauth_callback()
#     → If ?access_token= in URL (from Google OAuth + JS hash reader),
#       call set_session() and store Supabase user in session_state.
#
#  2. hydrate_session()
#     → On every Streamlit rerun, restore Supabase user from the
#       cached client (get_session() returns Optional[Session] directly).
#
#  3. Profile gate
#     → If no Supabase user           → show login page
#     → If Supabase user but no profile → show profile setup form
#     → If profile.status == "pending"  → show waiting screen
#     → If profile.status == "rejected" → show denied screen
#     → If profile.status == "approved" → show dashboard
#
#  SESSION STATE
#  ─────────────
#  sb_user       Supabase User object  (set by handle_oauth_callback / hydrate)
#  user_email    str
#  user_name     str  (from profiles table)
#  user_role     str  "admin"|"editor"|"viewer"
#  user_status   str  "pending"|"approved"|"rejected"
#  authenticated bool True only when status == "approved"
# ══════════════════════════════════════════════════════════════

import streamlit as st

# ── Page config — MUST be the very first Streamlit call ───────
st.set_page_config(
    page_title="Cricket Availability Dashboard",
    page_icon="🏏",
    layout="wide",
    initial_sidebar_state="expanded",
)

from config.styles import inject
inject()

# ── Step 1 + 2: OAuth callback then session hydration ─────────
from db.auth import (
    handle_oauth_callback, hydrate_session,
    is_supabase_authenticated, is_logged_in,
    get_supabase_user, current_email, current_name,
    get_role, can_edit, is_admin, logout,
)

handle_oauth_callback()   # exchange ?access_token= → Supabase session
hydrate_session()          # restore session on every rerun

# ── Step 3a: No Supabase Auth user → login ────────────────────
if not is_supabase_authenticated():
    from pages.login import render as login_page
    login_page()
    st.stop()

# ── Step 3b: Supabase user present → check profile ───────────
from db.operations import get_profile
from db.auth import get_supabase_user

user = get_supabase_user()

# Cache profile in session_state so we don't hit DB on every rerun
if not st.session_state.get("profile_checked"):
    profile = get_profile(user.id)
    st.session_state["profile_checked"] = True
    st.session_state["_cached_profile"] = profile

    if profile:
        st.session_state["user_name"]     = profile.get("name", "")
        st.session_state["user_role"]     = profile.get("role", "viewer")
        st.session_state["user_status"]   = profile.get("status", "pending")
        st.session_state["authenticated"] = (profile.get("status") == "approved")

profile = st.session_state.get("_cached_profile")
status  = st.session_state.get("user_status", "")

# ── No profile → show setup form ─────────────────────────────
if profile is None:
    from pages.profile import render_setup
    render_setup()
    st.stop()

# ── Pending → waiting screen ─────────────────────────────────
if status == "pending":
    from pages.profile import render_pending
    render_pending()
    st.stop()

# ── Rejected → denied screen ──────────────────────────────────
if status == "rejected":
    from pages.profile import render_rejected
    render_rejected()
    st.stop()

# ── Approved → dashboard ──────────────────────────────────────
if not is_logged_in():
    # Shouldn't reach here — safety fallback
    st.error("Access check failed. Please log out and try again.")
    if st.button("Log Out"):
        logout()
        st.rerun()
    st.stop()

# ── Page imports (only after full auth + approval) ────────────
from pages import (
    dashboard, calendar_view, search,
    add_event, add_team, add_squad,
    conflicts, availability, timeline, admin,
)
from db.operations import load_events, load_teams, load_squad
from utils.conflicts import detect_event_overlaps, detect_player_conflicts

# ── Sidebar ───────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="padding:1.1rem 0 1.3rem;">
        <div style="font-family:'Bebas Neue',sans-serif;font-size:2rem;
                    color:#f0b429;letter-spacing:.06em;line-height:1;">
            🏏 CRICKET
        </div>
        <div style="font-family:'Bebas Neue',sans-serif;font-size:.78rem;
                    color:#8b949e;letter-spacing:.18em;margin-top:.1rem;">
            AVAILABILITY DASHBOARD
        </div>
    </div>
    """, unsafe_allow_html=True)

    # User card
    role      = get_role()
    role_cls  = {"admin":"role-admin","editor":"role-editor","viewer":"role-viewer"}.get(role,"role-viewer")
    role_icon = {"admin":"👑","editor":"✏️","viewer":"👁"}.get(role,"👁")

    st.markdown(f"""
    <div style="background:#1c2128;border:1px solid #30363d;border-radius:10px;
                padding:.7rem .9rem;margin-bottom:1rem;">
        <div style="font-size:.84rem;font-weight:600;color:#e6edf3;
                    margin-bottom:.15rem;">{current_name()}</div>
        <div style="font-size:.7rem;color:#8b949e;overflow:hidden;
                    text-overflow:ellipsis;white-space:nowrap;
                    margin-bottom:.35rem;">{current_email()}</div>
        <span class="role-pill {role_cls}">{role_icon} {role}</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    nav_options = [
        "📊  Dashboard",
        "📅  Calendar",
        "🔍  Search",
        "⚠️  Conflicts",
        "🧑  Availability",
        "📈  Timeline",
    ]
    if can_edit():
        nav_options += ["➕  Add Event", "🏟  Add Team", "👥  Add Squad"]
    if is_admin():
        nav_options += ["🛡  Admin"]

    page = st.radio("NAVIGATE", nav_options)

    st.markdown("---")

    events_df = load_events()
    teams_df  = load_teams()
    squad_df  = load_squad()

    total_events  = len(events_df)
    total_teams   = teams_df["team_name"].nunique() if not teams_df.empty else 0
    total_players = squad_df["player_name"].nunique() if not squad_df.empty else 0
    eo = detect_event_overlaps(events_df)
    pc = detect_player_conflicts(squad_df)

    stat_rows = "".join(
        f'<div style="background:#1c2128;border:1px solid #30363d;border-radius:8px;'
        f'padding:.45rem .85rem;display:flex;align-items:center;gap:.75rem;">'
        f'<span style="font-family:\'Bebas Neue\',sans-serif;font-size:1.35rem;'
        f'color:{c};min-width:1.8rem;text-align:right;">{v}</span>'
        f'<span style="font-size:.68rem;font-weight:700;letter-spacing:.07em;'
        f'text-transform:uppercase;color:#8b949e;">{l}</span></div>'
        for v, l, c in [
            (total_events,  "Events",          "#f0b429"),
            (total_teams,   "Teams",            "#3fb950"),
            (total_players, "Players",          "#58a6ff"),
            (len(eo), "Date Conflicts",   "#f85149" if eo else "#3fb950"),
            (len(pc), "Player Conflicts", "#f85149" if pc else "#3fb950"),
        ]
    )
    st.markdown(f"""
    <div style="font-size:.6rem;font-weight:800;letter-spacing:.14em;
                text-transform:uppercase;color:#8b949e;margin-bottom:.6rem;">
        QUICK STATS
    </div>
    <div style="display:flex;flex-direction:column;gap:.35rem;">
        {stat_rows}
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🚪  Log Out", use_container_width=True, key="logout_btn"):
        logout()
        st.rerun()

    st.markdown("""
    <div style="font-size:.62rem;color:#8b949e;margin-top:.7rem;
                line-height:1.7;text-align:center;">
        Powered by <b style="color:#f0b429;">Supabase</b> + Streamlit<br>
        🔒 Internal use only
    </div>
    """, unsafe_allow_html=True)


# ── Page router ───────────────────────────────────────────────
ROUTES = {
    "📊  Dashboard":    dashboard.render,
    "📅  Calendar":     calendar_view.render,
    "🔍  Search":       search.render,
    "⚠️  Conflicts":    conflicts.render,
    "🧑  Availability": availability.render,
    "📈  Timeline":     timeline.render,
    "➕  Add Event":    add_event.render,
    "🏟  Add Team":     add_team.render,
    "👥  Add Squad":    add_squad.render,
    "🛡  Admin":        admin.render,
}

if page in ROUTES:
    ROUTES[page]()
