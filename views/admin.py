# # pages/admin.py
# # ══════════════════════════════════════════════════════════════
# #  Admin Panel — User Management via profiles table
# #
# #  TABS
# #  ─────
# #  1. Pending Approval  — approve / reject new users
# #  2. All Users         — view, change role, deactivate/reactivate
# # ══════════════════════════════════════════════════════════════

# import streamlit as st
# import pandas as pd
# from db.auth import is_admin, current_email
# from db.operations import (
#     get_all_users,
#     get_pending_users,
#     update_user_status,
#     update_user_role,
# )


# def render() -> None:
#     st.markdown("""
#     <div class="page-header">
#         <div>
#             <h1>ADMIN</h1>
#             <p>User access management — approve requests, assign roles, manage access</p>
#         </div>
#     </div>
#     """, unsafe_allow_html=True)

#     if not is_admin():
#         st.markdown("""
#         <div class="alert-box alert-error">
#             <div class="icon">🔒</div>
#             <div class="body"><div class="title">Admins Only</div>
#             This page is restricted to administrators.</div>
#         </div>""", unsafe_allow_html=True)
#         return

#     # ── Role info ──────────────────────────────────────────────
#     st.markdown("""
#     <div class="alert-box alert-info">
#         <div class="icon">ℹ️</div>
#         <div class="body">
#             <div class="title">Role Permissions</div>
#             <span class="badge badge-red">admin</span>&nbsp;
#             Full access — manage users, all data, delete<br>
#             <span class="badge badge-yellow">editor</span>&nbsp;
#             Add &amp; edit events, teams, squads<br>
#             <span class="badge badge-blue">viewer</span>&nbsp;
#             Read-only — calendar, search, availability
#         </div>
#     </div>""", unsafe_allow_html=True)

#     pending = get_pending_users()
#     pending_lbl = f"⏳  Pending ({len(pending)})" if pending else "⏳  Pending"

#     tab_pending, tab_all = st.tabs([pending_lbl, "👥  All Users"])

#     # ════════════════════════════════════════════════════════
#     #  TAB 1 — PENDING APPROVAL
#     # ════════════════════════════════════════════════════════
#     with tab_pending:
#         if not pending:
#             st.markdown("""
#             <div class="alert-box alert-success">
#                 <div class="icon">✅</div>
#                 <div class="body"><div class="title">No Pending Requests</div>
#                 Everyone has been reviewed.</div>
#             </div>""", unsafe_allow_html=True)
#         else:
#             st.markdown(f"""
#             <div class="alert-box alert-warn">
#                 <div class="icon">📨</div>
#                 <div class="body"><div class="title">
#                 {len(pending)} user(s) awaiting approval</div>
#                 Choose a role before approving.</div>
#             </div>""", unsafe_allow_html=True)

#             for u in pending:
#                 joined = (u.get("created_at","")[:10])
#                 with st.container():
#                     c1, c2, c3, c4 = st.columns([3, 1.5, 1.2, 1.2])

#                     with c1:
#                         st.markdown(
#                             f'<div style="padding:.35rem 0;font-size:.88rem;">'
#                             f'<b>{u.get("name","—")}</b><br>'
#                             f'<span style="color:#8b949e;font-size:.78rem;">{u.get("email","")}</span><br>'
#                             f'<span style="color:#8b949e;font-size:.75rem;">'
#                             f'📞 {u.get("phone","—") or "—"} &nbsp;·&nbsp; '
#                             f'📍 {u.get("location","—") or "—"}</span></div>',
#                             unsafe_allow_html=True,
#                         )
#                     with c2:
#                         st.markdown(
#                             f'<div style="font-size:.78rem;color:#8b949e;padding:.5rem 0;">'
#                             f'Requested<br>{joined}</div>',
#                             unsafe_allow_html=True,
#                         )
#                     with c3:
#                         role_sel = st.selectbox(
#                             "Role", ["viewer","editor","admin"],
#                             key=f"role_pend_{u['id']}",
#                             label_visibility="collapsed",
#                         )
#                         if st.button("✅ Approve", key=f"app_{u['id']}",
#                                      use_container_width=True):
#                             update_user_status(u["id"], "approved")
#                             update_user_role(u["id"], role_sel)
#                             st.success(f"✅ {u.get('email','')} approved as {role_sel}.")
#                             st.rerun()
#                     with c4:
#                         st.markdown("<br>", unsafe_allow_html=True)
#                         if st.button("✕ Reject", key=f"rej_{u['id']}",
#                                      use_container_width=True):
#                             update_user_status(u["id"], "rejected")
#                             st.rerun()

#                 st.markdown(
#                     "<hr style='border-color:#1c2128;margin:.3rem 0;'>",
#                     unsafe_allow_html=True,
#                 )

#     # ════════════════════════════════════════════════════════
#     #  TAB 2 — ALL USERS
#     # ════════════════════════════════════════════════════════
#     with tab_all:
#         all_users = get_all_users()

#         if not all_users:
#             st.info("No profiles in the database yet.")
#             return

#         # Metrics
#         approved = sum(1 for u in all_users if u.get("status") == "approved")
#         pend_c   = sum(1 for u in all_users if u.get("status") == "pending")
#         rejected = sum(1 for u in all_users if u.get("status") == "rejected")

#         st.markdown(f"""
#         <div class="stat-row">
#             <div class="stat-chip">
#                 <div class="val">{len(all_users)}</div><div class="lbl">Total</div></div>
#             <div class="stat-chip">
#                 <div class="val" style="color:#3fb950;">{approved}</div>
#                 <div class="lbl">Approved</div></div>
#             <div class="stat-chip">
#                 <div class="val" style="color:#e3b341;">{pend_c}</div>
#                 <div class="lbl">Pending</div></div>
#             <div class="stat-chip">
#                 <div class="val" style="color:#f85149;">{rejected}</div>
#                 <div class="lbl">Rejected</div></div>
#         </div>
#         """, unsafe_allow_html=True)

#         # Filter
#         status_filter = st.selectbox(
#             "Filter by status",
#             ["All", "approved", "pending", "rejected"],
#             key="all_users_filter",
#         )
#         filtered = all_users if status_filter == "All" else [
#             u for u in all_users if u.get("status") == status_filter
#         ]

#         if not filtered:
#             st.info(f"No {status_filter} users.")
#             return

#         # Column header
#         st.markdown("""
#         <div style="display:grid;
#                     grid-template-columns:2.5fr 1.2fr 1fr 1fr 1fr 1fr;
#                     gap:.5rem;padding:.4rem .8rem;
#                     font-size:.62rem;font-weight:800;letter-spacing:.1em;
#                     text-transform:uppercase;color:#8b949e;
#                     border-bottom:1px solid #30363d;margin-bottom:.4rem;">
#             <span>Name / Email</span><span>Location</span>
#             <span>Status</span><span>Role</span>
#             <span>Change Role</span><span>Actions</span>
#         </div>""", unsafe_allow_html=True)

#         me = current_email()

#         for u in filtered:
#             status   = u.get("status", "pending")
#             role     = u.get("role",   "viewer")
#             is_me    = u.get("email","") == me
#             stat_col = {"approved":"#3fb950","pending":"#e3b341","rejected":"#f85149"}.get(status,"#8b949e")
#             role_cls = {"admin":"role-admin","editor":"role-editor","viewer":"role-viewer"}.get(role,"role-viewer")

#             c1, c2, c3, c4, c5, c6 = st.columns([2.5, 1.2, 1, 1, 1, 1])

#             with c1:
#                 you = " <span style='color:#f0b429;font-size:.7rem;'>(you)</span>" if is_me else ""
#                 st.markdown(
#                     f'<div style="font-size:.86rem;padding:.3rem 0;">'
#                     f'<b>{u.get("name","—")}</b>{you}<br>'
#                     f'<span style="font-size:.74rem;color:#8b949e;">{u.get("email","")}</span></div>',
#                     unsafe_allow_html=True,
#                 )
#             with c2:
#                 st.markdown(
#                     f'<div style="font-size:.8rem;color:#8b949e;padding:.5rem 0;">'
#                     f'{u.get("location","—") or "—"}</div>',
#                     unsafe_allow_html=True,
#                 )
#             with c3:
#                 st.markdown(
#                     f'<div style="font-size:.8rem;font-weight:700;'
#                     f'color:{stat_col};padding:.5rem 0;">{status}</div>',
#                     unsafe_allow_html=True,
#                 )
#             with c4:
#                 st.markdown(
#                     f'<div style="padding:.5rem 0;">'
#                     f'<span class="role-pill {role_cls}">{role}</span></div>',
#                     unsafe_allow_html=True,
#                 )
#             with c5:
#                 new_role = st.selectbox(
#                     "r", ["viewer","editor","admin"],
#                     index=["viewer","editor","admin"].index(role),
#                     key=f"nr_{u['id']}",
#                     label_visibility="collapsed",
#                 )
#                 if st.button("Save", key=f"sv_{u['id']}", use_container_width=True):
#                     update_user_role(u["id"], new_role)
#                     st.rerun()

#             with c6:
#                 if is_me:
#                     st.markdown(
#                         '<div style="font-size:.72rem;color:#8b949e;padding:.5rem 0;">—</div>',
#                         unsafe_allow_html=True,
#                     )
#                 else:
#                     if status == "approved":
#                         if st.button("Reject", key=f"rej2_{u['id']}",
#                                      use_container_width=True):
#                             update_user_status(u["id"], "rejected")
#                             st.rerun()
#                     elif status == "rejected":
#                         if st.button("Restore", key=f"rst_{u['id']}",
#                                      use_container_width=True):
#                             update_user_status(u["id"], "approved")
#                             st.rerun()
#                     else:  # pending
#                         if st.button("Approve", key=f"app2_{u['id']}",
#                                      use_container_width=True):
#                             update_user_status(u["id"], "approved")
#                             st.rerun()

#             st.markdown(
#                 "<hr style='border-color:#1c2128;margin:.15rem 0;'>",
#                 unsafe_allow_html=True,
#             )











# pages/admin.py  —  SCMA Admin Panel
import streamlit as st
import pandas as pd
from db.auth import is_admin, current_email
from db.operations import (
    get_all_users, update_user_status, update_user_role,
    get_activity_logs, get_all_notifications,
)


def _tab_users() -> None:
    all_users = get_all_users()
    if not all_users:
        st.info("No users found.")
        return

    approved = sum(1 for u in all_users if u.get("status")=="approved")
    pending  = sum(1 for u in all_users if u.get("status")=="pending")
    rejected = sum(1 for u in all_users if u.get("status")=="rejected")

    st.markdown(f"""
    <div class="stat-row">
        <div class="stat-chip"><div class="val">{len(all_users)}</div><div class="lbl">Total</div></div>
        <div class="stat-chip"><div class="val" style="color:#3fb950;">{approved}</div><div class="lbl">Approved</div></div>
        <div class="stat-chip"><div class="val" style="color:#e3b341;">{pending}</div><div class="lbl">Pending</div></div>
        <div class="stat-chip"><div class="val" style="color:#f85149;">{rejected}</div><div class="lbl">Rejected</div></div>
    </div>""", unsafe_allow_html=True)

    status_f = st.selectbox("Filter status",["All","approved","pending","rejected"],key="uf")
    filtered = all_users if status_f=="All" else [u for u in all_users if u.get("status")==status_f]
    me = current_email()

    for u in filtered:
        status  = u.get("status","pending")
        role    = u.get("role","viewer")
        is_me   = u.get("email","") == me
        sc      = {"approved":"#3fb950","pending":"#e3b341","rejected":"#f85149"}.get(status,"#8b949e")
        rc      = {"admin":"role-admin","editor":"role-editor","viewer":"role-viewer"}.get(role,"role-viewer")

        c1,c2,c3,c4,c5 = st.columns([2.5,1,1,1,1])
        with c1:
            you = " (you)" if is_me else ""
            st.markdown(
                f'<div style="font-size:.84rem;padding:.3rem 0;"><b>{u.get("name","—")}</b>{you}<br>'
                f'<span style="color:#8b949e;font-size:.74rem;">{u.get("email","")}</span></div>',
                unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div style="font-size:.8rem;color:{sc};padding:.5rem 0;">{status}</div>',
                        unsafe_allow_html=True)
        with c3:
            st.markdown(f'<div style="padding:.5rem 0;"><span class="role-pill {rc}">{role}</span></div>',
                        unsafe_allow_html=True)
        with c4:
            nr = st.selectbox("r",["viewer","editor","admin"],
                               index=["viewer","editor","admin"].index(role),
                               key=f"nr_{u['id']}", label_visibility="collapsed")
            if st.button("Save",key=f"sv_{u['id']}",use_container_width=True):
                update_user_role(u["id"],nr); st.rerun()
        with c5:
            if not is_me:
                if status=="approved":
                    if st.button("Reject",key=f"rj_{u['id']}",use_container_width=True):
                        update_user_status(u["id"],"rejected"); st.rerun()
                elif status=="rejected":
                    if st.button("Restore",key=f"rs_{u['id']}",use_container_width=True):
                        update_user_status(u["id"],"approved"); st.rerun()
                else:
                    if st.button("Approve",key=f"ap_{u['id']}",use_container_width=True):
                        update_user_status(u["id"],"approved"); st.rerun()
        st.markdown("<hr style='border-color:#1c2128;margin:.15rem 0;'>", unsafe_allow_html=True)


def _tab_activity() -> None:
    logs = get_activity_logs(300)
    if not logs:
        st.info("No activity logged yet.")
        return
    df = pd.DataFrame(logs)
    df["created_at"] = pd.to_datetime(df["created_at"]).dt.strftime("%Y-%m-%d %H:%M")

    c1,c2 = st.columns(2)
    with c1:
        af = st.selectbox("Action",["All"]+sorted(df["action"].unique().tolist()),key="af")
    with c2:
        ef = st.text_input("Email filter",placeholder="Search…",key="ef",label_visibility="collapsed")

    disp = df.copy()
    if af!="All":  disp = disp[disp["action"]==af]
    if ef.strip(): disp = disp[disp["user_email"].str.contains(ef.strip(),case=False,na=False)]

    show = disp[["created_at","user_email","action","entity_type","entity_id"]].rename(columns={
        "created_at":"Time","user_email":"User","action":"Action",
        "entity_type":"Entity","entity_id":"ID"
    })
    st.dataframe(show,use_container_width=True,hide_index=True)
    csv = show.to_csv(index=False)
    st.download_button("Export CSV",csv,"activity_logs.csv","text/csv",key="exp_logs")


def _tab_notifications() -> None:
    notifs = get_all_notifications(300)
    if not notifs:
        st.info("No notifications yet.")
        return
    df = pd.DataFrame(notifs)
    df["scheduled_at"] = pd.to_datetime(df["scheduled_at"]).dt.strftime("%Y-%m-%d %H:%M")

    sf  = st.selectbox("Status",["All","pending","sent","failed"],key="nf")
    disp = df if sf=="All" else df[df["status"]==sf]

    p = len(df[df["status"]=="pending"])
    s = len(df[df["status"]=="sent"])
    f = len(df[df["status"]=="failed"])
    st.markdown(f"""
    <div class="stat-row">
        <div class="stat-chip"><div class="val" style="color:#e3b341;">{p}</div><div class="lbl">Pending</div></div>
        <div class="stat-chip"><div class="val" style="color:#3fb950;">{s}</div><div class="lbl">Sent</div></div>
        <div class="stat-chip"><div class="val" style="color:#f85149;">{f}</div><div class="lbl">Failed</div></div>
    </div>""", unsafe_allow_html=True)

    if not disp.empty:
        show = disp[["scheduled_at","user_email","type","entity_type","status","message"]].rename(columns={
            "scheduled_at":"Scheduled","user_email":"To","type":"Type",
            "entity_type":"Entity","status":"Status","message":"Message"
        })
        st.dataframe(show,use_container_width=True,hide_index=True)


def render() -> None:
    st.markdown("""
    <div class="page-header">
        <div><h1>ADMIN</h1><p>Users · Activity · Notifications</p></div>
    </div>""", unsafe_allow_html=True)

    if not is_admin():
        st.markdown("""
        <div class="alert-box alert-error">
            <div class="icon">🔒</div>
            <div class="body"><div class="title">Admins Only</div></div>
        </div>""", unsafe_allow_html=True)
        return

    tab_u,tab_a,tab_n = st.tabs(["Users","Activity Logs","Notifications"])
    with tab_u: _tab_users()
    with tab_a: _tab_activity()
    with tab_n: _tab_notifications()
