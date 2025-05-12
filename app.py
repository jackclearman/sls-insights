# ──────────────────────────────────────────────────────────────────────────────
# SLS Insights Dashboard  – full Streamlit app
# (2025-05-11)  – includes requested fixes:
#   • plain-text fetch messages (no green success banners)
#   • restored “Experience” tab in Attorney Placements
#   • detailed tables for Top Firms and Top Cities in Placements
# ──────────────────────────────────────────────────────────────────────────────

import os
from datetime import datetime, timedelta

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

# ─── Streamlit page config ────────────────────────────────────────────────────
st.set_page_config(page_title="Legal Recruiting Dashboard", layout="wide")
st.title("SLS Insights Dashboard")

# ─── API configuration ────────────────────────────────────────────────────────
JOBS_API_ENDPOINT = "https://developer.firmprospects.com/v1/jobs"
ATTORNEYS_API_ENDPOINT = "https://developer.firmprospects.com/v1/attorneys"

# ─── Helpers ──────────────────────────────────────────────────────────────────
def get_api_key():
    """Return FirmProspects API token from Streamlit secrets or env var."""
    try:
        return st.secrets["API_CREDENTIALS"]["X_AUTH_TOKEN"]
    except Exception:
        token = os.environ.get("FIRMPROSPECTS_API_TOKEN")
        if token:
            return token
        st.error("API key not found – add it to Streamlit secrets or env vars.")
        return None


@st.cache_data
def load_amlaw_data():
    """Load Am Law 200 CSV (expects ‘FP ID - Firm’, ‘AmLaw Rank’)."""
    try:
        df = pd.read_csv("amlaw_200.csv")
        # normalise column names if needed
        if "FP ID - Firm" not in df.columns or "AmLaw Rank" not in df.columns:
            df.columns = ["AmLaw Rank", "FP ID - Firm"]
        df["FP ID - Firm"] = pd.to_numeric(df["FP ID - Firm"], errors="coerce")
        df["AmLaw Rank"]   = pd.to_numeric(df["AmLaw Rank"],   errors="coerce")
        return df
    except Exception as e:
        st.warning(f"Could not load AmLaw 200 data → {e}")
        return pd.DataFrame(columns=["AmLaw Rank", "FP ID - Firm"])


@st.cache_data(ttl=24 * 3600)
def fetch_jobs_from_api(days_range: int = 30):
    key = get_api_key()
    if not key:
        return []
    headers = {"X-AUTH-TOKEN": key, "Content-Type": "application/json"}

    today       = datetime.now().strftime("%Y-%m-%d")
    start_date  = (datetime.now() - timedelta(days=days_range)).strftime("%Y-%m-%d")
    base_params = {"t": "", "page[limit]": 5000, "page[offset]": 0, "condition": "AND"}

    def _payload(title):
        return {
            "regions": {
                "items": ["California", "Washington-Seattle"],
                "condition": "or",
                "use_second_location": True,
            },
            "posted_date": {"min": start_date, "max": today},
            "status": 1,
            "title": [title],
        }

    jobs = []
    for title in ("Associate", "Partner"):
        resp = requests.post(JOBS_API_ENDPOINT,
                             headers=headers,
                             json=_payload(title),
                             params=base_params)
        resp.raise_for_status()
        jobs.extend(resp.json().get("data", []))
    return jobs


@st.cache_data(ttl=24 * 3600)
def fetch_attorneys_from_api(attorney_type: str, days_range: int = 90):
    key = get_api_key()
    if not key:
        return []
    headers = {"X-AUTH-TOKEN": key, "Content-Type": "application/json"}

    today      = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days_range)).strftime("%Y-%m-%d")

    payload = {
        "regions": {"items": ["California"], "condition": "or", "use_second_location": True},
        "last_move_date": {"min": start_date, "max": today},
        "titles": ["Associate"] if attorney_type == "associates" else ["Partner"],
    }
    params = {"t": "", "page[limit]": 5000, "page[offset]": 0, "condition": "AND"}

    resp = requests.post(ATTORNEYS_API_ENDPOINT,
                         headers=headers,
                         json=payload,
                         params=params)
    resp.raise_for_status()
    return resp.json().get("data", [])


# ─── extraction helpers (→ dicts) ────────────────────────────────────────────
def extract_job(job):
    region = city = None
    if job.get("locations"):
        loc_parts = job["locations"][0].split(", ")
        if len(loc_parts) > 1:
            city, region = loc_parts[0], loc_parts[1]
        else:
            city = loc_parts[0]

    experience_range = ""
    if job.get("minYrs") is not None and job.get("maxYrs") is not None:
        experience_range = (
            f"{job['minYrs']} years"
            if job["minYrs"] == job["maxYrs"]
            else f"{job['minYrs']}-{job['maxYrs']} years"
        )

    firm_id = (
        job.get("firmId")
        or job.get("firm_id")
        or (job.get("firm", {}).get("id") if isinstance(job.get("firm"), dict) else None)
    )

    return {
        "Job Title": job.get("jobTitle", ""),
        "Firm": job.get("firmName", ""),
        "Practice Areas": ", ".join(job.get("practiceAreas", []) or []),
        "Specialties": ", ".join(job.get("specialty", []) or []),
        "City": city,
        "Experience Range": experience_range,
        "Posted Date": job.get("postedDate", ""),
        "Job Status": job.get("statusLabel", ""),
        "Job Type": job.get("title", [""])[0] if job.get("title") else "",
        "FirmProspects ID": job.get("id"),
        "Profile Link": f"[Link]({job.get('pageUrl', '')})",
        "Am Law Ranking": None,  # filled later
        "Region": region,
        "Firm ID": firm_id,
    }


def extract_attorney(atty):
    recent = atty.get("recent_move") or {}
    move   = recent.get("firm") or {}
    firm   = atty.get("firm", {})
    ranks  = firm.get("ranks", {})

    return {
        "Name": f"{atty.get('first_name', '')} {atty.get('last_name', '')}",
        "From Firm": move.get("old", {}).get("firm_name"),
        "To Firm": move.get("new", {}).get("firm_name"),
        "Practice Areas": ", ".join(atty.get("attorneys_practice_areas", []) or []),
        "Specialties": ", ".join(atty.get("attorneys_specialties", []) or []),
        "City": atty.get("location", {}).get("city"),
        "Graduation Year": atty.get("graduation_year"),
        "Law School": atty.get("law_school", {}).get("law_school_name"),
        "Current Firm": firm.get("firm_name"),
        "Title": ", ".join(atty.get("attorneys_titles", []) or []),
        "FirmProspects ID": atty.get("id"),
        "Profile Link": f"[Link](https://engage.firmprospects.com/attorneys/profile/{atty.get('id')})",
        "Am Law Ranking": ranks.get("top200"),
        "Region": atty.get("location", {}).get("state"),
        "Move Date": recent.get("date"),
        "Firm ID": firm.get("id"),
    }


# ─── Load reference data once ────────────────────────────────────────────────
amlaw_df = load_amlaw_data()

# ─── Tab layout ──────────────────────────────────────────────────────────────
job_tab, atty_tab = st.tabs(["Job Postings", "Attorney Placements"])

# keep shared colour palettes consistent
JOB_COLOR  = "#636EFA"  # plotly blue
ATTY_COLOR = "#EF553B"  # plotly red

# --------------------------------------------------------------------------- #
#  JOB POSTINGS TAB
# --------------------------------------------------------------------------- #
with job_tab:
    # ── controls ───────────────────────────────────────
    period_label = st.selectbox(
        "Select Time Period",
        ["Last 7 days", "Last 14 days", "Last 30 days", "Last 60 days"],
        index=2
    )
    period_days = {"Last 7 days": 7, "Last 14 days": 14,
                   "Last 30 days": 30, "Last 60 days": 60}[period_label]

    job_type = st.radio("Select Job Type", ["Associates", "Partners"], horizontal=True)

    # ── data ──────────────────────────────────────────
        # ── data (refresh when the date range changes) ─────────────────────────────
    if (
        "job_raw" not in st.session_state
        or st.session_state.get("jobs_fetch_days") != period_days
    ):
        st.session_state["job_raw"]        = fetch_jobs_from_api(period_days)
        st.session_state["jobs_fetch_days"] = period_days    # remember current range
        st.text(f"{len(st.session_state['job_raw']):,} jobs fetched from API.")


    job_df = pd.DataFrame([extract_job(j) for j in st.session_state["job_raw"]])

    # add Am Law ranking
    if not job_df.empty and not amlaw_df.empty:
        job_df["Firm ID"] = pd.to_numeric(job_df["Firm ID"], errors="coerce")
        mapping = dict(zip(amlaw_df["FP ID - Firm"], amlaw_df["AmLaw Rank"]))
        job_df["Am Law Ranking"] = (
            job_df["Firm ID"].map(mapping).astype("Int64")
        )

    # filter by job type
    if job_type == "Associates":
        job_df = job_df[job_df["Job Type"].str.contains("Associate", case=False, na=False)]
    else:
        job_df = job_df[job_df["Job Type"].str.contains("Partner", case=False, na=False)]

    if job_df.empty:
        st.warning("No jobs for the selected criteria.")
        st.stop()

    # ── filter widgets ─────────────────────────────────
    col1, col2, col3 = st.columns(3)
    with col1:
        amlaw_filter = st.selectbox("Filter by Am Law Ranking",
                                    ["All Firms", "Am Law 50", "Am Law 100"])
    with col2:
        region_filter = st.selectbox("Filter by Region",
                                     ["California Only", "Washington Only", "All Regions"])
    with col3:
        # dynamic practice areas list
        all_areas = sorted({area.strip()
                            for s in job_df["Practice Areas"].dropna()
                            for area in s.split(",")})
        practice_filter = st.selectbox("Filter by Practice Area",
                                       ["All Practice Areas"] + all_areas)

    # apply filters
    df = job_df.copy()
    if amlaw_filter == "Am Law 50":
        df = df[df["Am Law Ranking"].notna() & (df["Am Law Ranking"] <= 50)]
    elif amlaw_filter == "Am Law 100":
        df = df[df["Am Law Ranking"].notna() & (df["Am Law Ranking"] <= 100)]

    if region_filter.startswith("California"):
        df = df[df["Region"] == "California"]
    elif region_filter.startswith("Washington"):
        df = df[df["Region"] == "Washington"]

    if practice_filter != "All Practice Areas":
        df = df[df["Practice Areas"].str.contains(practice_filter, na=False)]

    if df.empty:
        st.warning("No jobs match your filters.")
        st.stop()

    # ── visual tabs ───────────────────────────────────
    top_firms_tab, top_cities_tab, practice_tab, exp_tab = st.tabs(
        ["Top Firms", "Top Cities", "Practice Areas", "Experience"]
    )

    # Top Firms
    with top_firms_tab:
        st.subheader(f"Top Hiring Firms ({job_type})")
        series = df["Firm"].value_counts().head(10)
        plot_df = pd.DataFrame({"Firm": series.index, "Count": series.values})
        fig = px.bar(plot_df, x="Firm", y="Count", color_discrete_sequence=[JOB_COLOR])
        fig.update_layout(xaxis=dict(categoryorder="total descending"),
                          xaxis_fixedrange=True, yaxis_fixedrange=True,
                          margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        st.dataframe(df[df["Firm"].isin(series.index)]
                     [["Job Title", "Firm", "Practice Areas", "City",
                       "Experience Range", "Posted Date"]],
                     hide_index=True)

    # Top Cities
    with top_cities_tab:
        st.subheader(f"Top Cities for {job_type} Jobs")
        series = df["City"].value_counts().head(10)
        plot_df = pd.DataFrame({"City": series.index, "Count": series.values})
        fig = px.bar(plot_df, x="City", y="Count", color_discrete_sequence=[JOB_COLOR])
        fig.update_layout(xaxis=dict(categoryorder="total descending"),
                          xaxis_fixedrange=True, yaxis_fixedrange=True,
                          margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        st.dataframe(df[df["City"].isin(series.index)]
                     [["Job Title", "Firm", "Practice Areas", "City",
                       "Experience Range", "Posted Date"]],
                     hide_index=True)

    # Practice Areas
    with practice_tab:
        st.subheader(f"Top Practice Areas ({job_type})")
        areas = [a.strip() for s in df["Practice Areas"].dropna() for a in s.split(",")]
        series = pd.Series(areas).value_counts().head(10)
        plot_df = pd.DataFrame({"Practice Area": series.index, "Count": series.values})
        fig = px.bar(plot_df, x="Practice Area", y="Count",
                     color_discrete_sequence=[JOB_COLOR])
        fig.update_layout(xaxis=dict(categoryorder="total descending"),
                          xaxis_fixedrange=True, yaxis_fixedrange=True,
                          margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        st.dataframe(plot_df, hide_index=True)

    # Experience
    with exp_tab:
        st.subheader(f"{job_type} Job Listings by Experience")
        exp_df = df.dropna(subset=["Experience Range"])
        exp_df = exp_df[exp_df["Experience Range"].str.contains(r"\d")]
        if exp_df.empty:
            st.info("Experience information missing.")
        else:
            exp_df["Min Years"] = exp_df["Experience Range"].str.extract(r"(\d+)").astype(float)
            counts = exp_df["Experience Range"].value_counts()
            plot_df = (pd.DataFrame({"Experience Required": counts.index,
                                     "Number of Jobs": counts.values})
                       .assign(_sort=lambda d: d["Experience Required"]
                               .str.extract(r"(\d+)").astype(float))
                       .sort_values("_sort")
                       [["Experience Required", "Number of Jobs"]])
            fig = px.bar(plot_df, x="Experience Required", y="Number of Jobs",
                         color_discrete_sequence=[JOB_COLOR])
            fig.update_layout(xaxis_fixedrange=True, yaxis_fixedrange=True,
                              margin=dict(t=10, b=10, l=10, r=10))
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
            st.dataframe(exp_df.sort_values("Min Years")
                         [["Job Title", "Firm", "Practice Areas", "City",
                           "Experience Range", "Posted Date"]],
                         hide_index=True)

# --------------------------------------------------------------------------- #
#  ATTORNEY PLACEMENTS TAB
# --------------------------------------------------------------------------- #
with atty_tab:
    # ── controls ───────────────────────────────────────
    atty_period_lbl = st.selectbox(
        "Select Time Period",
        ["Last 1 month", "Last 2 months", "Last 3 months", "Last 6 months"],
        index=2,
        key="atty_period")
    atty_days = {"Last 1 month": 30, "Last 2 months": 60,
                 "Last 3 months": 90, "Last 6 months": 180}[atty_period_lbl]

    role_type = st.radio("Select Attorney Type", ["Partners", "Associates"],
                         horizontal=True, key="atty_role")

    # ── data ──────────────────────────────────────────
    atty_key = "partners" if role_type == "Partners" else "associates"
    
    # ── data (refresh when date range OR role changes) ─────────────────────────
    if (
        "atty_raw" not in st.session_state
        or st.session_state.get("atty_fetch_days") != atty_days
        or st.session_state.get("atty_fetch_role") != atty_key
    ):
        st.session_state["atty_raw"]        = fetch_attorneys_from_api(atty_key, atty_days)
        st.session_state["atty_fetch_days"] = atty_days   # remember current range
        st.session_state["atty_fetch_role"] = atty_key    # remember Partner/Associate
        st.text(f"{len(st.session_state['atty_raw']):,} placement records fetched from API.")


    atty_df = pd.DataFrame([extract_attorney(a) for a in st.session_state["atty_raw"]])

    if not atty_df.empty and not amlaw_df.empty:
        atty_df["Firm ID"] = pd.to_numeric(atty_df["Firm ID"], errors="coerce")
        mapping = dict(zip(amlaw_df["FP ID - Firm"], amlaw_df["AmLaw Rank"]))
        atty_df.loc[atty_df["Am Law Ranking"].isna(), "Am Law Ranking"] = (
            atty_df.loc[atty_df["Am Law Ranking"].isna(), "Firm ID"]
            .map(mapping)
            .astype("Int64")
        )

    # ── filter widgets ─────────────────────────────────
    col1, col2, col3 = st.columns(3)
    with col1:
        amlaw_filter = st.selectbox("Filter by Am Law Ranking",
                                    ["All Firms", "Am Law 50", "Am Law 100"],
                                    key="atty_amlaw")
    with col2:
        region_filter = st.selectbox("Filter by Region",
                                     ["California Only", "Washington Only", "All Regions"],
                                     index=0, key="atty_region")
    with col3:
        all_areas = sorted({area.strip()
                            for s in atty_df["Practice Areas"].dropna()
                            for area in s.split(",")})
        practice_filter = st.selectbox("Filter by Practice Area",
                                       ["All Practice Areas"] + all_areas,
                                       key="atty_practice")

    # apply filters
    df = atty_df.copy()
    if amlaw_filter == "Am Law 50":
        df = df[df["Am Law Ranking"].notna() & (df["Am Law Ranking"] <= 50)]
    elif amlaw_filter == "Am Law 100":
        df = df[df["Am Law Ranking"].notna() & (df["Am Law Ranking"] <= 100)]

    if region_filter.startswith("California"):
        df = df[df["Region"] == "California"]
    elif region_filter.startswith("Washington"):
        df = df[df["Region"] == "Washington"]

    if practice_filter != "All Practice Areas":
        df = df[df["Practice Areas"].str.contains(practice_filter, na=False)]

    if df.empty:
        st.warning("No placements match your filters.")
        st.stop()

    # ── visual tabs ───────────────────────────────────
    top_firms_tab, top_cities_tab, practice_tab, exp_tab = st.tabs(
        ["Top Firms", "Top Cities", "Practice Areas", "Experience"]
    )

    # Top Firms
    with top_firms_tab:
        st.subheader(f"Top Destination Firms ({role_type})")
        series = df["To Firm"].value_counts().head(10)
        plot_df = pd.DataFrame({"Firm": series.index, "Count": series.values})
        fig = px.bar(plot_df, x="Firm", y="Count", color_discrete_sequence=[ATTY_COLOR])
        fig.update_layout(xaxis=dict(categoryorder="total descending"),
                          xaxis_fixedrange=True, yaxis_fixedrange=True,
                          margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        detail_cols = ["Name", "From Firm", "To Firm", "Practice Areas",
                       "City", "Title", "Move Date"]
        st.dataframe(df[df["To Firm"].isin(series.index)][detail_cols],
                     hide_index=True)

    # Top Cities
    with top_cities_tab:
        st.subheader(f"Top Cities for {role_type} Moves")
        series = df["City"].value_counts().head(10)
        plot_df = pd.DataFrame({"City": series.index, "Count": series.values})
        fig = px.bar(plot_df, x="City", y="Count", color_discrete_sequence=[ATTY_COLOR])
        fig.update_layout(xaxis=dict(categoryorder="total descending"),
                          xaxis_fixedrange=True, yaxis_fixedrange=True,
                          margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        detail_cols = ["Name", "From Firm", "To Firm", "Practice Areas",
                       "City", "Title", "Move Date"]
        st.dataframe(df[df["City"].isin(series.index)][detail_cols],
                     hide_index=True)

    # Practice Areas
    with practice_tab:
        st.subheader(f"Top Practice Areas ({role_type})")
        areas = [a.strip() for s in df["Practice Areas"].dropna() for a in s.split(",")]
        series = pd.Series(areas).value_counts().head(10)
        plot_df = pd.DataFrame({"Practice Area": series.index, "Count": series.values})
        fig = px.bar(plot_df, x="Practice Area", y="Count",
                     color_discrete_sequence=[ATTY_COLOR])
        fig.update_layout(xaxis=dict(categoryorder="total descending"),
                          xaxis_fixedrange=True, yaxis_fixedrange=True,
                          margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        st.dataframe(plot_df, hide_index=True)

    # Experience
    with exp_tab:
        st.subheader(f"{role_type} Experience Distribution")
        current_year = datetime.now().year
        df_exp = df.copy()
        df_exp["Graduation Year"] = pd.to_numeric(df_exp["Graduation Year"], errors="coerce")
        df_exp = df_exp.dropna(subset=["Graduation Year"])
        if df_exp.empty:
            st.info("No experience data available.")
        else:
            df_exp["Years Since JD"] = current_year - df_exp["Graduation Year"]
            bins   = [0, 3, 5, 8, 10, 15, 20, 50]
            labels = ["0-3", "3-5", "5-8", "8-10", "10-15", "15-20", "20+"]
            df_exp["Bracket"] = pd.cut(df_exp["Years Since JD"], bins=bins,
                                       labels=labels, right=False)

            counts = df_exp["Bracket"].value_counts().sort_index()
            plot_df = pd.DataFrame({"Experience": counts.index, "Count": counts.values})
            fig = px.bar(plot_df, x="Experience", y="Count",
                         color_discrete_sequence=[ATTY_COLOR])
            fig.update_layout(xaxis_fixedrange=True, yaxis_fixedrange=True,
                              margin=dict(t=10, b=10, l=10, r=10))
            st.plotly_chart(fig, use_container_width=True,
                            config={"displayModeBar": False})

            cols = ["Name", "From Firm", "To Firm", "Practice Areas",
                    "City", "Title", "Graduation Year", "Years Since JD",
                    "Bracket", "Move Date"]
            st.dataframe(df_exp[cols].sort_values("Years Since JD"),
                         hide_index=True)
