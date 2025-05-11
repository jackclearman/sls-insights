import os
from datetime import datetime, timedelta

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

# ──────────────────────────────────────────────────────────────────────────────
# SLS Insights Dashboard  – FULL Streamlit script (2025‑05‑11)
#   • Plain‑text dataset counts (no green success banners)
#   • Am Law filters work
#   • Robust None‑handling in `extract_attorney`
#   • Experience tabs & detailed tables for Jobs and Placements
# ──────────────────────────────────────────────────────────────────────────────

st.set_page_config(page_title="Legal Recruiting Dashboard", layout="wide")
st.title("SLS Insights Dashboard")

JOBS_API_ENDPOINT      = "https://developer.firmprospects.com/v1/jobs"
ATTORNEYS_API_ENDPOINT = "https://developer.firmprospects.com/v1/attorneys"
JOB_COLOR  = "#636EFA"  # plotly blue
ATTY_COLOR = "#EF553B"  # plotly red

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def get_api_key():
    """Return FirmProspects API token from Streamlit secrets or env var."""
    try:
        return st.secrets["API_CREDENTIALS"]["X_AUTH_TOKEN"]
    except Exception:
        token = os.environ.get("FIRMPROSPECTS_API_TOKEN")
        if token:
            return token
        st.error("API key not found → configure in Streamlit secrets or env.")
        return None

@st.cache_data
def load_amlaw_data():
    """Load Am Law 200 CSV shipped with the app."""
    try:
        df = pd.read_csv("amlaw_200.csv")
        if not {"FP ID - Firm", "AmLaw Rank"}.issubset(df.columns):
            df.columns = ["AmLaw Rank", "FP ID - Firm"]
        df["FP ID - Firm"] = pd.to_numeric(df["FP ID - Firm"], errors="coerce")
        df["AmLaw Rank"]   = pd.to_numeric(df["AmLaw Rank"],   errors="coerce")
        return df
    except Exception as e:
        st.warning(f"Couldn’t load Am Law CSV → {e}")
        return pd.DataFrame(columns=["AmLaw Rank", "FP ID - Firm"])

@st.cache_data(ttl=24*3600)
def fetch_jobs(days: int = 30):
    key = get_api_key()
    if not key:
        return []

    headers = {"X-AUTH-TOKEN": key, "Content-Type": "application/json"}
    today   = datetime.now().strftime("%Y-%m-%d")
    start   = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    base_payload = {
        "regions": {"items": ["California", "Washington-Seattle"], "condition": "or", "use_second_location": True},
        "posted_date": {"min": start, "max": today},
        "status": 1,
    }
    params = {"t": "", "page[limit]": 5000, "page[offset]": 0, "condition": "AND"}

    all_jobs = []
    for title in ("Associate", "Partner"):
        r = requests.post(JOBS_API_ENDPOINT, headers=headers, json={**base_payload, "title": [title]}, params=params)
        r.raise_for_status()
        all_jobs.extend(r.json().get("data", []))
    return all_jobs

@st.cache_data(ttl=24*3600)
def fetch_attorneys(kind: str, days: int = 90):
    key = get_api_key()
    if not key:
        return []

    headers = {"X-AUTH-TOKEN": key, "Content-Type": "application/json"}
    today   = datetime.now().strftime("%Y-%m-%d")
    start   = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    payload = {
        "regions": {"items": ["California"], "condition": "or", "use_second_location": True},
        "last_move_date": {"min": start, "max": today},
        "titles": ["Associate"] if kind == "associates" else ["Partner"],
    }
    params = {"t": "", "page[limit]": 5000, "page[offset]": 0, "condition": "AND"}

    r = requests.post(ATTORNEYS_API_ENDPOINT, headers=headers, json=payload, params=params)
    r.raise_for_status()
    return r.json().get("data", [])

# ──────────────────────────────────────────────────────────────────────────────
# Extractors
# ──────────────────────────────────────────────────────────────────────────────

def extract_job(j):
    region = city = None
    if j.get("locations"):
        parts = j["locations"][0].split(", ")
        if len(parts) > 1:
            city, region = parts[0], parts[1]
        else:
            city = parts[0]

    exp = ""
    if j.get("minYrs") is not None and j.get("maxYrs") is not None:
        exp = f"{j['minYrs']}-{j['maxYrs']} years" if j["minYrs"] != j["maxYrs"] else f"{j['minYrs']} years"

    firm_id = (
        j.get("firmId")
        or j.get("firm_id")
        or (j.get("firm", {}).get("id") if isinstance(j.get("firm"), dict) else None)
    )

    return {
        "Job Title": j.get("jobTitle", ""),
        "Firm": j.get("firmName", ""),
        "Practice Areas": ", ".join(j.get("practiceAreas", []) or []),
        "Specialties": ", ".join(j.get("specialty", []) or []),
        "City": city,
        "Experience Range": exp,
        "Posted Date": j.get("postedDate", ""),
        "Job Status": j.get("statusLabel", ""),
        "Job Type": (j.get("title") or [""])[0],
        "FirmProspects ID": j.get("id"),
        "Profile Link": f"[Link]({j.get('pageUrl', '')})",
        "Am Law Ranking": None,  # mapped later
        "Region": region,
        "Firm ID": firm_id,
    }

def extract_attorney(a):
    """Safely flatten an attorney JSON object."""
    if not isinstance(a, dict):
        return {}

    recent = a.get("recent_move") or {}
    move   = recent.get("firm") or {}
    firm   = a.get("firm") or {}
    ranks  = firm.get("ranks") or {}

    return {
        "Name": f"{a.get('first_name', '')} {a.get('last_name', '')}",
        "From Firm": move.get("old", {}).get("firm_name"),
        "To Firm": move.get("new", {}).get("firm_name"),
        "Practice Areas": ", ".join(a.get("attorneys_practice_areas", []) or []),
        "Specialties": ", ".join(a.get("attorneys_specialties", []) or []),
        "City": (a.get("location") or {}).get("city"),
        "Graduation Year": a.get("graduation_year"),
        "Law School": (a.get("law_school") or {}).get("law_school_name"),
        "Current Firm": firm.get("firm_name"),
        "Title": ", ".join(a.get("attorneys_titles", []) or []),
        "FirmProspects ID": a.get("id"),
        "Profile Link": f"[Link](https://engage.firmprospects.com/attorneys/profile/{a.get('id')})",
        "Am Law Ranking": ranks.get("top200"),
        "Region": (a.get("location") or {}).get("state"),
        "Move Date": recent.get("date"),
        "Firm ID": firm.get("id"),
    }

# ──────────────────────────────────────────────────────────────────────────────
# UI – Tabs
# ──────────────────────────────────────────────────────────────────────────────

amlaw_df = load_amlaw_data()
job_tab, atty_tab = st.tabs(["Job Postings", "Attorney Placements"])

# ---------------------------------------------------------------------------
# JOB POSTINGS TAB
# ---------------------------------------------------------------------------
with job_tab:
    period_label = st.selectbox(
        "Select Time Period",
        ["Last 7 days", "Last 14 days", "Last 30 days", "Last 60 days"],
        index=2,
    )
    period_days = {"Last 7 days": 7, "Last 14 days": 14, "Last 30 days": 30, "Last 60 days": 60}[period_label]
    job_type = st.radio("Select Job Type", ["Associates", "Partners"], horizontal=True)

    if "jobs_raw" not in st.session_state:
        st.session_state.jobs_raw = fetch_jobs(period_days)
    st.text(f"{len(st.session_state.jobs_raw)} Job Postings")

    job_df = pd.DataFrame([extract_job(j) for j in st.session_state.jobs_raw])

    # map AmLaw rank
    if not job_df.empty and not amlaw_df.empty:
        job_df["Firm ID"] = pd.to_numeric(job_df["Firm ID"], errors="coerce")
        mapping = dict(zip(amlaw_df["FP ID - Firm"], amlaw_df["AmLaw Rank"]))
        job_df["Am Law Ranking"] = job_df["Firm ID"].map(mapping).astype("Int64")

    job_df = job_df[job_df["Job Type"].str.contains("Associate" if job_type == "Associates" else "Partner", case=False, na=False)]
    if job_df.empty:
        st.warning("No jobs for selected criteria.")
        st.stop()

    # ------------------------------------------------------------ Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        amlaw_filter = st.selectbox("Filter by Am Law Ranking", ["All Firms", "Am Law 50", "Am Law 100"])
    with col2:
        region_filter = st.selectbox("Filter by Region", ["California Only", "Washington Only", "All Regions"], index=2)
    with col3:
        areas = sorted({a.strip() for s in job_df["Practice Areas"].dropna() for a in s.split(",")})
        pa_filter = st.selectbox("Filter by Practice Area", ["All Practice Areas"] + areas)

    df = job_df.copy()
    if amlaw_filter == "Am Law 50":
        df = df[df["Am Law Ranking"].notna() & (df["Am Law Ranking"] <= 50)]
    elif amlaw_filter == "Am Law 100":
        df = df[df["Am Law Ranking"].notna() & (df["Am Law Ranking"] <= 100)]

    if region_filter.startswith("California"):
        df = df[df["Region"] == "California"]
    elif region_filter.startswith("Washington"):
        df = df[df["Region"] == "Washington"]

    if pa_filter != "All Practice Areas":
        df = df[df["Practice Areas"].str.contains(pa_filter, na=False)]

    if df.empty:
        st.warning("No jobs match your filters.")
        st.stop()

    tf, tc, pa, exp = st.tabs(["Top Firms", "Top Cities", "Practice Areas", "Experience"])

    # Top Firms
    with tf:
        series = df["Firm"].value_counts().head(10)
        plot_df = pd.DataFrame({"Firm": series.index, "Count": series.values})
        fig = px.bar(plot_df, x="Firm", y="Count", color_discrete_sequence=[JOB_COLOR])
        fig.update_layout(xaxis=dict(categoryorder="total descending"), xaxis_fixedrange=True, yaxis_fixedrange=True, margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        st.dataframe(df[df["Firm"].isin(series.index)][["Job Title", "Firm", "Practice Areas", "City", "Experience Range", "Posted Date"]], hide_index=True)

    # Top Cities
    with tc:
        series = df["City"].value_counts().head(10)
        plot_df = pd.DataFrame({"City": series.index, "Count": series.values})
        fig = px.bar(plot_df, x="City", y="Count", color_discrete_sequence=[JOB_COLOR])
        fig.update_layout(xaxis=dict(categoryorder="total descending"), xaxis_fixedrange=True, yaxis_fixedrange=True, margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig, use_container_width=True, config={
