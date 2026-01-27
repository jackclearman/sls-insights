# dashboard_email_tracking.py
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
from sqlalchemy import create_engine, text


# ----------------------------
# DB / helpers
# ----------------------------
@st.cache_resource(show_spinner=False)
def _get_engine():
    """
    Expects one of:
      1) st.secrets["POSTGRES"]["url"] = "postgresql+psycopg2://user:pass@host:5432/dbname"
    OR
      2) st.secrets["POSTGRES"] with host/dbname/user/password/port
    """
    if "POSTGRES" not in st.secrets:
        raise RuntimeError("Missing st.secrets['POSTGRES'].")

    pg = st.secrets["POSTGRES"]

    if "url" in pg and pg["url"]:
        return create_engine(pg["url"], pool_pre_ping=True)

    required = ["host", "dbname", "user", "password"]
    missing = [k for k in required if k not in pg or not pg[k]]
    if missing:
        raise RuntimeError(f"Missing POSTGRES secrets: {', '.join(missing)}")

    host = pg["host"]
    dbname = pg["dbname"]
    user = pg["user"]
    password = pg["password"]
    port = int(pg.get("port", 5432))

    # SSL defaults on (common for RDS); override with POSTGRES.sslmode if needed
    sslmode = pg.get("sslmode", "require")

    url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}?sslmode={sslmode}"
    return create_engine(url, pool_pre_ping=True)


def _read_sql(sql: str, params: dict | None = None) -> pd.DataFrame:
    engine = _get_engine()
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn, params=params or {})


def _to_dt(d: date) -> datetime:
    return datetime(d.year, d.month, d.day)


# ----------------------------
# SQL
# ----------------------------

BASE_FILTERS_SQL = """
WHERE sent_at >= :start_ts
  AND sent_at <  :end_ts
  AND delivery_status <> 'bounced'
"""

# recruiter filter (by logged-in email) is optional; we apply in Python for flexibility
SENDS_SQL = f"""
SELECT
  sent_by_email,
  recruiter_name,
  subject,
  body_text,
  sent_at,
  delivery_status,
  open_count,
  click_count,
  first_opened_at,
  last_opened_at,
  replied,
  reply_received_at,
  reply_subject,
  reply_body,
  sf_template_id,
  sf_template_name,
  sf_email_recipient_id,
  sf_contact_id,
  sf_job_id,
  sf_firm_id,
  company_name,
  recipient_jd_year,
  num_times_opened
FROM email_sends
{BASE_FILTERS_SQL}
ORDER BY sent_at DESC
LIMIT :limit;
"""

REPLIES_SQL = """
SELECT
  sent_by_email,
  recruiter_name,
  subject,
  body_text,
  sent_at,
  sf_contact_id,
  sf_job_id,
  sf_firm_id,
  company_name,
  replied,
  reply_received_at,
  reply_subject,
  reply_body
FROM email_sends
WHERE replied = TRUE
  AND reply_received_at IS NOT NULL
  AND delivery_status <> 'bounced'
  AND COALESCE(reply_subject, '') <> ''
  AND COALESCE(reply_body, '') <> ''

  -- exclude automated responses (subject OR body)
  AND NOT (
    LOWER(COALESCE(reply_subject, '') || ' ' || COALESCE(reply_body, '')) LIKE '%automatic reply%'
    OR LOWER(COALESCE(reply_subject, '') || ' ' || COALESCE(reply_body, '')) LIKE '%auto reply%'
    OR LOWER(COALESCE(reply_subject, '') || ' ' || COALESCE(reply_body, '')) LIKE '%autoreply%'
    OR LOWER(COALESCE(reply_subject, '') || ' ' || COALESCE(reply_body, '')) LIKE '%out of office%'
    OR LOWER(COALESCE(reply_subject, '') || ' ' || COALESCE(reply_body, '')) LIKE '%ooo%'
    OR LOWER(COALESCE(reply_subject, '') || ' ' || COALESCE(reply_body, '')) LIKE '%vacation%'
    OR LOWER(COALESCE(reply_subject, '') || ' ' || COALESCE(reply_body, '')) LIKE '%away from the office%'
    OR LOWER(COALESCE(reply_subject, '') || ' ' || COALESCE(reply_body, '')) LIKE '%do not monitor%'
    OR LOWER(COALESCE(reply_subject, '') || ' ' || COALESCE(reply_body, '')) LIKE '%noreply%'
  )
ORDER BY reply_received_at DESC
LIMIT :limit;
"""


# ----------------------------
# UI sections
# ----------------------------
def _kpi_row(df: pd.DataFrame):
    sent = len(df)
    opened = int((df["open_count"].fillna(0) > 0).sum()) if sent else 0
    replied = int(df["replied"].fillna(False).sum()) if sent else 0
    clickers = int((df["click_count"].fillna(0) > 0).sum()) if sent else 0

    open_rate = (opened / sent) if sent else 0.0
    reply_rate = (replied / sent) if sent else 0.0
    click_rate = (clickers / sent) if sent else 0.0

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Sent", f"{sent:,}")
    c2.metric("Opened", f"{opened:,}")
    c3.metric("Open rate", f"{open_rate:.1%}")
    c4.metric("Replied", f"{replied:,}")
    c5.metric("Reply rate", f"{reply_rate:.1%}")
    c6.metric("Click rate", f"{click_rate:.1%}")


def _render_sent_table(df: pd.DataFrame):
    st.subheader("Recent sends")

    show_cols = [
        "sent_at",
        "sent_by_email",
        "recruiter_name",
        "company_name",
        "subject",
        "delivery_status",
        "open_count",
        "click_count",
        "replied",
        "reply_received_at",
        "sf_template_name",
        "sf_contact_id",
        "sf_job_id",
    ]
    existing = [c for c in show_cols if c in df.columns]

    # make it readable
    table = df.copy()
    if "body_text" in table.columns:
        table["body_text_preview"] = table["body_text"].fillna("").astype(str).str.replace("\r", " ").str.replace("\n", " ")
        table["body_text_preview"] = table["body_text_preview"].str.slice(0, 160)
    if "reply_body" in table.columns:
        table["reply_body_preview"] = table["reply_body"].fillna("").astype(str).str.replace("\r", " ").str.replace("\n", " ")
        table["reply_body_preview"] = table["reply_body_preview"].str.slice(0, 160)

    # add previews if present
    if "body_text_preview" in table.columns and "subject" in existing:
        existing.insert(existing.index("subject") + 1, "body_text_preview")
    if "reply_subject" in table.columns and "replied" in existing:
        # show reply subject + preview near reply fields
        if "reply_subject" not in existing:
            existing.insert(existing.index("replied") + 1, "reply_subject")
        if "reply_body_preview" in table.columns:
            existing.insert(existing.index("reply_subject") + 1, "reply_body_preview")

    st.dataframe(
        table[existing],
        use_container_width=True,
        hide_index=True,
    )


def _render_replies_section(df_replies: pd.DataFrame):
    st.subheader("Emails with replies (original + reply)")
    st.caption("Automated responses are filtered out by reply_subject/reply_body content rules.")

    if df_replies.empty:
        st.info("No non-automated replies found for the current filters.")
        return

    # compact expander list
    for _, r in df_replies.iterrows():
        company = r.get("company_name") or "Unknown company"
        recruiter = r.get("recruiter_name") or "Unknown recruiter"
        sent_subject = (r.get("subject") or "").strip()
        reply_subject = (r.get("reply_subject") or "").strip()

        exp_title = (
            f"{company} • {recruiter} — "
            f"Sent: {sent_subject[:80]} — "
            f"Reply: {reply_subject[:80]}"
        )

        with st.expander(exp_title, expanded=False):
            m1, m2, m3 = st.columns([1, 1, 1])
            m1.write(f"**Sent at:** {r.get('sent_at')}")
            m2.write(f"**Reply at:** {r.get('reply_received_at')}")
            m3.write(f"**SF Contact:** {r.get('sf_contact_id') or ''}")

            left, right = st.columns(2)

            with left:
                st.markdown("#### Original email sent")
                st.markdown(f"**Subject:** {sent_subject}")
                st.text(r.get("body_text") or "")

            with right:
                st.markdown("#### Reply received")
                st.markdown(f"**Reply subject:** {reply_subject}")
                st.text(r.get("reply_body") or "")


# ----------------------------
# Main entrypoint
# ----------------------------
def render_email_tracking():
    st.title("Email Tracking")

    # Default: last 30 days
    today = datetime.now().date()
    default_start = today - timedelta(days=30)
    default_end = today + timedelta(days=1)  # end-exclusive

    with st.expander("Filters", expanded=True):
        c1, c2, c3, c4 = st.columns([1, 1, 1, 1])

        with c1:
            start_date = st.date_input("Start date", value=default_start)
        with c2:
            end_date = st.date_input("End date", value=default_end)
        with c3:
            limit = st.number_input("Max rows (sends)", min_value=50, max_value=5000, value=500, step=50)
        with c4:
            replies_limit = st.number_input("Max threads (replies)", min_value=10, max_value=500, value=50, step=10)

        st.markdown("---")

        fc1, fc2, fc3 = st.columns([1, 1, 1])
        with fc1:
            only_my_emails = st.checkbox("Only my emails", value=True)
        with fc2:
            subject_contains = st.text_input("Subject contains (optional)", value="")
        with fc3:
            company_contains = st.text_input("Company contains (optional)", value="")

    # convert to timestamps (end-exclusive)
    start_ts = _to_dt(start_date)
    end_ts = _to_dt(end_date)

    # pull sends
    try:
        df = _read_sql(
            SENDS_SQL,
            params={
                "start_ts": start_ts,
                "end_ts": end_ts,
                "limit": int(limit),
            },
        )
    except Exception as e:
        st.error(f"Could not load email_sends: {e}")
        return

    # recruiter scoping (by logged-in email)
    user_email = st.session_state.get("user_email")  # set by your login flow
    if only_my_emails and user_email:
        df = df[df["sent_by_email"].fillna("").str.lower() == str(user_email).lower()]

    # optional quick filters
    if subject_contains.strip():
        df = df[df["subject"].fillna("").str.contains(subject_contains.strip(), case=False, na=False)]
    if company_contains.strip():
        df = df[df["company_name"].fillna("").str.contains(company_contains.strip(), case=False, na=False)]

    # KPI row
    st.subheader("Summary")
    _kpi_row(df)

    # Breakdown per recruiter (useful even if you’re filtering)
    st.subheader("Breakdown")
    if not df.empty and "recruiter_name" in df.columns:
        grp = df.copy()
        grp["opened"] = grp["open_count"].fillna(0) > 0
        grp["clicked"] = grp["click_count"].fillna(0) > 0
        grp["replied_bool"] = grp["replied"].fillna(False)

        summary = (
            grp.groupby(["recruiter_name", "sent_by_email"], dropna=False)
            .agg(
                sent=("subject", "count"),
                opened=("opened", "sum"),
                clicked=("clicked", "sum"),
                replied=("replied_bool", "sum"),
            )
            .reset_index()
        )
        summary["open_rate"] = summary["opened"] / summary["sent"]
        summary["reply_rate"] = summary["replied"] / summary["sent"]
        summary["click_rate"] = summary["clicked"] / summary["sent"]

        st.dataframe(
            summary.sort_values(["reply_rate", "open_rate", "sent"], ascending=[False, False, False]),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No rows to summarize for the selected filters.")

    # Recent sends table
    st.divider()
    _render_sent_table(df)

    # Replies section (original + reply), with same “Only my emails” filter applied
    st.divider()
    try:
        df_replies = _read_sql(REPLIES_SQL, params={"limit": int(replies_limit)})
    except Exception as e:
        st.error(f"Could not load replies: {e}")
        return

    if only_my_emails and user_email and not df_replies.empty:
        df_replies = df_replies[df_replies["sent_by_email"].fillna("").str.lower() == str(user_email).lower()]

    # apply same optional filters to replies list
    if subject_contains.strip() and not df_replies.empty:
        df_replies = df_replies[df_replies["subject"].fillna("").str.contains(subject_contains.strip(), case=False, na=False)]
    if company_contains.strip() and not df_replies.empty:
        df_replies = df_replies[df_replies["company_name"].fillna("").str.contains(company_contains.strip(), case=False, na=False)]

    _render_replies_section(df_replies)
