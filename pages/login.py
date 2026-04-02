# pages/login.py
# ══════════════════════════════════════════════════════════════
#  Login Page — Supabase Auth (Google OAuth + Email/Password)
#
#  CRITICAL: JS hash reader runs first on every load.
#  Supabase OAuth returns tokens as URL hash fragments (#).
#  Streamlit cannot read hashes — the JS snippet converts them
#  to query params (?access_token=...) which Streamlit CAN read.
#  handle_oauth_callback() in app.py then exchanges those tokens.
# ══════════════════════════════════════════════════════════════

import streamlit as st
import streamlit.components.v1 as components
from db.auth import login_with_password, signup_with_password, login_with_google


# JS converts URL #hash tokens → ?query params before Streamlit reads the URL
_HASH_READER = """
<script>
(function() {
    var hash = window.location.hash;
    if (!hash || hash.length < 2) return;
    var p = new URLSearchParams(hash.substring(1));
    var at = p.get('access_token');
    var rt = p.get('refresh_token') || '';
    var err = p.get('error');
    if (at) {
        window.location.replace(
            window.location.origin + window.location.pathname +
            '?access_token=' + encodeURIComponent(at) +
            '&refresh_token=' + encodeURIComponent(rt)
        );
    } else if (err) {
        window.location.replace(
            window.location.origin + window.location.pathname +
            '?error=' + encodeURIComponent(err) +
            '&error_description=' + encodeURIComponent(p.get('error_description') || err)
        );
    }
})();
</script>
"""


def render() -> None:
    # ── JS hash reader — inject before anything else ───────────
    components.html(_HASH_READER, height=0, scrolling=False)

    # ── Page styles ────────────────────────────────────────────
    st.markdown("""
    <style>
    .stApp {
        background:
            radial-gradient(ellipse at 15% 50%, rgba(26,111,181,.13) 0%, transparent 55%),
            radial-gradient(ellipse at 85% 15%, rgba(240,180,41,.09) 0%, transparent 50%),
            #0d1117 !important;
    }
    section[data-testid="stSidebar"] { display:none !important; }
    .main .block-container {
        padding-top:0 !important; padding-bottom:0 !important;
        max-width:100% !important;
    }
    .lc {
        background:#161b22; border:1px solid #30363d; border-radius:18px;
        padding:2.8rem 2.6rem 2.4rem;
        box-shadow:0 8px 48px rgba(0,0,0,.55), 0 1px 0 rgba(255,255,255,.04) inset;
        max-width:460px; margin:0 auto;
    }
    .google-btn > button {
        background:#fff !important; color:#1f1f1f !important;
        border:1px solid #e0e0e0 !important; border-radius:8px !important;
        font-weight:600 !important; font-size:.92rem !important;
        padding:.65rem 1.4rem !important; width:100% !important;
        letter-spacing:.01em !important;
    }
    .google-btn > button:hover {
        background:#f5f5f5 !important;
        box-shadow:0 2px 10px rgba(0,0,0,.3) !important;
        transform:none !important; opacity:1 !important;
    }
    .or-line {
        display:flex; align-items:center; gap:.9rem;
        margin:1.3rem 0; font-size:.72rem; color:#8b949e;
        font-weight:700; letter-spacing:.1em; text-transform:uppercase;
    }
    .or-line::before,.or-line::after {
        content:''; flex:1; height:1px; background:#30363d;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("<div style='min-height:6vh'></div>", unsafe_allow_html=True)
    _, mid, _ = st.columns([1, 2, 1])

    with mid:
        # Header
        st.markdown("""
        <div class="lc">
            <div style="text-align:center;margin-bottom:2rem;">
                <div style="font-size:3rem;line-height:1;margin-bottom:.6rem;">🏏</div>
                <div style="font-family:'Bebas Neue',sans-serif;font-size:2.2rem;
                            color:#f0b429;letter-spacing:.06em;line-height:1;">
                    CRICKET DASHBOARD
                </div>
                <div style="font-size:.85rem;color:#8b949e;margin-top:.45rem;">
                    Availability &amp; Conflict System
                </div>
                <div style="margin-top:.8rem;">
                    <span style="display:inline-block;padding:.2rem .85rem;
                        background:rgba(248,81,73,.1);border:1px solid rgba(248,81,73,.25);
                        border-radius:20px;font-size:.66rem;font-weight:800;
                        letter-spacing:.12em;text-transform:uppercase;color:#f85149;">
                        🔒 Internal Staff Access Only
                    </span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Error banner
        err = st.session_state.pop("auth_error", None)
        if err:
            st.markdown(f"""
            <div style="background:rgba(248,81,73,.1);border:1px solid rgba(248,81,73,.3);
                        border-radius:10px;padding:.85rem 1.1rem;margin-bottom:1rem;
                        font-size:.84rem;color:#f85149;display:flex;gap:.6rem;">
                <span>⚠️</span><span>{err}</span>
            </div>""", unsafe_allow_html=True)

        # ── Google (primary CTA) ───────────────────────────────
        st.markdown('<div class="google-btn">', unsafe_allow_html=True)
        if st.button(
            "🔵  Continue with Google",
            use_container_width=True,
            key="btn_google",
            disabled=st.session_state.get("oauth_pending", False),
        ):
            st.session_state["oauth_pending"] = True
            url = login_with_google()
            if url:
                st.markdown(
                    f'<meta http-equiv="refresh" content="0;url={url}">',
                    unsafe_allow_html=True,
                )
                st.markdown(f"""
                <div style="text-align:center;margin-top:1rem;
                            font-size:.84rem;color:#8b949e;">
                    Redirecting to Google…&nbsp;
                    <a href="{url}" target="_self" style="color:#58a6ff;">
                    Click here if not redirected</a>
                </div>""", unsafe_allow_html=True)
            else:
                st.session_state.pop("oauth_pending", None)
                st.warning("Google login not configured. Use email login below.")
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="or-line">or</div>', unsafe_allow_html=True)

        # ── Email / Password tabs ──────────────────────────────
        tab_in, tab_up = st.tabs(["Sign In", "Create Account"])

        with tab_in:
            email_in = st.text_input(
                "Email", placeholder="you@example.com", key="si_email",
                label_visibility="collapsed",
            )
            pass_in = st.text_input(
                "Password", type="password", placeholder="Password",
                key="si_pass", label_visibility="collapsed",
            )
            if st.button("Sign In →", use_container_width=True, key="btn_signin"):
                if not email_in.strip() or not pass_in:
                    st.error("Enter email and password.")
                else:
                    with st.spinner("Signing in…"):
                        ok, msg = login_with_password(email_in.strip(), pass_in)
                    if ok:
                        st.session_state.pop("oauth_pending", None)
                        st.rerun()
                    else:
                        st.error(f"❌ {msg}")

        with tab_up:
            st.caption("Create a Supabase Auth account. An admin must then approve your access.")
            email_up = st.text_input(
                "Email", placeholder="you@example.com", key="su_email",
                label_visibility="collapsed",
            )
            pass_up = st.text_input(
                "Password (min 6 chars)", type="password",
                placeholder="Choose a password", key="su_pass",
                label_visibility="collapsed",
            )
            name_up = st.text_input(
                "Your name", placeholder="Full name", key="su_name",
                label_visibility="collapsed",
            )
            if st.button("Create Account →", use_container_width=True, key="btn_signup"):
                if not email_up.strip() or not pass_up or not name_up.strip():
                    st.error("All fields required.")
                elif len(pass_up) < 6:
                    st.error("Password must be at least 6 characters.")
                else:
                    with st.spinner("Creating account…"):
                        ok, reason = signup_with_password(
                            email_up.strip(), pass_up, name_up.strip()
                        )
                    if ok and reason == "confirmed":
                        st.rerun()
                    elif ok and reason == "confirm_email":
                        st.success("✅ Account created! Check your email to confirm, then sign in.")
                    else:
                        st.error(f"❌ {reason}")

        # Footer
        st.markdown("""
        <div style="display:flex;align-items:center;justify-content:center;
                    gap:.5rem;margin-top:1.8rem;font-size:.72rem;color:#8b949e;">
            <span>🔐</span><span>Secured by Supabase Auth</span>
            <span style="color:#30363d;">·</span><span>Internal use only</span>
        </div>""", unsafe_allow_html=True)
