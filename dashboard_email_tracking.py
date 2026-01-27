import os
from datetime import datetime, timedelta
from typing import Optional, Tuple
import re

import pytz
import pandas as pd
import psycopg2
import psycopg2.extras
import streamlit as st

# Admin emails who can toggle company-wide view
ADMIN_EMAILS = {"jack@swanlegal.com", "jenny@swanlegal.com"}
PST = pytz.timezone("America/Los_Angeles")

# Heuristic filters for automated replies
AUTO_REPLY_PATTERNS = [
    r"automatic reply",
    r"\bauto\s*reply\b",
    r"\bautoreply\b",
    r"out of office",
    r"\booo\b",
    r"vacation",
    r"away from (the )?office",
    r"do not (monitor|check)",
    r"\bnoreply\b",
    r"\bno-reply\b",
    r"mailer-daemon",
    r"delivery status notification",
    r"undeliverable",
]


def is_automated_reply(reply_subject: Optional[str], reply_body: Optional[str]) -> bool:
    hay = f"{reply_subject or ''} {reply_body or ''}".strip().lower()
    if not hay:
        return True
    for pat in AUTO_REPLY_PATTERNS:
        if re.search(pat, hay, flags=re.IGNORECASE):
            return True
    return False


def to_pst_safe(dt):
    """Convert any datetime-like value to PST safely."""
    if pd.isna(dt):
        return None
    ts = pd.to_datetime(dt, errors="coerce")
    if ts is None or pd.isna(ts):
        return None
    # If tz-naive, assume UTC
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    return ts.tz_convert(PST)


def get_db_conn():
    """Open a new DB connection using environment variables.

    Expects: DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
    """
    # Prefer environment variables (useful for local runs)
    host = os.environ.get("DB_HOST")
    dbname = os.environ.get("DB_NAME")
    port = os.environ.get("DB_PORT", "5432")
    user = os.environ.get("DB_USER")
    password = os.environ.get("DB_PASSWORD")

    # Fallback to Streamlit secrets (useful for Streamlit Cloud or .streamlit/secrets.toml)
    try:
        secrets = st.secrets
    except Exception:
        secrets = {}

    if not host:
        host = secrets.get("DB_HOST") or secrets.get("DATABASE", {}).get("host")
    if not dbname:
        dbname = secrets.get("DB_NAME") or secrets.get("DATABASE", {}).get("name")
    if not port:
        port = secrets.get("DB_PORT") or secrets.get("DATABASE", {}).get("port", "5432")
    if not user:
        user = secrets.get("DB_USER") or secrets.get("DATABASE", {}).get("user")
    if not password:
        password = secrets.get("DB_PASSWORD") or secrets.get("DATABASE", {}).get("password")

    if not host or not dbname:
        raise RuntimeError("Database environment variables not set (DB_HOST/DB_NAME)")

    params = dict(host=host, port=port, dbname=dbname, user=user, password=password)
    return psycopg2.connect(**params)


def _admin_where_clause(admin: bool, recruiter_email: str):
    if admin:
        # Always exclude Jack’s test sends, regardless of who’s logged in
        return "WHERE e.recruiter_email NOT IN (%s)", ["jack@swanlegal.com"]
    else:
        # Normal recruiter view (only their own emails)
        return "WHERE e.recruiter_email = %s", [recruiter_email]


@st.cache_data(ttl=300)
def fetch_emails_paginated(
    recruiter_email: str,
    admin: bool,
    start_date: datetime,
    end_date: datetime,
    template_id: Optional[str],
    limit: int,
    offset: int,
) -> Tuple[pd.DataFrame, int]:
    """Return paginated email rows and total count."""
    where_clause, base_params = _admin_where_clause(admin, recruiter_email)

    date_filter = "e.sent_timestamp BETWEEN %s AND %s"
    if where_clause:
        where_sql = f"{where_clause} AND {date_filter}"
    else:
        where_sql = f"WHERE {date_filter}"

    template_filter = ""
    template_params: list = []
    if template_id:
        template_filter = " AND e.sf_template_id = %s"
        template_params = [template_id]

    # Count query
    count_sql = f"""
        SELECT COUNT(*)
        FROM email_sends e
        {where_sql}
        {template_filter}
    """
    count_params = base_params + [start_date, end_date] + template_params

    # Data query (NOW includes reply_subject/reply_body)
    data_sql = f"""
        SELECT
            e.sent_timestamp AS sent_at,
            e.delivery_status AS delivery_status,
            e.contact_name,
            e.recipient_jd_year,
            e.sf_email_recipient_id AS contact_id,
            e.sf_account_id AS account_id,
            e.company_name AS company_name,
            e.subject AS subject,
            COALESCE(e.sf_template_name, '(None)') AS template_name,
            COALESCE(e.recipient_email, '') AS recipient_email,
            e.body_html AS body_html,
            e.body_text AS body_text,
            e.open_count,
            e.click_count,
            e.replied,
            e.reply_received_at,
            e.reply_subject,
            e.reply_body
        FROM email_sends e
        {where_sql}
        {template_filter}
        ORDER BY e.sent_timestamp DESC
        LIMIT %s OFFSET %s
    """
    data_params = base_params + [start_date, end_date] + template_params + [limit, offset]

    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(count_sql, count_params)
            count_row = cur.fetchone()
            total = count_row[0] if count_row else 0

        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            expected_placeholders = data_sql.count("%s")
            if len(data_params) != expected_placeholders:
                st.error(
                    f"Parameter mismatch in email query: expected {expected_placeholders}, got {len(data_params)}"
                )
                st.stop()
            cur.execute(data_sql, data_params)
            rows = cur.fetchall()

    df = pd.DataFrame(rows)
    return df, int(total)


@st.cache_data(ttl=300)
def fetch_replied_threads(
    recruiter_email: str,
    admin: bool,
    start_date: datetime,
    end_date: datetime,
    template_id: Optional[str],
    limit: int = 50,
) -> pd.DataFrame:
    """Fetch emails that have replies, excluding automated responses (heuristic)."""
    where_clause, base_params = _admin_where_clause(admin, recruiter_email)

    date_filter = "e.reply_received_at BETWEEN %s AND %s"
    if where_clause:
        where_sql = f"{where_clause} AND {date_filter}"
    else:
        where_sql = f"WHERE {date_filter}"

    template_filter = ""
    template_params: list = []
    if template_id:
        template_filter = " AND e.sf_template_id = %s"
        template_params = [template_id]

    # Pull candidates; filter automated in Python (more flexible)
    sql = f"""
        SELECT
            e.sent_timestamp AS sent_at,
            e.contact_name,
            e.recipient_jd_year,
            e.sf_email_recipient_id AS contact_id,
            e.sf_account_id AS account_id,
            e.company_name,
            e.subject,
            COALESCE(e.sf_template_name, '(None)') AS template_name,
            COALESCE(e.recipient_email, '') AS recipient_email,
            e.body_html,
            e.body_text,
            e.reply_received_at,
            e.reply_subject,
            e.reply_body
        FROM email_sends e
        {where_sql}
          AND (e.replied IS TRUE OR e.reply_received_at IS NOT NULL)
          AND COALESCE(e.reply_subject, '') <> ''
          AND COALESCE(e.reply_body, '') <> ''
          AND e.delivery_status <> 'bounced'
        {template_filter}
        ORDER BY e.reply_received_at DESC
        LIMIT %s
    """
    params = base_params + [start_date, end_date] + template_params + [limit]

    with get_db_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # exclude automated replies
    df = df[~df.apply(lambda r: is_automated_reply(r.get("reply_subject"), r.get("reply_body")), axis=1)].copy()
    return df


@st.cache_data(ttl=300)
def fetch_templates(recruiter_email: str, admin: bool) -> pd.DataFrame:
    """Return templates available to the recruiter (or all for admin)."""
    where_clause, params = _admin_where_clause(admin, recruiter_email)
    if where_clause:
        where_clause = where_clause + " AND e.sf_template_id IS NOT NULL"
    else:
        where_clause = "WHERE e.sf_template_id IS NOT NULL"

    sql = f"""
    SELECT DISTINCT e.sf_template_id AS id, e.sf_template_name AS name
    FROM email_sends e
    {where_clause}
    ORDER BY name
    """

    with get_db_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    return pd.DataFrame(rows)


@st.cache_data(ttl=300)
def fetch_kpis(
    recruiter_email: str,
    admin: bool,
    start_date: datetime,
    end_date: datetime,
    template_id: Optional[str] = None,
) -> dict:
    """Fetch KPI metrics based on open_count/replied, not delivery_status text."""
    where_clause, base_params = _admin_where_clause(admin, recruiter_email)
    template_filter = ""
    template_params: list = []
    if template_id:
        template_filter = " AND e.sf_template_id = %s"
        template_params = [template_id]

    if where_clause:
        where_sql = where_clause + " AND e.sent_timestamp BETWEEN %s AND %s"
    else:
        where_sql = "WHERE e.sent_timestamp BETWEEN %s AND %s"

    sql = f"""
    SELECT
      COUNT(*) AS total_sent,
      COUNT(*) FILTER (
        WHERE COALESCE(e.open_count, 0) > 0
           OR e.replied IS TRUE
           OR e.reply_received_at IS NOT NULL
      ) AS total_opens,
      COUNT(*) FILTER (
        WHERE e.replied IS TRUE
           OR e.reply_received_at IS NOT NULL
      ) AS total_replies
    FROM email_sends e
    {where_sql}
    AND e.sf_job_name IS NOT NULL
    AND e.sf_template_name IS NOT NULL
    {template_filter}
    """

    params = base_params + [start_date, end_date] + template_params
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()

    if not row:
        return {"total_sent": 0, "total_opens": 0, "total_replies": 0}

    return {
        "total_sent": int(row[0] or 0),
        "total_opens": int(row[1] or 0),
        "total_replies": int(row[2] or 0),
    }


@st.cache_data(ttl=300)
def fetch_top_templates(
    recruiter_email: str,
    admin: bool,
    start_date: datetime,
    end_date: datetime,
    top_n: int = 10,
) -> pd.DataFrame:
    """Return top templates by open rate using open_count/replied flags."""
    where_clause, params = _admin_where_clause(admin, recruiter_email)
    if where_clause:
        where_sql = where_clause + " AND e.sent_timestamp BETWEEN %s AND %s"
    else:
        where_sql = "WHERE e.sent_timestamp BETWEEN %s AND %s"

    sql = f"""
    SELECT 
        e.sf_template_id AS template_id,
        e.sf_template_name AS template_name,
        COUNT(*) AS sent_count,
        COUNT(*) FILTER (
          WHERE COALESCE(e.open_count, 0) > 0
             OR e.replied IS TRUE
             OR e.reply_received_at IS NOT NULL
        ) AS opens,
        (
          COUNT(*) FILTER (
            WHERE COALESCE(e.open_count, 0) > 0
               OR e.replied IS TRUE
               OR e.reply_received_at IS NOT NULL
          )::float
          / NULLIF(COUNT(*), 0)
        ) AS open_rate
    FROM email_sends e
    {where_sql}
    AND e.sf_template_name IS NOT NULL
    AND e.sf_job_name IS NOT NULL
    GROUP BY e.sf_template_id, e.sf_template_name
    HAVING COUNT(*) > 0
    ORDER BY open_rate DESC NULLS LAST, opens DESC
    LIMIT %s
    """

    query_params = params + [start_date, end_date, top_n]
    with get_db_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, query_params)
            rows = cur.fetchall()
    return pd.DataFrame(rows)


@st.cache_data(ttl=300)
def fetch_performance_by_job(
    recruiter_email: str,
    admin: bool,
    start_date: datetime,
    end_date: datetime,
    template_id: Optional[str] = None,
    limit: int = 100,
) -> pd.DataFrame:
    """Aggregate performance metrics per job using open_count/replied logic."""
    where_clause, base_params = _admin_where_clause(admin, recruiter_email)
    template_filter = ""
    template_params: list = []
    if template_id:
        template_filter = " AND e.sf_template_id = %s"
        template_params = [template_id]

    if where_clause:
        where_sql = where_clause + " AND e.sent_timestamp BETWEEN %s AND %s"
    else:
        where_sql = "WHERE e.sent_timestamp BETWEEN %s AND %s"

    sql = f"""
    WITH per_job AS (
        SELECT
            e.sf_job_id AS job_id,
            e.sf_job_name AS job_name,
            COUNT(*) AS sent_count,
            COUNT(*) FILTER (
              WHERE COALESCE(e.open_count, 0) > 0
                 OR e.replied IS TRUE
                 OR e.reply_received_at IS NOT NULL
            ) AS opens,
            COUNT(*) FILTER (
              WHERE e.replied IS TRUE
                 OR e.reply_received_at IS NOT NULL
            ) AS replies,
            (
              COUNT(*) FILTER (
                WHERE COALESCE(e.open_count, 0) > 0
                   OR e.replied IS TRUE
                   OR e.reply_received_at IS NOT NULL
              )::float
              / NULLIF(COUNT(*),0)
            ) AS open_rate,
            (
              COUNT(*) FILTER (
                WHERE e.replied IS TRUE
                   OR e.reply_received_at IS NOT NULL
              )::float
              / NULLIF(COUNT(*),0)
            ) AS reply_rate,
            MAX(e.sent_timestamp) AS last_sent_at
        FROM email_sends e
        {where_sql}
        AND e.sf_job_name IS NOT NULL
        AND e.sf_template_name IS NOT NULL
        {template_filter}
        GROUP BY e.sf_job_id, e.sf_job_name
    )
    SELECT *
    FROM per_job
    ORDER BY last_sent_at DESC NULLS LAST
    LIMIT %s
    """

    params = base_params + [start_date, end_date] + template_params + [limit]
    with get_db_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
    return pd.DataFrame(rows)


def build_salesforce_link(contact_id: Optional[str], account_id: Optional[str]) -> str:
    base = os.environ.get(
        "SALESFORCE_BASE_URL",
        "https://momentum-site-8441.lightning.force.com/",
    )
    if contact_id:
        return f"{base}/{contact_id}/view"
    if account_id:
        return f"{base}/{account_id}/view"
    return ""


def render_email_tracking():
    st.title("Email Tracking")

    user_email = st.session_state.get("user_email")
    if not user_email:
        st.error("User not logged in (st.session_state['user_email'] missing)")
        return

    admin_view = st.checkbox("View company-wide metrics", value=False)

    window_label = st.selectbox(
        "Time window",
        ["1 day", "7 days", "2 weeks", "30 days", "90 days", "180 days", "1 year"],
        index=2,
    )
    mapping = {
        "1 day": 1,
        "7 days": 7,
        "2 weeks": 14,
        "30 days": 30,
        "90 days": 90,
        "180 days": 180,
        "1 year": 365,
    }
    days = mapping[window_label]
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    templates_df = fetch_templates(user_email, admin_view)
    template_options = [("All Templates", None)]
    if not templates_df.empty:
        template_options += list(zip(templates_df.get("name", []), templates_df.get("id", [])))
    template_display = [t[0] for t in template_options]
    sel_idx = st.selectbox("Template", template_display)
    template_id = None
    for name, tid in template_options:
        if name == sel_idx:
            template_id = tid
            break

    # KPI overview
    kpis = fetch_kpis(user_email, admin_view, start_date, end_date, template_id)
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Emails Sent", f"{kpis['total_sent']:,}")
    col2.metric("Total Opens", f"{kpis['total_opens']:,}")
    col3.metric("Total Replies", f"{kpis['total_replies']:,}")

    st.markdown("---")

    # Performance by Job
    st.subheader("Performance by Job")
    st.markdown(
        """
    Shows per-job performance: job name, last sent date, emails sent, open & reply rates.
    """
    )
    perf_df = fetch_performance_by_job(
        user_email, admin_view, start_date, end_date, template_id, limit=100
    )
    if perf_df.empty:
        st.info("No job-level data for the selected filters.")
    else:
        disp = perf_df.copy()
        disp["open_rate"] = (disp["open_rate"] * 100).round(1).astype(str) + "%"
        disp["reply_rate"] = (disp["reply_rate"] * 100).round(1).astype(str) + "%"
        disp["last_sent_at"] = disp["last_sent_at"].apply(
            lambda x: to_pst_safe(x).strftime("%Y-%m-%d %I:%M %p") if pd.notna(x) else ""
        )

        st.dataframe(
            disp[["job_name", "last_sent_at", "sent_count", "open_rate", "reply_rate"]],
            width="stretch",
        )

    # Top templates
    st.subheader("Top Templates by Open Rate")
    top_templates = fetch_top_templates(user_email, admin_view, start_date, end_date, top_n=10)
    if top_templates.empty:
        st.info("No template data for selected range.")
    else:
        st.dataframe(
            top_templates.assign(
                open_rate=lambda d: (d.open_rate * 100).round(1).astype(str) + "%"
            )[["template_name", "sent_count", "opens", "open_rate"]].rename(
                columns={
                    "template_name": "Template",
                    "sent_count": "Sent",
                    "opens": "Opens",
                    "open_rate": "Open Rate",
                }
            ),
            width="stretch",
        )

    st.markdown("---")

    # ----------------------------
    # NEW: Emails with Replies
    # ----------------------------
    st.subheader("Emails with Replies (original + reply)")
    st.caption("Automated responses are excluded.")

    replies_limit = st.number_input("Max reply threads to show", min_value=10, max_value=500, value=50, step=10)

    replies_df = fetch_replied_threads(
        user_email, admin_view, start_date, end_date, template_id, limit=int(replies_limit)
    )

    if replies_df.empty:
        st.info("No non-automated replies found for the selected filters.")
    else:
        for _, r in replies_df.iterrows():
            pst_sent = to_pst_safe(r.get("sent_at"))
            pst_reply = to_pst_safe(r.get("reply_received_at"))

            sent_display = pst_sent.strftime("%Y-%m-%d %I:%M %p") if pst_sent else "(no sent time)"
            reply_display = pst_reply.strftime("%Y-%m-%d %I:%M %p") if pst_reply else "(no reply time)"

            recipient = r.get("contact_name") or "(Unknown Recipient)"
            jd = r.get("recipient_jd_year")
            if pd.notna(jd):
                try:
                    recipient = f"{recipient} (JD {int(jd)})"
                except Exception:
                    pass

            company_name = r.get("company_name") or "Unknown Firm"
            company_link = (
                f"[{company_name}]({build_salesforce_link(None, r.get('account_id'))})"
                if r.get("account_id")
                else company_name
            )

            subject = r.get("subject") or "(no subject)"
            reply_subject = r.get("reply_subject") or "(no reply subject)"

            header = (
                f"**{subject}** — {recipient} | {company_link}  \n"
                f"Sent: {sent_display} • Reply: {reply_display}"
            )

            with st.expander(header):
                left, right = st.columns(2)

                with left:
                    st.markdown("#### Original email sent")
                    st.markdown(f"**Subject:** {subject}")
                    if r.get("body_html"):
                        cleaned_html = r["body_html"]
                        for tag in ["<html>", "</html>", "<body>", "</body>", "<head>", "</head>"]:
                            cleaned_html = cleaned_html.replace(tag, "")
                        safe_html = f"""
                        <div style="
                            background-color: white;
                            color: black;
                            padding: 16px;
                            border-radius: 10px;
                            line-height: 1.6;
                            font-family: Arial, sans-serif;
                        ">
                            {cleaned_html}
                        </div>
                        """
                        st.components.v1.html(safe_html, height=450, scrolling=True)
                    elif r.get("body_text"):
                        st.markdown(
                            f"""
                            <div style="
                                background-color: white;
                                color: black;
                                padding: 16px;
                                border-radius: 10px;
                                line-height: 1.6;
                                font-family: Arial, sans-serif;
                                white-space: pre-wrap;
                            ">
                                {r["body_text"]}
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                    else:
                        st.info("No email body stored for this message.")

                with right:
                    st.markdown("#### Reply received")
                    st.markdown(f"**Reply subject:** {reply_subject}")
                    reply_body = r.get("reply_body") or ""
                    st.markdown(
                        f"""
                        <div style="
                            background-color: white;
                            color: black;
                            padding: 16px;
                            border-radius: 10px;
                            line-height: 1.6;
                            font-family: Arial, sans-serif;
                            white-space: pre-wrap;
                        ">
                            {reply_body}
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

    st.markdown("---")

    # Paginated table
    st.subheader("Emails")
    page_size = 50
    if "email_page" not in st.session_state:
        st.session_state.email_page = 0

    offset = st.session_state.email_page * page_size
    df_page, total = fetch_emails_paginated(
        user_email, admin_view, start_date, end_date, template_id, limit=page_size, offset=offset
    )

    st.write(f"Showing {min(total, offset+1)}-{min(total, offset+page_size)} of {total:,} emails")

    if df_page.empty:
        st.info("No emails found for the selected filters.")
    else:
        display = df_page.copy()

        if not display["sent_at"].empty:
            display["sent_at"] = pd.to_datetime(display["sent_at"])

        display["Opened"] = (
            display.get("open_count", 0).fillna(0) > 0
        ) | display.get("replied", False).fillna(False) | display.get("reply_received_at").notna()

        display["Replied"] = (
            display.get("replied", False).fillna(False)
            | display.get("reply_received_at").notna()
        )

        display["Recipient"] = display.apply(
            lambda r: f"{r.get('contact_name','')} (JD {int(r['recipient_jd_year'])})"
            if pd.notna(r.get("recipient_jd_year"))
            else r.get("contact_name", ""),
            axis=1,
        )

        display["SF Link"] = display.apply(
            lambda r: build_salesforce_link(r.get("contact_id"), r.get("account_id")), axis=1
        )

        display = display.rename(
            columns={
                "sent_at": "Sent Date",
                "subject": "Subject",
                "template_name": "Template",
                "recipient_email": "Recipient Email",
                "delivery_status": "Status",
            }
        )

        st.markdown("### 📧 View Email Content")
        for _, row in display.iterrows():
            pst_time = to_pst_safe(row["Sent Date"])
            sent_display = pst_time.strftime("%Y-%m-%d %I:%M %p") if pst_time else "(no timestamp)"

            status_label = (row.get("Status") or "sent").lower()
            if row.get("Replied", False):
                status_label = "replied"
            elif row.get("Opened", False):
                status_label = "opened"

            recipient_name = row.get("Recipient") or "(Unknown Recipient)"
            company_name = row.get("company_name") or "Unknown Firm"
            company_link = (
                f"[{company_name}]({build_salesforce_link(None, row.get('account_id'))})"
                if row.get("account_id")
                else company_name
            )

            header = (
                f"**{row['Subject']}** — {recipient_name} | {company_link}  \n"
                f"{sent_display} | **Status:** {status_label}"
            )

            with st.expander(header):
                # Original email
                if row.get("body_html"):
                    cleaned_html = row["body_html"]
                    for tag in ["<html>", "</html>", "<body>", "</body>", "<head>", "</head>"]:
                        cleaned_html = cleaned_html.replace(tag, "")
                    safe_html = f"""
                    <div style="
                        background-color: white;
                        color: black;
                        padding: 16px;
                        border-radius: 10px;
                        line-height: 1.6;
                        font-family: Arial, sans-serif;
                    ">
                        {cleaned_html}
                    </div>
                    """
                    st.components.v1.html(safe_html, height=600, scrolling=True)
                elif row.get("body_text"):
                    st.markdown(
                        f"""
                        <div style="
                            background-color: white;
                            color: black;
                            padding: 16px;
                            border-radius: 10px;
                            line-height: 1.6;
                            font-family: Arial, sans-serif;
                            white-space: pre-wrap;
                        ">
                            {row["body_text"]}
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                else:
                    st.info("No email body stored for this message.")

                # Reply (only if present + not automated)
                reply_subject = row.get("reply_subject")
                reply_body = row.get("reply_body")
                if reply_subject or reply_body:
                    if not is_automated_reply(reply_subject, reply_body):
                        st.markdown("---")
                        st.markdown("#### Reply received")
                        st.markdown(f"**Reply subject:** {reply_subject or '(no reply subject)'}")
                        st.markdown(
                            f"""
                            <div style="
                                background-color: white;
                                color: black;
                                padding: 16px;
                                border-radius: 10px;
                                line-height: 1.6;
                                font-family: Arial, sans-serif;
                                white-space: pre-wrap;
                            ">
                                {reply_body or ''}
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

    # Pagination controls
    colp1, colp2, colp3 = st.columns([1, 6, 1])
    with colp1:
        if st.button("Prev"):
            if st.session_state.email_page > 0:
                st.session_state.email_page -= 1
                st.rerun()
    with colp3:
        if st.button("Next"):
            if (offset + page_size) < total:
                st.session_state.email_page += 1
                st.rerun()


if __name__ == "__main__":
    render_email_tracking()
