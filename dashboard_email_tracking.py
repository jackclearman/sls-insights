import os
from datetime import datetime, timedelta
from typing import Optional, Tuple

import pandas as pd
import psycopg2
import psycopg2.extras
import streamlit as st

# Admin emails who can toggle company-wide view
ADMIN_EMAILS = {"jack@swanlegal.com", "jenny@swanlegal.com"}


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


def _admin_where_clause(admin: bool, recruiter_email: str) -> Tuple[str, list]:
    """Return a WHERE clause and params for recruiter vs admin scoping.

    NOTE: we build SQL fragments here (not user inputs) and keep values in params.
    """
    if admin:
        return "", []
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

    # Proper WHERE clause
    date_filter = "e.sent_timestamp BETWEEN %s AND %s"
    if where_clause:
        where_sql = f"{where_clause} AND {date_filter}"
    else:
        where_sql = f"WHERE {date_filter}"

    template_filter = ""
    template_params = []
    if template_id:
        template_filter = " AND e.sf_template_id = %s"
        template_params = [template_id]

    # ✅ Correct param order: recruiter_email → start_date → end_date → template_id
    count_sql = f"""
        SELECT COUNT(*)
        FROM email_sends e
        {where_sql}
        {template_filter}
    """
    count_params = base_params + [start_date, end_date] + template_params

    data_sql = f"""
        WITH latest_events AS (
            SELECT DISTINCT ON (email_id) email_id, sf_account_id
            FROM email_tracking_events
            ORDER BY email_id, event_timestamp DESC
        )
        SELECT e.sent_timestamp AS sent_at,
               e.delivery_status AS delivery_status,
               NULL::text AS e.contact_name,
               NULL::int AS e.recipient_jd_year,
               e.sf_email_recipient_id AS contact_id,
               le.sf_account_id AS account_id,
               e.subject AS subject,
               COALESCE(e.sf_template_name, '(None)') AS template_name,
               CASE WHEN e.delivery_status ILIKE 'open%%' OR e.delivery_status ILIKE 'replied%%' THEN TRUE ELSE FALSE END AS opened,
               CASE WHEN e.delivery_status ILIKE 'replied%%' THEN TRUE ELSE FALSE END AS replied,

               COALESCE(e.recipient_email, '') AS recipient_email,
               e.body_html AS body_html,
               e.body_text AS body_text


        FROM email_sends e
        LEFT JOIN latest_events le ON le.email_id = e.email_id
        {where_sql}
        {template_filter}
        ORDER BY e.sent_timestamp DESC
        LIMIT %s OFFSET %s
    """
    data_params = base_params + [start_date, end_date] + template_params + [limit, offset]

    # --- Execute queries safely
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(count_sql, count_params)
            count_row = cur.fetchone()
            total = count_row[0] if count_row else 0
    
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            expected_placeholders = data_sql.count("%s")
            if len(data_params) != expected_placeholders:
                st.error(f"Parameter mismatch in email query: expected {expected_placeholders}, got {len(data_params)}")
                st.stop()
    
            cur.execute(data_sql, data_params)
            rows = cur.fetchall()


    df = pd.DataFrame(rows)
    return df, int(total)

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
def fetch_kpis(recruiter_email: str, admin: bool, start_date: datetime, end_date: datetime, template_id: Optional[str] = None) -> dict:
    """Fetch KPI metrics using same open/reply logic as bottom section."""
    where_clause, base_params = _admin_where_clause(admin, recruiter_email)
    template_filter = ""
    template_params = []
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
      COUNT(*) FILTER (WHERE e.delivery_status ILIKE 'open%%' OR e.delivery_status ILIKE 'replied%%') AS total_opens,
      COUNT(*) FILTER (WHERE e.delivery_status ILIKE 'replied%%') AS total_replies
    FROM email_sends e
    {where_sql}
    {template_filter}
    """

    params = base_params + [start_date, end_date] + template_params
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
    if not row:
        return {"total_sent": 0, "total_opens": 0, "total_replies": 0}
    return {"total_sent": int(row[0] or 0), "total_opens": int(row[1] or 0), "total_replies": int(row[2] or 0)}

@st.cache_data(ttl=300)
def fetch_top_templates(recruiter_email: str, admin: bool, start_date: datetime, end_date: datetime, top_n: int = 10) -> pd.DataFrame:
    """Return top templates by open rate, matching bottom-section logic."""
    where_clause, params = _admin_where_clause(admin, recruiter_email)
    if where_clause:
        where_sql = where_clause + " AND e.sent_timestamp BETWEEN %s AND %s"
    else:
        where_sql = "WHERE e.sent_timestamp BETWEEN %s AND %s"

    sql = f"""
    SELECT 
        e.sf_template_id AS template_id,
        COALESCE(e.sf_template_name, '(None)') AS template_name,
        COUNT(*) AS sent_count,
        COUNT(*) FILTER (WHERE e.delivery_status ILIKE 'open%%' OR e.delivery_status ILIKE 'replied%%') AS opens,
        (COUNT(*) FILTER (WHERE e.delivery_status ILIKE 'open%%' OR e.delivery_status ILIKE 'replied%%')::float
         / NULLIF(COUNT(*), 0)) AS open_rate
    FROM email_sends e
    {where_sql}
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
    limit: int = 100
) -> pd.DataFrame:
    """Aggregate performance metrics per job using same open/reply logic as bottom section."""
    where_clause, base_params = _admin_where_clause(admin, recruiter_email)
    template_filter = ""
    template_params = []
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
            COALESCE(e.sf_job_name, '(Unspecified)') AS job_name,
            COUNT(*) AS sent_count,
            COUNT(*) FILTER (WHERE e.delivery_status ILIKE 'open%%' OR e.delivery_status ILIKE 'replied%%') AS opens,
            COUNT(*) FILTER (WHERE e.delivery_status ILIKE 'replied%%') AS replies,
            (COUNT(*) FILTER (WHERE e.delivery_status ILIKE 'open%%' OR e.delivery_status ILIKE 'replied%%')::float
             / NULLIF(COUNT(*),0)) AS open_rate,
            (COUNT(*) FILTER (WHERE e.delivery_status ILIKE 'replied%%')::float
             / NULLIF(COUNT(*),0)) AS reply_rate,
            MAX(e.sent_timestamp) AS last_sent_at
        FROM email_sends e
        {where_sql}
        {template_filter}
        GROUP BY e.sf_job_id, e.sf_job_name
    )
    SELECT *
    FROM per_job
    ORDER BY sent_count DESC NULLS LAST
    LIMIT %s
    """

    params = base_params + [start_date, end_date] + template_params + [limit]
    with get_db_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
    return pd.DataFrame(rows)


def build_salesforce_link(contact_id: Optional[str], account_id: Optional[str]) -> str:
    base = os.environ.get("SALESFORCE_BASE_URL", "https://momentum-site-8441.lightning.force.com/")
    if contact_id:
        return f"{base}/{contact_id}/view"
    if account_id:
        return f"{base}/{account_id}/view"
    return ""


def render_email_tracking():
    # `st.set_page_config` must be called once at the top-level (in main.py).
    # This function only renders the dashboard UI.
    st.title("Email Tracking")

    user_email = st.session_state.get("user_email")
    if not user_email:
        st.error("User not logged in (st.session_state['user_email'] missing)")
        return

    is_admin_user = user_email in ADMIN_EMAILS
    admin_view = False
    if is_admin_user:
        admin_view = st.checkbox("Admin view (company-wide metrics)", value=False)

    # Time window selector (quick choices) with default 14 days
    window_label = st.selectbox("Time window", ["1 day", "7 days", "2 weeks", "30 days", "90 days", "180 days", "1 year"], index=2)
    mapping = {"1 day":1, "7 days":7, "2 weeks":14, "30 days":30, "90 days":90, "180 days":180, "1 year":365}
    days = mapping[window_label]
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    # Templates filter
    templates_df = fetch_templates(user_email, admin_view)
    # templates_df returns columns 'name' and 'id' (or is empty)
    template_options = [("All Templates", None)]
    if not templates_df.empty:
        template_options += list(zip(templates_df.get("name", []), templates_df.get("id", [])))
    template_display = [t[0] for t in template_options]
    sel_idx = st.selectbox("Template", template_display)
    template_id = None
    # find selected id
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
    st.markdown("""
    Shows per-job performance: job name, template, last sent date, emails sent, open & reply rates,
    and the JD year with the highest open rate and reply rate.
    """)
    perf_df = fetch_performance_by_job(user_email, admin_view, start_date, end_date, template_id, limit=100)
    if perf_df.empty:
        st.info("No job-level data for the selected filters.")
    else:
        # format rates
        disp = perf_df.copy()
        disp["open_rate"] = (disp["open_rate"] * 100).round(1).astype(str) + "%"
        disp["reply_rate"] = (disp["reply_rate"] * 100).round(1).astype(str) + "%"
        
        st.dataframe(
            disp[["job_name", "last_sent_at", "sent_count", "open_rate", "reply_rate"]],
            width="stretch"
        )


    # Top templates
    st.subheader("Top Templates by Open Rate")
    top_templates = fetch_top_templates(user_email, admin_view, start_date, end_date, top_n=10)
    if top_templates.empty:
        st.info("No template data for selected range.")
    else:
        st.dataframe(top_templates.assign(open_rate=lambda d: (d.open_rate * 100).round(1).astype(str) + "%")[["template_name","sent_count","opens","open_rate"]].rename(columns={"template_name":"Template","sent_count":"Sent","opens":"Opens","open_rate":"Open Rate"}), width="stretch")

    st.markdown("---")

    # Paginated table
    st.subheader("Emails")
    page_size = 50
    if "email_page" not in st.session_state:
        st.session_state.email_page = 0

    offset = st.session_state.email_page * page_size
    df_page, total = fetch_emails_paginated(user_email, admin_view, start_date, end_date, template_id, limit=page_size, offset=offset)

    st.write(f"Showing {min(total, offset+1)}-{min(total, offset+page_size)} of {total:,} emails")
    if df_page.empty:
        st.info("No emails found for the selected filters.")
    else:
        def sf_link(row):
            return build_salesforce_link(row.get("contact_id"), row.get("account_id"))
    
        display = df_page.copy()
        display["sent_at"] = pd.to_datetime(display["sent_at"]) if not display["sent_at"].empty else display["sent_at"]
        display["Recipient"] = display.apply(
            lambda r: f"{r.get('contact_name','')} (JD {int(r['recipient_jd_year'])})"
            if pd.notna(r.get('recipient_jd_year'))
            else r.get('contact_name',''),
            axis=1
        )
        display["SF Link"] = display.apply(sf_link, axis=1)
        display = display.rename(columns={
            "sent_at": "Sent Date",
            "subject": "Subject",
            "template_name": "Template",
            "opened": "Opened",
            "replied": "Replied",
            "recipient_email": "Recipient Email",
            "SF Link": "Salesforce Link",
            "delivery_status": "Status"
        })
    
        # Summary table
        st.dataframe(
            display[["Sent Date", "Recipient", "Subject", "Template", "Opened", "Replied", "Recipient Email", "Salesforce Link"]],
            width="stretch"
        )
    
        # Expandable detailed emails
        st.markdown("### 📧 View Email Content")
        for _, row in display.iterrows():
            sent_display = pd.to_datetime(row["Sent Date"]).strftime("%Y-%m-%d %H:%M")
            status_label = (row["Status"] or "sent").lower()
            if row["Replied"]:
                status_label = "replied"
            elif row["Opened"]:
                status_label = "opened"
            
            header = f"**{row['Subject']}** — {row['Recipient Email']}  \n{sent_display} | **Email Status:** {status_label}"
            with st.expander(header):
                if row.get("body_html"):
                    st.markdown(row["body_html"], unsafe_allow_html=True)
                elif row.get("body_text"):
                    st.text(row["body_text"])
                else:
                    st.info("No email body stored for this message.")

    

    # Pagination controls
    colp1, colp2, colp3 = st.columns([1,6,1])
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
