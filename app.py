import streamlit as st
import pandas as pd
import json
import plotly.express as px
from datetime import datetime, timedelta
import requests
import os

# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG & TITLE
# ─────────────────────────────────────────────────────────────────────────────

st.set_page_config(page_title="Legal Recruiting Dashboard", layout="wide")
st.title("SLS Insights Dashboard")

# Success‑message placeholders to ensure one‑time toasts
job_success_ph  = st.empty()
atty_success_ph = st.empty()

# ─────────────────────────────────────────────────────────────────────────────
# API ENDPOINTS & SECRETS HANDLING
# ─────────────────────────────────────────────────────────────────────────────

JOBS_API_ENDPOINT      = "https://developer.firmprospects.com/v1/jobs"
ATTORNEYS_API_ENDPOINT = "https://developer.firmprospects.com/v1/attorneys"


def get_api_key():
    """Return API key from Streamlit secrets or env var."""
    try:
        return st.secrets["API_CREDENTIALS"]["X_AUTH_TOKEN"]
    except Exception:
        token = os.environ.get("FIRMPROSPECTS_API_TOKEN")
        if token:
            return token
        st.error("API key not found. Please configure it in Streamlit secrets or env vars.")
        return None

# ─────────────────────────────────────────────────────────────────────────────
# DATA LOADERS (cached)
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data
def load_amlaw_data():
    """Load AmLaw‑200 CSV shipped with the app."""
    try:
        df = pd.read_csv("amlaw_200.csv")
        # Normalise headers if necessary
        if {"AmLaw Rank", "FP ID - Firm"}.issubset(df.columns) is False:
            df.columns = ["AmLaw Rank", "FP ID - Firm"]
        df["FP ID - Firm"] = pd.to_numeric(df["FP ID - Firm"], errors="coerce")
        df["AmLaw Rank"]   = pd.to_numeric(df["AmLaw Rank"],   errors="coerce")
        return df
    except Exception as e:
        st.warning(f"Could not load AmLaw 200 data: {e}")
        return pd.DataFrame(columns=["AmLaw Rank", "FP ID - Firm"])


@st.cache_data(ttl=24*3600)
def fetch_jobs_from_api(days_range: int = 30):
    api_key = get_api_key()
    if not api_key:
        return []

    headers = {
        "X-AUTH-TOKEN": api_key,
        "Content-Type": "application/json",
    }

    today       = datetime.now().strftime("%Y-%m-%d")
    start_date  = (datetime.now() - timedelta(days=days_range)).strftime("%Y-%m-%d")

    base_payload = {
        "regions": {
            "items": ["California", "Washington-Seattle"],
            "condition": "or",
            "use_second_location": True,
        },
        "posted_date": {"min": start_date, "max": today},
        "status": 1,
    }

    payloads = {
        "Associates": {**base_payload, "title": ["Associate"]},
        "Partners":   {**base_payload, "title": ["Partners"]},
    }

    all_jobs = []
    params   = {"t": "", "page[limit]": 5000, "page[offset]": 0, "condition": "AND"}

    try:
        for p in payloads.values():
            r = requests.post(JOBS_API_ENDPOINT, headers=headers, json=p, params=params)
            r.raise_for_status()
            all_jobs.extend(r.json().get("data", []))
        return all_jobs
    except Exception as e:
        st.error(f"❌ Error fetching jobs from API: {e}")
        return []


@st.cache_data(ttl=24*3600)
def fetch_attorneys_from_api(attorney_type: str, days_range: int = 90):
    api_key = get_api_key()
    if not api_key:
        return []

    headers = {
        "X-AUTH-TOKEN": api_key,
        "Content-Type": "application/json",
    }

    today      = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days_range)).strftime("%Y-%m-%d")
    titles     = ["Associate"] if attorney_type == "associates" else ["Partner"]

    payload = {
        "regions": {
            "items": ["California"],
            "condition": "or",
            "use_second_location": True,
        },
        "last_move_date": {"min": start_date, "max": today},
        "titles": titles,
    }

    params = {"t": "", "page[limit]": 5000, "page[offset]": 0, "condition": "AND"}

    try:
        r = requests.post(ATTORNEYS_API_ENDPOINT, headers=headers, json=payload, params=params)
        r.raise_for_status()
        return r.json().get("data", [])
    except Exception as e:
        st.error(f"❌ Error fetching {attorney_type} from API: {e}")
        return []

# ─────────────────────────────────────────────────────────────────────────────
# DATA EXTRACTORS
# ─────────────────────────────────────────────────────────────────────────────

def extract_attorney(a: dict) -> dict:
    recent = a.get("recent_move") or {}
    move   = recent.get("firm")  or {}
    firm   = a.get("firm", {})
    ranks  = firm.get("ranks", {})

    return {
        "Name": f"{a.get('first_name', '')} {a.get('last_name', '')}",
        "From Firm": move.get("old", {}).get("firm_name"),
        "To Firm": move.get("new", {}).get("firm_name"),
        "Practice Areas": ", ".join(a.get("attorneys_practice_areas", []) or []),
        "Specialties": ", ".join(a.get("attorneys_specialties", []) or []),
        "City": a.get("location", {}).get("city"),
        "Graduation Year": a.get("graduation_year"),
        "Law School": a.get("law_school", {}).get("law_school_name"),
        "Current Firm": firm.get("firm_name"),
        "Title": ", ".join(a.get("attorneys_titles", []) or []),
        "FirmProspects ID": a.get("id"),
        "Profile Link": f"[Link](https://engage.firmprospects.com/attorneys/profile/{a.get('id')})",
        "Am Law Ranking": ranks.get("top200"),
        "Region": a.get("location", {}).get("state"),
        "Move Date": recent.get("date"),
        "Firm ID": firm.get("id"),
    }


def extract_job(j: dict) -> dict:
    # Location parsing
    region, city = None, None
    if j.get("locations"):
        parts = j["locations"][0].split(", ")
        if len(parts) > 1:
            city, region = parts[0], parts[1]
        elif parts:
            city = parts[0]

    practice_areas = ", ".join(j.get("practiceAreas", []) or [])
    specialties    = ", ".join(j.get("specialty",      []) or [])

    experience = ""
    if j.get("minYrs") is not None and j.get("maxYrs") is not None:
        experience = f"{j['minYrs']}-{j['maxYrs']} years" if j["minYrs"] != j["maxYrs"] else f"{j['minYrs']} years"

    # Firm ID detection across possible keys
    firm_id = j.get("firmId") or j.get("firm_id")
    if firm_id is None and isinstance(j.get("firm"), dict):
        firm_id = j["firm"].get("id")

    return {
        "Job Title": j.get("jobTitle", ""),
        "Firm": j.get("firmName", ""),
        "Practice Areas": practice_areas,
        "Specialties": specialties,
        "City": city,
        "Experience Range": experience,
        "Posted Date": j.get("postedDate", ""),
        "Job Status": j.get("statusLabel", ""),
        "Job Type": (j.get("title") or [""])[0],
        "FirmProspects ID": j.get("id"),
        "Profile Link": f"[Link]({j.get('pageUrl', '')})",
        "Am Law Ranking": None,  # to be mapped
        "Region": region,
        "Firm ID": firm_id,
    }

# ─────────────────────────────────────────────────────────────────────────────
# MAIN UI
# ─────────────────────────────────────────────────────────────────────────────

tabs = st.tabs(["Job Listings", "Attorney Placements"])

amlaw_df = load_amlaw_data()

# Shared state
if "job_msg_shown" not in st.session_state:
    st.session_state.job_msg_shown = False
if "atty_msg_shown" not in st.session_state:
    st.session_state.atty_msg_shown = False

# ─────────────────────────────────────────────────────────────────────────────
# JOB LISTINGS TAB
# ─────────────────────────────────────────────────────────────────────────────

with tabs[0]:
    time_opts  = ["Last 7 days", "Last 14 days", "Last 30 days", "Last 60 days"]
    time_vals  = [7, 14, 30, 60]
    sel_period = st.selectbox("Select Time Period", time_opts, index=2)
    days_back  = time_vals[time_opts.index(sel_period)]

    job_type = st.radio("Select Job Type", ["Associates", "Partners"], horizontal=True)

    if "job_data" not in st.session_state:
        st.session_state.job_data = fetch_jobs_from_api(days_back)
        if st.session_state.job_data and not st.session_state.job_msg_shown:
            job_success_ph.success(f"✅ Successfully fetched {len(st.session_state.job_data)} jobs from API!")
            st.session_state.job_msg_shown = True

    job_df = pd.DataFrame([extract_job(j) for j in st.session_state.job_data])

    # Map AmLaw ranking (robust casting to nullable Int64)
    if not job_df.empty and not amlaw_df.empty:
        job_df["Firm ID"] = pd.to_numeric(job_df["Firm ID"], errors="coerce")
        amlaw_mapping = dict(zip(amlaw_df["FP ID - Firm"], amlaw_df["AmLaw Rank"]))
        job_df["Am Law Ranking"] = job_df["Firm ID"].map(amlaw_mapping).astype("Int64")

    # Filter by job type early
    if job_type == "Associates":
        filtered_job_df = job_df[job_df["Job Type"].str.contains("Associate", case=False, na=False)].copy()
    else:
        filtered_job_df = job_df[job_df["Job Type"].str.contains("Partner", case=False, na=False)].copy()

    if filtered_job_df.empty:
        st.warning("No data for the selected options.")
    else:
        # ---------------------------------------------------------------------
        # FILTER CONTROLS
        # ---------------------------------------------------------------------
        areas = set()
        for s in filtered_job_df["Practice Areas"].dropna():
            areas.update(a.strip() for a in s.split(", "))
        area_opts = ["All Practice Areas"] + sorted(areas)

        c1, c2, c3 = st.columns(3)
        with c1:
            amlaw_filter = st.selectbox("Filter by Am Law Ranking", ["All Firms", "Am Law 50", "Am Law 100"], key="job_amlaw")
        with c2:
            region_filter = st.selectbox("Filter by Region", ["California Only", "Washington Only", "All Regions"], key="job_region")
        with c3:
            pa_filter = st.selectbox("Filter by Practice Area", area_opts, key="job_pa")

        data = filtered_job_df.copy()
        # AmLaw
        if amlaw_filter == "Am Law 50":
            data = data[data["Am Law Ranking"].notna() & (data["Am Law Ranking"] <= 50)]
        elif amlaw_filter == "Am Law 100":
            data = data[data["Am Law Ranking"].notna() & (data["Am Law Ranking"] <= 100)]
        # Region
        if region_filter == "California Only":
            data = data[data["Region"] == "California"]
        elif region_filter == "Washington Only":
            data = data[data["Region"] == "Washington"]
        # Practice area
        if pa_filter != "All Practice Areas":
            data = data[data["Practice Areas"].str.contains(pa_filter, na=False)]

        if data.empty:
            st.warning("No job data with current filters.")
        else:
            jt = st.tabs(["Top Firms", "Top Cities", "Practice Areas", "Experience"])
            JOB_COLOR = ["#636EFA"]

            # Top Firms
            with jt[0]:
                top_firms = data["Firm"].value_counts().head(10)
                plot_df = pd.DataFrame({"Firm": top_firms.index, "Count": top_firms.values})
                fig = px.bar(plot_df, x="Firm", y="Count", color_discrete_sequence=JOB_COLOR, labels={"Count": f"Number of {job_type} Jobs", "Firm": ""})
                fig.update_layout(xaxis=dict(categoryorder="total descending"), margin=dict(t=10, b=10, l=10, r=10), xaxis_fixedrange=True, yaxis_fixedrange=True)
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
                st.dataframe(data[data["Firm"].isin(top_firms.index)][["Job Title", "Firm", "Practice Areas", "City", "Experience Range", "Posted Date"]], hide_index=True)

            # Top Cities
            with jt[1]:
                top_cities = data["City"].value_counts().head(10)
                city_df = pd.DataFrame({"City": top_cities.index, "Count": top_cities.values})
                fig = px.bar(city_df, x="City", y="Count", color_discrete_sequence=JOB_COLOR, labels={"Count": f"Number of {job_type} Jobs", "City": ""})
                fig.update_layout(xaxis=dict(categoryorder="total descending"), margin=dict(t=10, b=10, l=10, r=10), xaxis_fixedrange=True, yaxis_fixedrange=True)
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
                st.dataframe(data[data["City"].isin(top_cities.index)][["Job Title", "Firm", "Practice Areas", "City", "Experience Range", "Posted Date"]], hide_index=True)

            # Practice Areas
            with jt[2]:
                pa_list = []
                for s in data["Practice Areas"].dropna():
                    pa_list.extend(a.strip() for a in s.split(","))
                pa_counts = pd.Series(pa_list).value_counts().head(10)
                pa_df = pd.DataFrame({"Practice Area": pa_counts.index, "Count": pa_counts.values})
                fig = px.bar(pa_df, x="Practice Area", y="Count", color_discrete_sequence=JOB_COLOR, labels={"Count": f"Number of {job_type} Jobs", "Practice Area": ""})
                fig.update_layout(xaxis=dict(categoryorder="total descending"), margin=dict(t=10, b=10, l=10, r=10), xaxis_fixedrange=True, yaxis_fixedrange=True)
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
                st.dataframe(pa_df, hide_index=True)

            # Experience
            with jt[3]:
                exp_df = data.dropna(subset=["Experience Range"])
                exp_df = exp_df[exp_df["Experience Range"].str.contains(r"\d+", regex=True)].copy()
                if exp_df.empty:
                    st.info("No experience data available.")
                else:
                    exp_df["Min Years"] = exp_df["Experience Range"].str.extract(r"(\d+)").astype(float)
                    counts = exp_df["Experience Range"].value_counts()
                    plot_df = pd.DataFrame({"Experience Required": counts.index, "Number of Jobs": counts.values})
                    plot_df["Min Years"] = plot_df["Experience Required"].str.extract(r"(\d+)").astype(float)
                    plot_df = plot_df.sort_values("Min Years")[["Experience Required", "Number of Jobs"]]  # drop helper columns

                    fig = px.bar(plot_df, x="Experience Required", y="Number of Jobs", color_discrete_sequence=JOB_COLOR, labels={"Number of Jobs": "Count", "Experience Required": "Years of Experience Required"})
                    fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), xaxis_fixedrange=True, yaxis_fixedrange=True)
                    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
                    st.dataframe(exp_df.sort_values("Min Years")[["Job Title", "Firm", "Practice Areas", "City", "Experience Range", "Posted Date"]], hide_index=True)

# ─────────────────────────────────────────────────────────────────────────────
# ATTORNEY PLACEMENTS TAB
# ─────────────────────────────────────────────────────────────────────────────

with tabs[1]:
    atty_time_opts  = ["Last 1 month", "Last 2 months", "Last 3 months", "Last 6 months"]
    atty_time_vals  = [30, 60, 90, 180]
    atty_period     = st.selectbox("Select Time Period", atty_time_opts, index=2, key="atty_tp")
    atty_days_back  = atty_time_vals[atty_time_opts.index(atty_period)]

    role_type = st.radio("Select Attorney Type", ["Partners", "Associates"], horizontal=True, key="atty_role")

    if "atty_data" not in st.session_state:
        api_label = "partners" if role_type == "Partners" else "associates"
        st.session_state.atty_data = fetch_attorneys_from_api(api_label, atty_days_back)
        if st.session_state.atty_data and not st.session_state.atty_msg_shown:
            atty_success_ph.success(f"✅ Successfully fetched {len(st.session_state.atty_data)} placement records from API!")
            st.session_state.atty_msg_shown = True

    atty_df = pd.DataFrame([extract_attorney(a) for a in st.session_state.atty_data])

    if not atty_df.empty and not amlaw_df.empty:
        atty_df["Firm ID"] = pd.to_numeric(atty_df["Firm ID"], errors="coerce")
        amlaw_mapping = dict(zip(amlaw_df["FP ID - Firm"], amlaw_df["AmLaw Rank"]))
        mask = atty_df["Am Law Ranking"].isna()
        atty_df.loc[mask, "Am Law Ranking"] = atty_df.loc[mask, "Firm ID"].map(amlaw_mapping)

    if atty_df.empty:
        st.warning("No attorney data for the selected options.")
    else:
        # Filters
        pa_set = set()
        for s in atty_df["Practice Areas"].dropna():
            pa_set.update(a.strip() for a in s.split(", "))
        pa_opts = ["All Practice Areas"] + sorted(pa_set)

        c1, c2, c3 = st.columns(3)
        with c1:
            amlaw_filter = st.selectbox("Filter by Am Law Ranking", ["All Firms", "Am Law 50", "Am Law 100"], key="atty_amlaw")
        with c2:
            region_filter = st.selectbox("Filter by Region", ["California Only", "Washington Only", "All Regions"], key="atty_reg")
        with c3:
            pa_filter = st.selectbox("Filter by Practice Area", pa_opts, key="atty_pa")

        data = atty_df.copy()
        if amlaw_filter == "Am Law 50":
            data = data[data["Am Law Ranking"].notna() & (data["Am Law Ranking"] <= 50)]
        elif amlaw_filter == "Am Law 100":
            data = data[data["Am Law Ranking"].notna() & (data["Am Law Ranking"] <= 100)]
        if region_filter == "California Only":
            data = data[data["Region"] == "California"]
        elif region_filter == "Washington Only":
            data = data[data["Region"] == "Washington"]
        if pa_filter != "All Practice Areas":
            data = data[data["Practice Areas"].str.contains(pa_filter, na=False)]

        if data.empty:
            st.warning("No placement data with current filters.")
        else:
            st.subheader(f"Recent {role_type} Moves")
            display_cols = ["Name", "Title", "From Firm", "To Firm", "Practice Areas", "City", "Move Date", "Am Law Ranking"]
            st.dataframe(data[display_cols], hide_index=True)
