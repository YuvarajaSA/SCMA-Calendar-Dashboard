# db/operations.py
from __future__ import annotations

import pandas as pd
import streamlit as st
from datetime import date
from postgrest.exceptions import APIError

from db.supabase_client import get_client

_REQUIRED_EVENT_COLS = [
    "event_name", "event_type", "category", "format",
    "start_date", "end_date", "country", "gender",
]


# ═══════════════════════════════════════════════════════════════
#  READ — events / teams / squad
# ═══════════════════════════════════════════════════════════════

@st.cache_data(ttl=60, show_spinner=False)
def load_events(gender: str | None = None, category: str | None = None) -> pd.DataFrame:
    """
    Always returns a valid DataFrame.
    Guarantees required columns exist.
    Never raises KeyError.
    """
    try:
        sb = get_client()
        q  = sb.table("events").select("*").order("start_date")
        if gender:
            q = q.eq("gender", gender)
        if category:
            q = q.eq("category", category)
        data = q.execute().data or []
        df   = pd.DataFrame(data)
    except Exception:
        df = pd.DataFrame()

    # Ensure every required column exists before any caller touches them
    for col in _REQUIRED_EVENT_COLS:
        if col not in df.columns:
            df[col] = ""

    if not df.empty:
        df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")
        df["end_date"]   = pd.to_datetime(df["end_date"],   errors="coerce")
        df = df.dropna(subset=["start_date", "end_date"]).reset_index(drop=True)

    return df


@st.cache_data(ttl=60, show_spinner=False)
def load_teams() -> pd.DataFrame:
    try:
        sb   = get_client()
        resp = sb.table("teams").select("*").execute()
        return pd.DataFrame(resp.data or [])
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=60, show_spinner=False)
def load_squad() -> pd.DataFrame:
    try:
        sb   = get_client()
        resp = sb.table("squad").select("*").order("start_date").execute()
        df   = pd.DataFrame(resp.data or [])
    except Exception:
        df = pd.DataFrame()

    if not df.empty:
        for col in ["start_date", "end_date"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")
        df = df.dropna(subset=["start_date", "end_date"]).reset_index(drop=True)

    return df


def search_events(query: str, year: int | None = None) -> pd.DataFrame:
    try:
        sb   = get_client()
        resp = sb.table("events").select("*").ilike("event_name", f"%{query}%").execute()
        df   = pd.DataFrame(resp.data or [])
    except Exception:
        df = pd.DataFrame()

    for col in _REQUIRED_EVENT_COLS:
        if col not in df.columns:
            df[col] = ""

    if not df.empty:
        df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")
        df["end_date"]   = pd.to_datetime(df["end_date"],   errors="coerce")
        df = df.dropna(subset=["start_date", "end_date"]).reset_index(drop=True)
        if year:
            df = df[
                (df["start_date"].dt.year == year) |
                (df["end_date"].dt.year   == year)
            ]
    return df


def event_names() -> list[str]:
    df = load_events()
    return df["event_name"].tolist() if not df.empty else []


def teams_for_event(event_name: str) -> list[str]:
    df = load_teams()
    if df.empty or "event_name" not in df.columns:
        return []
    return df[df["event_name"] == event_name]["team_name"].tolist()


# ═══════════════════════════════════════════════════════════════
#  WRITE — events / teams / squad
# ═══════════════════════════════════════════════════════════════

def add_event(
    name: str, etype: str, category: str, fmt: str,
    start: date, end: date, country: str, gender: str,
    notes: str = "", user_id: str | None = None,
) -> tuple[bool, str]:
    sb = get_client()
    try:
        payload = {
            "event_name": name, "event_type": etype, "category": category,
            "format": fmt, "start_date": str(start), "end_date": str(end),
            "country": country, "gender": gender, "notes": notes,
        }
        if user_id:
            payload["created_by"] = user_id
        sb.table("events").insert(payload).execute()
        load_events.clear()
        return True, f"✅ Event **{name}** added."
    except APIError as e:
        if "unique" in str(e).lower() or "23505" in str(e):
            return False, f"Event **{name}** already exists."
        return False, f"Database error: {e}"


def update_event(event_id: int, payload: dict) -> tuple[bool, str]:
    sb = get_client()
    try:
        sb.table("events").update(payload).eq("id", event_id).execute()
        load_events.clear()
        return True, "Event updated."
    except APIError as e:
        return False, str(e)


def delete_event(event_id: int) -> tuple[bool, str]:
    sb = get_client()
    try:
        sb.table("events").delete().eq("id", event_id).execute()
        load_events.clear()
        return True, "Event deleted."
    except APIError as e:
        return False, str(e)


def add_team(event_name: str, team_name: str) -> tuple[bool, str]:
    sb = get_client()
    try:
        sb.table("teams").insert({
            "event_name": event_name, "team_name": team_name,
        }).execute()
        load_teams.clear()
        return True, f"✅ **{team_name}** added to *{event_name}*."
    except APIError as e:
        if "unique" in str(e).lower() or "23505" in str(e):
            return False, f"**{team_name}** already in *{event_name}*."
        return False, f"Database error: {e}"


def add_teams_bulk(event_name: str, team_names: list[str]) -> tuple[int, list[str]]:
    ok_count, warns = 0, []
    for t in team_names:
        t = t.strip()
        if not t:
            continue
        ok, msg = add_team(event_name, t)
        if ok:
            ok_count += 1
        else:
            warns.append(msg)
    return ok_count, warns


def add_player_to_squad(player: str, event_name: str, team: str) -> tuple[bool, str]:
    sb = get_client()
    try:
        resp = (
            sb.table("events")
            .select("*")
            .eq("event_name", event_name)
            .single()
            .execute()
        )
        ev = resp.data
    except Exception as e:
        return False, f"Event not found: {e}"

    try:
        sb.table("squad").insert({
            "player_name": player.strip(),
            "event_name":  event_name,
            "event_type":  ev["event_type"],
            "category":    ev["category"],
            "format":      ev["format"],
            "start_date":  ev["start_date"],
            "end_date":    ev["end_date"],
            "team":        team,
            "gender":      ev["gender"],
            "country":     ev["country"],
        }).execute()
        load_squad.clear()
        return True, f"✅ **{player}** added to {team} / {event_name}."
    except APIError as e:
        if "unique" in str(e).lower() or "23505" in str(e):
            return False, f"**{player}** already in {team} / {event_name}."
        return False, f"Database error: {e}"


def bulk_add_players(players: list[str], event_name: str, team: str) -> tuple[int, list[str]]:
    success, warns = 0, []
    for p in players:
        ok, msg = add_player_to_squad(p, event_name, team)
        if ok:
            success += 1
        else:
            warns.append(msg)
    return success, warns


# ═══════════════════════════════════════════════════════════════
#  PROFILES — profiles table only, no legacy tables
# ═══════════════════════════════════════════════════════════════

def get_profile(user_id: str) -> dict | None:
    sb = get_client()
    try:
        resp = (
            sb.table("profiles")
            .select("*")
            .eq("id", user_id)
            .maybe_single()
            .execute()
        )
        return resp.data
    except Exception:
        return None


def create_profile(user_id: str, email: str, name: str,
                   phone: str = "", location: str = "") -> tuple[bool, str]:
    sb = get_client()
    try:
        sb.table("profiles").insert({
            "id":       user_id,
            "email":    email.strip().lower(),
            "name":     name.strip(),
            "phone":    phone.strip(),
            "location": location.strip(),
            "status":   "pending",
            "role":     "viewer",
        }).execute()
        return True, "ok"
    except APIError as e:
        if "23505" in str(e) or "unique" in str(e).lower():
            return False, "profile_exists"
        return False, f"db_error:{e}"
    except Exception as e:
        return False, f"db_error:{e}"


def update_profile_details(user_id: str, name: str,
                           phone: str = "", location: str = "") -> tuple[bool, str]:
    """Users update ONLY name / phone / location — never status or role."""
    sb = get_client()
    try:
        sb.table("profiles").update({
            "name":     name.strip(),
            "phone":    phone.strip(),
            "location": location.strip(),
        }).eq("id", user_id).execute()
        return True, "ok"
    except Exception as e:
        return False, f"db_error:{e}"


def update_user_status(user_id: str, status: str) -> tuple[bool, str]:
    """Admin only. Validated before DB call."""
    if status not in ("pending", "approved", "rejected"):
        return False, "Invalid status."
    sb = get_client()
    try:
        sb.table("profiles").update({"status": status}).eq("id", user_id).execute()
        return True, "ok"
    except Exception as e:
        return False, str(e)


def update_user_role(user_id: str, role: str) -> tuple[bool, str]:
    """Admin only. Validated before DB call."""
    if role not in ("admin", "editor", "viewer"):
        return False, "Invalid role."
    sb = get_client()
    try:
        sb.table("profiles").update({"role": role}).eq("id", user_id).execute()
        return True, "ok"
    except Exception as e:
        return False, str(e)


def get_all_users() -> list[dict]:
    sb = get_client()
    try:
        resp = (
            sb.table("profiles")
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )
        return resp.data or []
    except Exception:
        return []


def get_pending_users() -> list[dict]:
    sb = get_client()
    try:
        resp = (
            sb.table("profiles")
            .select("*")
            .eq("status", "pending")
            .order("created_at", desc=True)
            .execute()
        )
        return resp.data or []
    except Exception:
        return []
