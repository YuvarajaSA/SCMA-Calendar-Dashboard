# pages/calendar_view.py
# ──────────────────────────────────────────────────────────────
#  Google Calendar-style monthly view — Desktop-first
#  • Two tabs: Men's / Women's
#  • Rich event pills: name + format + country + teams
#  • Right panel: click-to-preview event details & conflicts
#  • Conflict highlighting on cells and pills
#  • Fully responsive fallback for mobile
# ──────────────────────────────────────────────────────────────

from __future__ import annotations

import calendar
import streamlit as st
import pandas as pd
from datetime import date

from db.operations import load_events, load_squad, load_teams
from utils.conflicts import detect_event_overlaps, conflicts_for_event

# ── Constants ─────────────────────────────────────────────────
MONTHS = ["","January","February","March","April","May","June",
          "July","August","September","October","November","December"]
DOW    = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
WEEKEND = {5, 6}  # Sat, Sun indices

CAT_CLASS = {
    "International": ("pill-intl", "badge-intl"),
    "Domestic":      ("pill-dom",  "badge-dom"),
    "League":        ("pill-league","badge-league"),
}


# ── Helpers ───────────────────────────────────────────────────

def _events_on_day(events_df: pd.DataFrame, d: date) -> pd.DataFrame:
    ts = pd.Timestamp(d)
    return events_df[
        (events_df["start_date"] <= ts) & (events_df["end_date"] >= ts)
    ]


def _pill_html(ev: pd.Series, conflict_names: set, teams_map: dict) -> str:
    cat      = ev.get("category", "International")
    pill_cls = CAT_CLASS.get(cat, ("pill-intl", "badge-intl"))[0]
    fem_cls  = " pill-female" if ev.get("gender") == "Female" else ""
    conf_cls = " pill-conflict" if ev["event_name"] in conflict_names else ""
    name     = ev["event_name"]
    fmt      = ev.get("format", "")
    country  = ev.get("country", "")
    teams    = teams_map.get(name, [])
    teams_str = " vs ".join(teams[:2]) + (" +more" if len(teams) > 2 else "") if teams else ""
    short    = (name[:26] + "…") if len(name) > 28 else name
    title    = name.replace('"', "'")
    flag     = " ⚠️" if name in conflict_names else ""

    return (
        f'<span class="gcal-pill {pill_cls}{fem_cls}{conf_cls}" title="{title}">'
        f'  <div class="gcal-pill-name">{short}{flag}</div>'
        f'  <div class="gcal-pill-meta">{fmt} · {country}</div>'
        f'  <div class="gcal-pill-teams">{teams_str}</div>'
        f'</span>'
    )


def _build_calendar_html(
    year: int, month: int,
    events_df: pd.DataFrame,
    conflict_names: set,
    teams_map: dict,
    max_pills: int = 3,
) -> str:
    today   = date.today()
    cal     = calendar.monthcalendar(year, month)

    # Day-of-week header
    dow_html = "".join(
        f'<div class="gcal-dow-cell{"  weekend" if i in WEEKEND else ""}">{d}</div>'
        for i, d in enumerate(DOW)
    )

    cells = ""
    for week in cal:
        for dow_idx, day_num in enumerate(week):
            if day_num == 0:
                cells += '<div class="gcal-cell gcal-other"></div>'
                continue

            d       = date(year, month, day_num)
            evs     = _events_on_day(events_df, d)
            is_today   = d == today
            is_weekend = dow_idx in WEEKEND
            has_conf   = any(ev["event_name"] in conflict_names for _, ev in evs.iterrows())

            cls = "gcal-cell"
            if is_today:   cls += " gcal-today"
            if is_weekend: cls += " gcal-weekend"
            if has_conf:   cls += " has-conflict"

            # Day number
            if is_today:
                day_num_html = (
                    f'<div class="gcal-day-num">'
                    f'<span class="gcal-today-circle">{day_num}</span></div>'
                )
            else:
                day_num_html = f'<div class="gcal-day-num">{day_num}</div>'

            # Pill rendering with overflow
            pills = ""
            total = len(evs)
            for i, (_, ev) in enumerate(evs.iterrows()):
                if i >= max_pills:
                    more = total - max_pills
                    pills += f'<span class="gcal-more">+{more} more</span>'
                    break
                pills += _pill_html(ev, conflict_names, teams_map)

            cells += f'<div class="{cls}">{day_num_html}{pills}</div>'

    return (
        f'<div class="gcal-wrapper">'
        f'  <div class="gcal-dow-row">{dow_html}</div>'
        f'  <div class="gcal-grid">{cells}</div>'
        f'</div>'
    )


def _legend() -> str:
    items = [
        ("rgba(26,111,181,.85)", "International"),
        ("rgba(26,107,58,.85)",  "Domestic"),
        ("rgba(107,58,122,.85)", "League"),
        ("#ff7eb6",              "Women's events (border)"),
        ("#f85149",              "⚠️ Conflict"),
    ]
    inner = "".join(
        f'<div class="gcal-legend-item">'
        f'<div class="gcal-legend-dot" style="background:{c};"></div>{l}</div>'
        for c, l in items
    )
    return f'<div class="gcal-legend">{inner}</div>'


def _right_panel_empty() -> None:
    st.markdown("""
    <div class="detail-panel">
        <div class="detail-panel-title">EVENT DETAILS</div>
        <div style="font-size:.82rem;color:#8b949e;text-align:center;padding:2rem 0;">
            Select a month with events to see details below.
        </div>
    </div>
    """, unsafe_allow_html=True)


def _right_panel(
    events_in_month: pd.DataFrame,
    all_events: pd.DataFrame,
    squad_df: pd.DataFrame,
    teams_map: dict,
    conflict_names: set,
) -> None:
    st.markdown('<div class="detail-panel-title">EVENT DETAILS</div>', unsafe_allow_html=True)

    if events_in_month.empty:
        st.markdown(
            '<div style="font-size:.82rem;color:#8b949e;">No events this month.</div>',
            unsafe_allow_html=True,
        )
        return

    # Event selector
    ev_names = events_in_month["event_name"].tolist()
    sel_ev   = st.selectbox("Event", ev_names, key="rp_event_sel", label_visibility="collapsed")

    row = events_in_month[events_in_month["event_name"] == sel_ev].iloc[0]
    cat = row.get("category", "International")
    badge_map = {"International":"badge-intl","Domestic":"badge-dom","League":"badge-league"}
    cat_badge = badge_map.get(cat, "badge-blue")
    gen_badge = "badge-blue" if row["gender"] == "Male" else "badge-pink"
    teams     = teams_map.get(sel_ev, [])
    duration  = (row["end_date"] - row["start_date"]).days + 1

    # Badges
    st.markdown(f"""
    <div style="display:flex;gap:.4rem;flex-wrap:wrap;margin-bottom:.9rem;">
        <span class="badge {cat_badge}">{cat}</span>
        <span class="badge {gen_badge}">{row['gender']}</span>
        <span class="badge badge-blue">{row['format']}</span>
        <span class="badge badge-yellow">{row['event_type']}</span>
        {"<span class='badge badge-red'>⚠️ Conflict</span>" if sel_ev in conflict_names else ""}
    </div>
    """, unsafe_allow_html=True)

    # Key details
    details = [
        ("Country",  row["country"]),
        ("Start",    str(row["start_date"].date())),
        ("End",      str(row["end_date"].date())),
        ("Duration", f"{duration} day(s)"),
        ("Teams",    f"{len(teams)} registered" if teams else "None yet"),
    ]
    for label, val in details:
        st.markdown(
            f'<div class="detail-row">'
            f'<span class="detail-label">{label}</span>'
            f'<span class="detail-val">{val}</span></div>',
            unsafe_allow_html=True,
        )

    # Notes
    if row.get("notes"):
        st.markdown(f"""
        <div style="margin-top:.8rem;font-size:.8rem;color:#8b949e;
                    border-left:2px solid var(--border);padding-left:.7rem;
                    line-height:1.5;">{row['notes']}</div>
        """, unsafe_allow_html=True)

    # Teams list
    if teams:
        st.markdown('<div class="section-label" style="margin-top:.9rem;">Teams</div>',
                    unsafe_allow_html=True)
        tags = " ".join(
            f'<span style="display:inline-block;background:var(--surface3);'
            f'border:1px solid var(--border);border-radius:20px;'
            f'padding:.15rem .6rem;font-size:.75rem;margin:2px;">{t}</span>'
            for t in teams
        )
        st.markdown(tags, unsafe_allow_html=True)

    # Conflict summary
    st.markdown('<div class="section-label" style="margin-top:.9rem;">Conflicts</div>',
                unsafe_allow_html=True)
    cfls = conflicts_for_event(sel_ev, all_events, squad_df)
    total_c = len(cfls["event"]) + len(cfls["player"]) + len(cfls["team"])

    if total_c == 0:
        st.markdown("""
        <div class="alert-box alert-success" style="margin-bottom:.4rem;">
            <div class="icon">✅</div>
            <div class="body" style="font-size:.8rem;">No conflicts detected.</div>
        </div>""", unsafe_allow_html=True)
    else:
        for c in cfls["event"]:
            other = c["Event B"] if c["Event A"] == sel_ev else c["Event A"]
            st.markdown(f"""
            <div class="alert-box alert-error" style="margin-bottom:.4rem;">
                <div class="icon">📅</div>
                <div class="body" style="font-size:.79rem;">
                    <b>Date clash</b> with {other}
                </div>
            </div>""", unsafe_allow_html=True)
        if cfls["player"]:
            st.markdown(f"""
            <div class="alert-box alert-warn" style="margin-bottom:.4rem;">
                <div class="icon">👤</div>
                <div class="body" style="font-size:.79rem;">
                    <b>{len(cfls['player'])} player conflict(s)</b>
                </div>
            </div>""", unsafe_allow_html=True)
        if cfls["team"]:
            st.markdown(f"""
            <div class="alert-box alert-warn" style="margin-bottom:.4rem;">
                <div class="icon">🏟</div>
                <div class="body" style="font-size:.79rem;">
                    <b>{len(cfls['team'])} team conflict(s)</b>
                </div>
            </div>""", unsafe_allow_html=True)


def _render_gender_calendar(gender: str) -> None:
    # ── Load data ──────────────────────────────────────────
    events_df  = load_events(gender=gender)
    all_events = load_events()
    squad_df   = load_squad()
    teams_df   = load_teams()

    # Build teams lookup: event_name → [team1, team2, …]
    teams_map: dict = {}
    if not teams_df.empty:
        for ev_name, grp in teams_df.groupby("event_name"):
            teams_map[ev_name] = grp["team_name"].tolist()

    # Conflict detection
    overlaps       = detect_event_overlaps(all_events)
    conflict_names = {o["Event A"] for o in overlaps} | {o["Event B"] for o in overlaps}

    # ── Year / month selectors ─────────────────────────────
    today     = date.today()
    min_year  = (events_df["start_date"].dt.year.min() if not events_df.empty else today.year)
    max_year  = (events_df["end_date"].dt.year.max()   if not events_df.empty else today.year + 1)
    year_list = list(range(min(min_year, today.year), max(max_year, today.year + 1) + 1))

    ctrl_col1, ctrl_col2, ctrl_col3 = st.columns([1, 1, 5])
    with ctrl_col1:
        try:
            default_yr_idx = year_list.index(today.year)
        except ValueError:
            default_yr_idx = 0
        sel_year = st.selectbox("Year",  year_list, index=default_yr_idx, key=f"yr_{gender}")
    with ctrl_col2:
        sel_month = st.selectbox(
            "Month", list(range(1, 13)), index=today.month - 1,
            format_func=lambda m: MONTHS[m], key=f"mo_{gender}",
        )
    with ctrl_col3:
        # Conflict summary chip
        if overlaps:
            st.markdown(
                f'<div style="margin-top:1.6rem;">'
                f'<span class="badge badge-red">⚠️ {len(overlaps)} event conflict(s)</span></div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div style="margin-top:1.6rem;">'
                '<span class="badge badge-green">✅ No conflicts</span></div>',
                unsafe_allow_html=True,
            )

    # Month bounds
    last_day    = calendar.monthrange(sel_year, sel_month)[1]
    month_start = pd.Timestamp(date(sel_year, sel_month, 1))
    month_end   = pd.Timestamp(date(sel_year, sel_month, last_day))

    month_events = pd.DataFrame()
    if not events_df.empty:
        month_events = events_df[
            (events_df["start_date"] <= month_end) &
            (events_df["end_date"]   >= month_start)
        ].copy()

    # ── Desktop 2-panel layout: calendar (left) + detail (right) ──
    cal_col, panel_col = st.columns([4, 1])

    with cal_col:
        # Month nav header
        st.markdown(f"""
        <div class="gcal-nav">
            <div class="gcal-month-label">{MONTHS[sel_month]} {sel_year}</div>
            <div style="font-size:.78rem;color:#8b949e;">
                {len(month_events)} event(s) this month
            </div>
        </div>
        """, unsafe_allow_html=True)

        cal_html = _build_calendar_html(
            sel_year, sel_month, month_events, conflict_names, teams_map,
            max_pills=4,
        )
        st.markdown(cal_html, unsafe_allow_html=True)
        st.markdown(_legend(), unsafe_allow_html=True)

    with panel_col:
        st.markdown('<div class="detail-panel">', unsafe_allow_html=True)
        _right_panel(month_events, all_events, squad_df, teams_map, conflict_names)
        st.markdown('</div>', unsafe_allow_html=True)

    # ── Events list for this month (desktop dense table) ──
    if not month_events.empty:
        st.markdown("---")
        st.markdown(
            f'<div class="card-title">📋 {MONTHS[sel_month]} {sel_year} — All Events</div>',
            unsafe_allow_html=True,
        )

        # Filter row
        fc1, fc2, fc3 = st.columns(3)
        with fc1:
            f_cat = st.selectbox("Category", ["All","International","Domestic","League"],
                                 key=f"fc_{gender}")
        with fc2:
            f_fmt = st.selectbox(
                "Format",
                ["All"] + sorted(month_events["format"].unique().tolist()),
                key=f"ff_{gender}",
            )
        with fc3:
            f_conf = st.selectbox("Conflicts", ["All","Conflicts only","No conflicts"],
                                  key=f"fco_{gender}")

        disp = month_events.copy()
        if f_cat  != "All":             disp = disp[disp["category"] == f_cat]
        if f_fmt  != "All":             disp = disp[disp["format"]   == f_fmt]
        if f_conf == "Conflicts only":  disp = disp[disp["event_name"].isin(conflict_names)]
        if f_conf == "No conflicts":    disp = disp[~disp["event_name"].isin(conflict_names)]

        out = disp[["event_name","category","format","start_date","end_date","country","event_type"]].copy()
        out["start_date"] = out["start_date"].dt.date
        out["end_date"]   = out["end_date"].dt.date
        out["conflict"]   = out["event_name"].apply(lambda n: "⚠️" if n in conflict_names else "—")
        out["teams"]      = out["event_name"].apply(lambda n: len(teams_map.get(n, [])))
        out.columns       = ["Event","Category","Format","Start","End","Country","Type","Conflict","Teams"]
        st.dataframe(out, use_container_width=True, hide_index=True)


def render() -> None:
    st.markdown("""
    <div class="page-header">
        <div>
            <h1>CRICKET CALENDAR</h1>
            <p>International · Domestic · Leagues — full schedule across formats & genders</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    tab_male, tab_female = st.tabs(["🔵  Men's Cricket", "🌸  Women's Cricket"])

    with tab_male:
        _render_gender_calendar("Male")

    with tab_female:
        _render_gender_calendar("Female")
