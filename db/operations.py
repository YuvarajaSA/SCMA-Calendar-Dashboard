# db/operations.py
# ──────────────────────────────────────────────────────────────
#  All Supabase read / write operations.
#  Uses the authenticated client (RLS enforced server-side).
# ──────────────────────────────────────────────────────────────

from __future__ import annotations

import pandas as pd
import streamlit as st
from datetime import date
from postgrest.exceptions import APIError

from db.supabase_client import get_client


# ═══════════════════════════════════════════════════════════════
#  READ HELPERS  (cached for performance on large datasets)
# ═══════════════════════════════════════════════════════════════

@st.cache_data(ttl=60, show_spinner=False)
def load_events(gender: str | None = None, category: str | None = None) -> pd.DataFrame:
    sb = get_client()
    q  = sb.table("events").select("*").order("start_date")
    if gender:
        q = q.eq("gender", gender)
    if category:
        q = q.eq("category", category)
    df = pd.DataFrame(q.execute().data)
    if not df.empty:
        df["start_date"] = pd.to_datetime(df["start_date"])
        df["end_date"]   = pd.to_datetime(df["end_date"])
    return df


@st.cache_data(ttl=60, show_spinner=False)
def load_teams() -> pd.DataFrame:
    sb   = get_client()
    resp = sb.table("teams").select("*").execute()
    return pd.DataFrame(resp.data)


@st.cache_data(ttl=60, show_spinner=False)
def load_squad() -> pd.DataFrame:
    sb   = get_client()
    resp = sb.table("squad").select("*").order("start_date").execute()
    df   = pd.DataFrame(resp.data)
    if not df.empty:
        df["start_date"] = pd.to_datetime(df["start_date"])
        df["end_date"]   = pd.to_datetime(df["end_date"])
    return df


def search_events(query: str, year: int | None = None) -> pd.DataFrame:
    """Full-text search across event_name, country, format, category."""
    sb   = get_client()
    resp = sb.table("events").select("*").ilike("event_name", f"%{query}%").execute()
    df   = pd.DataFrame(resp.data)
    if not df.empty:
        df["start_date"] = pd.to_datetime(df["start_date"])
        df["end_date"]   = pd.to_datetime(df["end_date"])
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
    if df.empty:
        return []
    return df[df["event_name"] == event_name]["team_name"].tolist()


# ═══════════════════════════════════════════════════════════════
#  WRITE HELPERS
# ═══════════════════════════════════════════════════════════════

def add_event(
    name: str,
    etype: str,
    category: str,
    fmt: str,
    start: date,
    end: date,
    country: str,
    gender: str,
    notes: str = "",
    user_id: str | None = None,
) -> tuple[bool, str]:
    sb = get_client()
    try:
        payload = {
            "event_name": name,
            "event_type": etype,
            "category":   category,
            "format":     fmt,
            "start_date": str(start),
            "end_date":   str(end),
            "country":    country,
            "gender":     gender,
            "notes":      notes,
        }
        if user_id:
            payload["created_by"] = user_id
        sb.table("events").insert(payload).execute()
        load_events.clear()
        return True, f"✅ Event **{name}** added successfully!"
    except APIError as e:
        if "unique" in str(e).lower() or "23505" in str(e):
            return False, f"Event **{name}** already exists."
        return False, f"Database error: {e}"


def update_event(event_id: int, payload: dict) -> tuple[bool, str]:
    sb = get_client()
    try:
        sb.table("events").update(payload).eq("id", event_id).execute()
        return True, "Event updated."
    except APIError as e:
        return False, str(e)


def delete_event(event_id: int) -> tuple[bool, str]:
    sb = get_client()
    try:
        sb.table("events").delete().eq("id", event_id).execute()
        return True, "Event deleted."
    except APIError as e:
        return False, str(e)


def add_team(event_name: str, team_name: str) -> tuple[bool, str]:
    sb = get_client()
    try:
        sb.table("teams").insert({
            "event_name": event_name,
            "team_name":  team_name,
        }).execute()
        load_teams.clear()
        return True, f"✅ **{team_name}** added to *{event_name}*."
    except APIError as e:
        if "unique" in str(e).lower() or "23505" in str(e):
            return False, f"**{team_name}** already in *{event_name}*."
        return False, f"Database error: {e}"


def add_teams_bulk(event_name: str, team_names: list[str]) -> tuple[int, list[str]]:
    """Insert multiple teams for one event. Returns (success_count, warnings)."""
    ok_count = 0
    warns    = []
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
    resp = (
        sb.table("events")
        .select("*")
        .eq("event_name", event_name)
        .single()
        .execute()
    )
    ev = resp.data
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


def bulk_add_players(
    players: list[str], event_name: str, team: str
) -> tuple[int, list[str]]:
    success, warns = 0, []
    for p in players:
        ok, msg = add_player_to_squad(p, event_name, team)
        if ok:
            success += 1
        else:
            warns.append(msg)
    return success, warns


# ═══════════════════════════════════════════════════════════════
#  ACCESS CONTROL  (allowed_users + access_requests)
# ═══════════════════════════════════════════════════════════════

def get_allowed_users() -> list[dict]:
    """Return all rows from allowed_users ordered by name."""
    sb   = get_client()
    resp = sb.table("allowed_users").select("*").order("name").execute()
    return resp.data or []


def create_access_request(name: str, email: str, phone: str) -> tuple[bool, str]:
    """
    Insert a new access request.
    Prevents duplicate pending requests for the same email.
    Returns (True, "ok") or (False, "duplicate"|"db_error:...")
    """
    sb = get_client()
    try:
        existing = (
            sb.table("access_requests")
            .select("id")
            .eq("email", email.strip().lower())
            .eq("status", "pending")
            .maybe_single()
            .execute()
        )
        if existing.data:
            return False, "duplicate"
    except Exception:
        pass

    try:
        sb.table("access_requests").insert({
            "name":  name.strip(),
            "email": email.strip().lower(),
            "phone": phone.strip(),
        }).execute()
        return True, "ok"
    except Exception as e:
        return False, f"db_error:{e}"


def get_pending_requests() -> list[dict]:
    """Return pending access requests, newest first."""
    sb   = get_client()
    resp = (
        sb.table("access_requests")
        .select("*")
        .eq("status", "pending")
        .order("created_at", desc=True)
        .execute()
    )
    return resp.data or []


def get_all_requests() -> list[dict]:
    """Return all requests regardless of status, newest first."""
    sb   = get_client()
    resp = (
        sb.table("access_requests")
        .select("*")
        .order("created_at", desc=True)
        .execute()
    )
    return resp.data or []


def approve_request(request_id: str, role: str = "viewer") -> tuple[bool, str]:
    """
    Approve an access request:
      1. Read request details
      2. Upsert into allowed_users
      3. Mark request as approved
    """
    sb = get_client()
    try:
        req = (
            sb.table("access_requests")
            .select("name, email, phone")
            .eq("id", request_id)
            .single()
            .execute()
        )
        if not req.data:
            return False, "Request not found."
        r = req.data
        sb.table("allowed_users").upsert({
            "email":     r["email"],
            "name":      r["name"],
            "phone":     r.get("phone", ""),
            "role":      role,
            "is_active": True,
        }).execute()
        sb.table("access_requests") \
          .update({"status": "approved"}) \
          .eq("id", request_id) \
          .execute()
        return True, f"Approved {r['email']} as **{role}**."
    except Exception as e:
        return False, f"Error: {e}"


def reject_request(request_id: str) -> tuple[bool, str]:
    """Mark an access request as rejected."""
    sb = get_client()
    try:
        sb.table("access_requests") \
          .update({"status": "rejected"}) \
          .eq("id", request_id) \
          .execute()
        return True, "Request rejected."
    except Exception as e:
        return False, f"Error: {e}"


def update_allowed_user(email: str, updates: dict) -> tuple[bool, str]:
    """Update role or is_active for a user. updates = {'role':'editor'} etc."""
    sb = get_client()
    try:
        sb.table("allowed_users").update(updates).eq("email", email).execute()
        return True, "Updated."
    except Exception as e:
        return False, f"Error: {e}"


def add_allowed_user_directly(
    email: str, name: str, phone: str = "", role: str = "viewer"
) -> tuple[bool, str]:
    """Admin adds a user directly without a request flow."""
    sb = get_client()
    try:
        sb.table("allowed_users").insert({
            "email":     email.strip().lower(),
            "name":      name.strip(),
            "phone":     phone.strip(),
            "role":      role,
            "is_active": True,
        }).execute()
        return True, f"Added {email} as **{role}**."
    except APIError as e:
        if "unique" in str(e).lower() or "23505" in str(e):
            return False, f"{email} already exists."
        return False, f"DB error: {e}"


# ═══════════════════════════════════════════════════════════════
#  PROFILES  (Supabase Auth + approval system)
# ═══════════════════════════════════════════════════════════════

def get_profile(user_id: str) -> dict | None:
    """
    Fetch profile by Supabase Auth user UUID.
    Returns dict or None if no profile exists yet.
    """
    sb = get_client()
    try:
        resp = (
            sb.table("profiles")
            .select("*")
            .eq("id", user_id)
            .maybe_single()
            .execute()
        )
        return resp.data  # None if not found
    except Exception:
        return None


def create_profile(user_id: str, email: str, name: str,
                   phone: str = "", location: str = "") -> tuple[bool, str]:
    """
    Insert a new profile row for a just-registered user.
    Status defaults to 'pending' — admin must approve.
    """
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
    """Update editable fields on a user's own profile."""
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
    """Admin: approve / reject a user. status in ('pending','approved','rejected')."""
    sb = get_client()
    try:
        sb.table("profiles").update({"status": status}).eq("id", user_id).execute()
        return True, "ok"
    except Exception as e:
        return False, str(e)


def update_user_role(user_id: str, role: str) -> tuple[bool, str]:
    """Admin: change a user's role. role in ('admin','editor','viewer')."""
    sb = get_client()
    try:
        sb.table("profiles").update({"role": role}).eq("id", user_id).execute()
        return True, "ok"
    except Exception as e:
        return False, str(e)


def get_all_users() -> list[dict]:
    """Admin: all profiles ordered by created_at desc."""
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
    """Admin: only pending profiles."""
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
