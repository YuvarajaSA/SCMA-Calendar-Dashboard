# # db/auth.py
# # ══════════════════════════════════════════════════════════════
# #  Authentication — Supabase Auth + profiles table
# #
# #  VERIFIED SUPABASE-PY 2.28.x API
# #  ─────────────────────────────────
# #  sign_in_with_password()  → AuthResponse  (.session, .user)
# #  sign_up()                → AuthResponse  (.session, .user)
# #  get_session()            → Optional[Session]  ← no .session wrapper!
# #  sign_out()               → None
# #  get_user(jwt)            → Optional[UserResponse]  (.user)
# #
# #  SESSION STATE KEYS
# #  ───────────────────
# #  sb_user          : Supabase User object (has .id, .email)
# #  user_email       : str
# #  user_name        : str    from profiles table
# #  user_role        : str    "admin" | "editor" | "viewer"
# #  user_status      : str    "pending" | "approved" | "rejected"
# #  authenticated    : bool   True only when status == "approved"
# #
# #  FLOW
# #  ─────
# #  login/OAuth  →  Supabase user established
# #  hydrate_session()  →  restores Supabase user on every rerun
# #  check_profile()    →  reads profiles table, sets user_status
# #  is_logged_in()     →  True only when authenticated == True
# # ══════════════════════════════════════════════════════════════

# from __future__ import annotations
# import streamlit as st
# from db.supabase_client import get_client


# # ── Internal helpers ──────────────────────────────────────────

# def _store_supabase_user(user) -> None:
#     """Store a Supabase User object in session_state."""
#     st.session_state["sb_user"]    = user
#     st.session_state["user_email"] = user.email or ""


# def _store_profile(profile: dict) -> None:
#     """Store profiles row in session_state and set authenticated."""
#     st.session_state["user_name"]   = profile.get("name", "")
#     st.session_state["user_role"]   = profile.get("role", "viewer")
#     st.session_state["user_status"] = profile.get("status", "pending")
#     st.session_state["authenticated"] = (profile.get("status") == "approved")


# def _clear_all() -> None:
#     for k in ["sb_user","user_email","user_name","user_role",
#               "user_status","authenticated","auth_error"]:
#         st.session_state.pop(k, None)


# # ── Public session API ────────────────────────────────────────

# def get_supabase_user():
#     """Return Supabase User object or None."""
#     return st.session_state.get("sb_user")


# def is_supabase_authenticated() -> bool:
#     """True if a Supabase Auth user is present (may be pending/rejected)."""
#     return st.session_state.get("sb_user") is not None


# def is_logged_in() -> bool:
#     """True only if Supabase Auth + profile status == approved."""
#     return st.session_state.get("authenticated", False) is True


# def current_email() -> str:
#     return st.session_state.get("user_email", "")


# def current_name() -> str:
#     return st.session_state.get("user_name", "")


# def current_status() -> str:
#     return st.session_state.get("user_status", "")


# def get_role() -> str:
#     return st.session_state.get("user_role", "viewer")


# def can_edit() -> bool:
#     return get_role() in ("admin", "editor")


# def is_admin() -> bool:
#     return get_role() == "admin"


# def logout() -> None:
#     sb = get_client()
#     try:
#         sb.auth.sign_out()
#     except Exception:
#         pass
#     _clear_all()


# # ── SESSION HYDRATION ─────────────────────────────────────────
# # Must be called at the very top of app.py on every load.
# # get_session() returns Optional[Session] DIRECTLY (no .session attr).

# def hydrate_session() -> bool:
#     """
#     Restore Supabase user from cached client on every Streamlit rerun.
#     st.session_state empties on rerun; the @st.cache_resource client
#     remembers its auth state as long as the server process is alive.

#     Returns True if a Supabase user was found and stored.
#     """
#     if st.session_state.get("sb_user"):
#         return True  # already hydrated this run

#     sb = get_client()
#     try:
#         # get_session() → Optional[Session], NOT AuthResponse
#         session = sb.auth.get_session()
#         if session and hasattr(session, "user") and session.user:
#             _store_supabase_user(session.user)
#             return True
#     except Exception:
#         pass
#     return False


# # ── OAUTH CALLBACK ────────────────────────────────────────────
# # Handles ?access_token= in URL after Google OAuth redirect.
# # The JS hash reader in login.py converts #hash to ?query params.

# def handle_oauth_callback() -> bool:
#     """
#     Called at the very top of app.py, before any auth check.
#     Reads access_token from URL query params and calls set_session().

#     Returns True if a new session was established.
#     """
#     params        = st.query_params
#     access_token  = params.get("access_token")
#     refresh_token = params.get("refresh_token", "")

#     if not access_token:
#         # Check for OAuth error
#         if params.get("error"):
#             st.session_state["auth_error"] = (
#                 params.get("error_description", params.get("error"))
#             )
#             st.query_params.clear()
#         return False

#     sb = get_client()
#     try:
#         # set_session(str, str) → AuthResponse (.session, .user)
#         resp = sb.auth.set_session(access_token, refresh_token)
#         if resp and resp.session and resp.session.user:
#             _store_supabase_user(resp.session.user)
#             st.query_params.clear()
#             return True
#     except Exception as e:
#         st.session_state["auth_error"] = f"Session error: {e}"
#         st.query_params.clear()
#     return False


# # ── EMAIL / PASSWORD LOGIN ────────────────────────────────────

# def login_with_password(email: str, password: str) -> tuple[bool, str]:
#     """
#     sign_in_with_password → AuthResponse (.session, .user)
#     Returns (True, "ok") or (False, reason_string).
#     """
#     sb = get_client()
#     try:
#         resp = sb.auth.sign_in_with_password({"email": email, "password": password})
#         if resp and resp.session and resp.session.user:
#             _store_supabase_user(resp.session.user)
#             return True, "ok"
#         return False, "Invalid credentials."
#     except Exception as e:
#         msg = str(e)
#         if "invalid_credentials" in msg or "Invalid login" in msg:
#             return False, "Incorrect email or password."
#         if "Email not confirmed" in msg:
#             return False, "Please confirm your email address first."
#         return False, f"Login failed: {msg}"


# def signup_with_password(email: str, password: str, name: str) -> tuple[bool, str]:
#     """
#     sign_up → AuthResponse (.session, .user)
#     Supabase may require email confirmation depending on project settings.
#     """
#     sb = get_client()
#     try:
#         resp = sb.auth.sign_up({"email": email, "password": password})
#         if resp and resp.user:
#             if resp.session and resp.session.user:
#                 # Email confirmation not required — logged in immediately
#                 _store_supabase_user(resp.session.user)
#                 return True, "confirmed"
#             else:
#                 # Email confirmation required
#                 return True, "confirm_email"
#         return False, "Sign-up failed. Please try again."
#     except Exception as e:
#         msg = str(e)
#         if "already registered" in msg or "23505" in msg:
#             return False, "An account with this email already exists. Please log in."
#         return False, f"Sign-up error: {msg}"


# def login_with_google() -> str:
#     """
#     Build Google OAuth URL (implicit flow — no PKCE).
#     Returns URL to redirect user to, or "" on failure.

#     WHY sign_out() first:
#     Prevents 403 on second click by clearing any stale auth
#     state in the cached Supabase client object.
#     """
#     sb = get_client()
#     try:
#         sb.auth.sign_out()
#     except Exception:
#         pass

#     redirect = st.secrets["supabase"].get("redirect_url", "")
#     try:
#         resp = sb.auth.sign_in_with_oauth({
#             "provider": "google",
#             "options": {
#                 "redirect_to":  redirect,
#                 "query_params": {
#                     "access_type": "offline",
#                     "prompt":      "select_account",
#                 },
#             },
#         })
#         return resp.url if resp else ""
#     except Exception as e:
#         st.session_state["auth_error"] = f"OAuth init failed: {e}"
#         return ""










# db/auth.py
# ══════════════════════════════════════════════════════════════
#  Authentication — Supabase Auth + profiles table
#
#  VERIFIED SUPABASE-PY 2.28.x API
#  ─────────────────────────────────
#  sign_in_with_password()  → AuthResponse  (.session, .user)
#  sign_up()                → AuthResponse  (.session, .user)
#  get_session()            → Optional[Session]  ← no .session wrapper!
#  sign_out()               → None
#  get_user(jwt)            → Optional[UserResponse]  (.user)
#
#  SESSION STATE KEYS
#  ───────────────────
#  sb_user          : Supabase User object (has .id, .email)
#  user_email       : str
#  user_name        : str    from profiles table
#  user_role        : str    "admin" | "editor" | "viewer"
#  user_status      : str    "pending" | "approved" | "rejected"
#  authenticated    : bool   True only when status == "approved"
#
#  FLOW
#  ─────
#  login/OAuth  →  Supabase user established
#  hydrate_session()  →  restores Supabase user on every rerun
#  check_profile()    →  reads profiles table, sets user_status
#  is_logged_in()     →  True only when authenticated == True
# ══════════════════════════════════════════════════════════════

from __future__ import annotations
import streamlit as st
from db.supabase_client import get_client


# ── Internal helpers ──────────────────────────────────────────

def _store_supabase_user(user) -> None:
    """Store a Supabase User object in session_state."""
    st.session_state["sb_user"]    = user
    st.session_state["user_email"] = user.email or ""


def _store_profile(profile: dict) -> None:
    """Store profiles row in session_state and set authenticated."""
    st.session_state["user_name"]   = profile.get("name", "")
    st.session_state["user_role"]   = profile.get("role", "viewer")
    st.session_state["user_status"] = profile.get("status", "pending")
    st.session_state["authenticated"] = (profile.get("status") == "approved")


def _clear_all() -> None:
    for k in ["sb_user","user_email","user_name","user_role",
              "user_status","authenticated","auth_error"]:
        st.session_state.pop(k, None)


# ── Public session API ────────────────────────────────────────

def get_supabase_user():
    """Return Supabase User object or None."""
    return st.session_state.get("sb_user")


def is_supabase_authenticated() -> bool:
    """True if a Supabase Auth user is present (may be pending/rejected)."""
    return st.session_state.get("sb_user") is not None


def is_logged_in() -> bool:
    """True only if Supabase Auth + profile status == approved."""
    return st.session_state.get("authenticated", False) is True


def current_email() -> str:
    return st.session_state.get("user_email", "")


def current_name() -> str:
    return st.session_state.get("user_name", "")


def current_status() -> str:
    return st.session_state.get("user_status", "")


def get_role() -> str:
    return st.session_state.get("user_role", "viewer")


def can_edit() -> bool:
    return get_role() in ("admin", "editor")


def is_admin() -> bool:
    return get_role() == "admin"


def logout() -> None:
    sb = get_client()
    try:
        sb.auth.sign_out()
    except Exception:
        pass
    _clear_all()


# ── SESSION HYDRATION ─────────────────────────────────────────
# Must be called at the very top of app.py on every load.
# get_session() returns Optional[Session] DIRECTLY (no .session attr).

def hydrate_session() -> bool:
    """
    Restore Supabase user from cached client on every Streamlit rerun.
    st.session_state empties on rerun; the @st.cache_resource client
    remembers its auth state as long as the server process is alive.

    Returns True if a Supabase user was found and stored.
    """
    if st.session_state.get("sb_user"):
        return True  # already hydrated this run

    sb = get_client()
    try:
        # get_session() → Optional[Session], NOT AuthResponse
        session = sb.auth.get_session()
        if session and hasattr(session, "user") and session.user:
            _store_supabase_user(session.user)
            return True
    except Exception:
        pass
    return False


# handle_oauth_callback kept as no-op stub so app.py call is harmless
def handle_oauth_callback() -> bool:
    """Google OAuth removed. Returns False always."""
    return False


# ── EMAIL / PASSWORD LOGIN ────────────────────────────────────

def login_with_password(email: str, password: str) -> tuple[bool, str]:
    """
    sign_in_with_password → AuthResponse (.session, .user)
    Returns (True, "ok") or (False, reason_string).
    """
    sb = get_client()
    try:
        resp = sb.auth.sign_in_with_password({"email": email, "password": password})
        if resp and resp.session and resp.session.user:
            _store_supabase_user(resp.session.user)
            return True, "ok"
        return False, "Invalid credentials."
    except Exception as e:
        msg = str(e)
        if "invalid_credentials" in msg or "Invalid login" in msg:
            return False, "Incorrect email or password."
        if "Email not confirmed" in msg:
            return False, "Please confirm your email address first."
        return False, f"Login failed: {msg}"


def signup_with_password(email: str, password: str, name: str) -> tuple[bool, str]:
    """
    sign_up → AuthResponse (.session, .user)
    Supabase may require email confirmation depending on project settings.
    """
    sb = get_client()
    try:
        resp = sb.auth.sign_up({"email": email, "password": password})
        if resp and resp.user:
            if resp.session and resp.session.user:
                # Email confirmation not required — logged in immediately
                _store_supabase_user(resp.session.user)
                return True, "confirmed"
            else:
                # Email confirmation required
                return True, "confirm_email"
        return False, "Sign-up failed. Please try again."
    except Exception as e:
        msg = str(e)
        if "already registered" in msg or "23505" in msg:
            return False, "An account with this email already exists. Please log in."
        return False, f"Sign-up error: {msg}"


