# ──────────────────────────────────────────────────────────────────────────────
# SLS Insights Dashboard  – full Streamlit app
#   • duplicates removed on FirmProspects ID
#   • live row-counts in headers + chart titles
#   • new Job-Status dropdown (Open ▸ default, Closed, All)
# ──────────────────────────────────────────────────────────────────────────────
import os
from datetime import datetime, timedelta

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

# ─── API endpoints ────────────────────────────────────────────────────────────
JOBS_API_ENDPOINT      = "https://developer.firmprospects.com/v1/jobs"
ATTORNEYS_API_ENDPOINT = "https://developer.firmprospects.com/v1/attorneys"
# ─── Streamlit page config ────────────────────────────────────────────────────
st.set_page_config(page_title="Legal Recruiting Dashboard", layout="wide")
st.title("SLS Insights Dashboard")
# ─── helpers ──────────────────────────────────────────────────────────────────
def get_api_key():
    try:
        return st.secrets["API_CREDENTIALS"]["X_AUTH_TOKEN"]
    except Exception:
        return os.environ.get("FIRMPROSPECTS_API_TOKEN")

@st.cache_data
def load_amlaw_data():
    try:
        df = pd.read_csv("amlaw_200.csv")
        if "FP ID - Firm" not in df.columns or "AmLaw Rank" not in df.columns:
            df.columns = ["AmLaw Rank", "FP ID - Firm"]
        df = df.astype({"FP ID - Firm": "Int64", "AmLaw Rank": "Int64"})
        return df
    except Exception:
        return pd.DataFrame(columns=["AmLaw Rank", "FP ID - Firm"])

@st.cache_data(ttl=24*3600)
def fetch_jobs_from_api(days_range=30, start_date=None, end_date=None):
    key = get_api_key()
    if not key:
        return []
    headers = {"X-AUTH-TOKEN": key, "Content-Type": "application/json"}
    if start_date is not None and end_date is not None:
        start = start_date.strftime("%Y-%m-%d")
        today = end_date.strftime("%Y-%m-%d")
    else:
        today  = datetime.now().strftime("%Y-%m-%d")
        start  = (datetime.now() - timedelta(days=days_range)).strftime("%Y-%m-%d")
    params = {"t": "", "page[limit]": 5000, "page[offset]": 0, "condition": "AND"}

    def payload(role):
        return {
            "regions": {"items": ["California", "Washington-Seattle"],
                        "condition": "or", "use_second_location": True},
            "posted_date": {"min": start, "max": today},
            "titles": [role]                      # no status filter → returns open + closed
        }

    jobs_by_id = {}
    for role in ("Associate", "Partner"):
        r = requests.post(JOBS_API_ENDPOINT, headers=headers,
                          json=payload(role), params=params)
        r.raise_for_status()
        for rec in r.json().get("data", []):
            jobs_by_id[rec["id"]] = rec
    return list(jobs_by_id.values())

@st.cache_data(ttl=24*3600)
def fetch_attorneys_from_api(attorney_type="associates", days_range=90, start_date=None, end_date=None):
    key = get_api_key()
    if not key:
        return []
    headers = {"X-AUTH-TOKEN": key, "Content-Type": "application/json"}
    if start_date is not None and end_date is not None:
        today = end_date.strftime("%Y-%m-%d")
        start = start_date.strftime("%Y-%m-%d")
    else:
        today  = datetime.now().strftime("%Y-%m-%d")
        start  = (datetime.now() - timedelta(days=days_range)).strftime("%Y-%m-%d")
    params = {"t": "", "page[limit]": 5000, "page[offset]": 0, "condition": "AND"}

    payload = {
        "regions": {"items": ["California"], "condition": "or",
                    "use_second_location": True},
        "last_move_date": {"min": start, "max": today},
        "titles": ["Associate"] if attorney_type == "associates" else ["Partner"],
    }
    r = requests.post(ATTORNEYS_API_ENDPOINT, headers=headers,
                      json=payload, params=params)
    r.raise_for_status()
    return r.json().get("data", [])

# ─── extract helpers ─────────────────────────────────────────────────────────
def extract_job(j):
    region = city = None
    if j.get("locations"):
        parts = j["locations"][0].split(", ")
        city, region = parts[0], parts[1] if len(parts) > 1 else None
    exp_range = ""
    if j.get("minYrs") is not None and j.get("maxYrs") is not None:
        exp_range = (f"{j['minYrs']} years" if j["minYrs"] == j["maxYrs"]
                     else f"{j['minYrs']}-{j['maxYrs']} years")
    firm_id = (j.get("firmId") or j.get("firm_id") or
               (j.get("firm", {}).get("id") if isinstance(j.get("firm"), dict) else None))
    return {
        "Job Title": j.get("jobTitle", ""),
        "Firm": j.get("firmName", ""),
        "Practice Areas": ", ".join(j.get("practiceAreas", []) or []),
        "Specialties": ", ".join(j.get("specialty", []) or []),
        "City": city,
        "Experience Range": exp_range,
        "Posted Date": j.get("postedDate", ""),
        "Status Code": j.get("status"),                      # 1 = open, 0 = closed
        "Job Status": j.get("statusLabel", ""),
        "Job Type": j.get("title", [""])[0] if j.get("title") else "",
        "FirmProspects ID": j.get("id"),
        "Firm Prospects Link": j.get("pageUrl", ""),
        "Am Law Ranking": None,
        "Region": region,
        "Firm ID": firm_id,
    }

def extract_attorney(a):
    recent = a.get("recent_move") or {}
    move   = recent.get("firm") or {}
    firm   = a.get("firm", {})
    ranks  = firm.get("ranks", {})
    move_date = recent.get("date") or (a.get("experience", {}) or {}).get("last_move_date")
    return {
        "id": a.get("id"),  # for table display
        "last_move_date": move_date,  # for table display
        "Name": f"{a.get('first_name','')} {a.get('last_name','')}",
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
        "Move Date": move_date,
        "Firm ID": firm.get("id"),
    }

# ─── colour palette ──────────────────────────────────────────────────────────
JOB_COLOR  = "#636EFA"
ATTY_COLOR = "#EF553B"


# ─── layout ──────────────────────────────────────────────────────────────────
job_tab, atty_tab, report_tab = st.tabs(["Job Postings", "Attorney Placements", "Monthly Report"])

## --------------------------------------------------------------------------- #
##  JOB POSTINGS TAB
## --------------------------------------------------------------------------- #
with job_tab:
    period_label = st.selectbox("Select Time Period",
        ["Last 7 days", "Last 14 days", "Last 30 days", "Last 60 days"], index=2)
    period_days  = {"Last 7 days":7,"Last 14 days":14,"Last 30 days":30,"Last 60 days":60}[period_label]

    job_type = st.radio("Select Job Type", ["Associates", "Partners"], horizontal=True)

    if ("job_raw" not in st.session_state or
        st.session_state.get("jobs_fetch_days") != period_days):
        st.session_state["job_raw"]        = fetch_jobs_from_api(period_days)
        st.session_state["jobs_fetch_days"] = period_days
        st.text(f"{len(st.session_state['job_raw']):,} jobs fetched from API.")

    job_df = (pd.DataFrame([extract_job(j) for j in st.session_state["job_raw"]])
              .drop_duplicates(subset="FirmProspects ID")
              .reset_index(drop=True))

    # add Am Law
    amlaw_df = load_amlaw_data()
    if not job_df.empty and not amlaw_df.empty:
        job_df["Firm ID"] = pd.to_numeric(job_df["Firm ID"], errors="coerce")
        mapping = dict(zip(amlaw_df["FP ID - Firm"], amlaw_df["AmLaw Rank"]))
        job_df["Am Law Ranking"] = job_df["Firm ID"].map(mapping).astype("Int64")

    # associate/partner filter
    if job_type == "Associates":
        job_df = job_df[job_df["Job Type"].str.contains("Associate", na=False, case=False)]
    else:
        job_df = job_df[job_df["Job Type"].str.contains("Partner",   na=False, case=False)]

    # top-level filters
    col1,col2,col3,col4 = st.columns(4)
    with col1:
        amlaw_filter = st.selectbox("Filter by Am Law Ranking",
                                    ["All Firms","Am Law 50","Am Law 100"])
    with col2:
        region_filter = st.selectbox("Filter by Region",
                                     ["California Only","Washington Only","All Regions"])
    with col3:
        all_areas = sorted({
            a.strip()
            for s in job_df["Practice Areas"].dropna()
            for a in s.split(",") if a.strip()
        })
        practice_filter = st.selectbox("Filter by Practice Area",
                                       ["All Practice Areas"]+all_areas)
    with col4:
        status_filter = st.selectbox("Filter by Status",
                                     ["Open Only","Closed Only","All Jobs"], index=0)

    df = job_df.copy()
    if amlaw_filter == "Am Law 50":
        df = df[df["Am Law Ranking"].notna() & (df["Am Law Ranking"]<=50)]
    elif amlaw_filter == "Am Law 100":
        df = df[df["Am Law Ranking"].notna() & (df["Am Law Ranking"]<=100)]

    if region_filter.startswith("California"):
        df = df[df["Region"]=="California"]
    elif region_filter.startswith("Washington"):
        df = df[df["Region"]=="Washington"]

    if practice_filter != "All Practice Areas":
        df = df[df["Practice Areas"].str.contains(practice_filter, na=False)]

    if status_filter == "Open Only":
        df = df[df["Status Code"] == 1]
    elif status_filter == "Closed Only":
        df = df[df["Status Code"] == 0]

    if df.empty:
        st.warning("No jobs match your filters."); st.stop()

    jobs_count = len(df)

    top_firms_tab, top_cities_tab, practice_tab, exp_tab = st.tabs(
        ["Top Firms","Top Cities","Practice Areas","Experience"])

    # ---- Top Firms ---------------------------------------------------------
    with top_firms_tab:
        st.subheader(f"Top Hiring Firms ({job_type}) — {jobs_count:,} jobs")
        s      = df["Firm"].value_counts().head(10)
        bar_df = pd.DataFrame({"Firm":s.index,"Count":s.values})
        fig = px.bar(bar_df, x="Firm", y="Count",
                     color_discrete_sequence=[JOB_COLOR])
        fig.update_layout(
            title_text=f"{jobs_count:,} {job_type.lower()} jobs",
            xaxis=dict(categoryorder="total descending"),
            xaxis_fixedrange=True, yaxis_fixedrange=True,
            margin=dict(t=40,b=10,l=10,r=10)
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False}, key="job_top_firms_chart")

        detail_cols = ["Job Title","Firm","Practice Areas","City",
                       "Experience Range","Posted Date","Job Status","Firm Prospects Link"]
        st.dataframe(df[df["Firm"].isin(s.index)][detail_cols],
                     hide_index=True, use_container_width=True)

    # ---- Top Cities --------------------------------------------------------
    with top_cities_tab:
        st.subheader(f"Top Cities for {job_type} Jobs — {jobs_count:,} jobs")
        s      = df["City"].value_counts().head(10)
        bar_df = pd.DataFrame({"City":s.index,"Count":s.values})
        fig = px.bar(bar_df, x="City", y="Count",
                     color_discrete_sequence=[JOB_COLOR])
        fig.update_layout(
            title_text=f"{jobs_count:,} {job_type.lower()} jobs",
            xaxis=dict(categoryorder="total descending"),
            xaxis_fixedrange=True, yaxis_fixedrange=True,
            margin=dict(t=40,b=10,l=10,r=10)
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False}, key="job_top_cities_chart")
        st.dataframe(df[df["City"].isin(s.index)][detail_cols],
                     hide_index=True, use_container_width=True)

    # ---- Practice Areas ----------------------------------------------------
    with practice_tab:
        st.subheader(f"Top Practice Areas ({job_type}) — {jobs_count:,} jobs")
        areas = [
            a.strip()
            for s in df["Practice Areas"].dropna()
            for a in s.split(",") if a.strip()
        ]
        s      = pd.Series(areas).value_counts().head(10)
        bar_df = pd.DataFrame({"Practice Area":s.index,"Count":s.values})
        fig = px.bar(bar_df, x="Practice Area", y="Count",
                     color_discrete_sequence=[JOB_COLOR])
        fig.update_layout(
            title_text=f"{jobs_count:,} {job_type.lower()} jobs",
            xaxis=dict(categoryorder="total descending"),
            xaxis_fixedrange=True,yaxis_fixedrange=True,
            margin=dict(t=40,b=10,l=10,r=10)
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False}, key="job_practice_areas_chart")

        mask = df["Practice Areas"].fillna("").apply(
            lambda cell: any(pa in cell for pa in s.index)
        )
        st.dataframe(df[mask][detail_cols],
                     hide_index=True, use_container_width=True)

    # ---- Experience --------------------------------------------------------
    with exp_tab:
        st.subheader(f"{job_type} Job Listings by Experience — {jobs_count:,} jobs")
        exp_df = df[df["Experience Range"].str.contains(r"\d", na=False)].copy()
        if exp_df.empty:
            st.info("Experience information missing.")
        else:
            exp_df["Min Years"] = exp_df["Experience Range"].str.extract(r"(\d+)").astype(float)
            counts = exp_df["Experience Range"].value_counts()
            bar_df = (pd.DataFrame({"Experience Required":counts.index,
                                    "Number of Jobs":counts.values})
                      .assign(_sort=lambda d: d["Experience Required"]
                              .str.extract(r"(\d+)").astype(float))
                      .sort_values("_sort")
                      [["Experience Required","Number of Jobs"]])
            fig = px.bar(bar_df, x="Experience Required", y="Number of Jobs",
                         color_discrete_sequence=[JOB_COLOR])
            fig.update_layout(
                title_text=f"{jobs_count:,} {job_type.lower()} jobs",
                xaxis_fixedrange=True, yaxis_fixedrange=True,
                margin=dict(t=40,b=10,l=10,r=10)
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False}, key="job_experience_chart")
            st.dataframe(exp_df.sort_values("Min Years")[detail_cols],
                         hide_index=True, use_container_width=True)
## --------------------------------------------------------------------------- #
##  ATTORNEY PLACEMENTS TAB
## --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #
#  ATTORNEY PLACEMENTS TAB
# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #
#  ATTORNEY PLACEMENTS TAB
# --------------------------------------------------------------------------- #
with atty_tab:
    atty_period = st.selectbox("Select Time Period",
        ["Last 1 month","Last 2 months","Last 3 months","Last 6 months"],
        index=2, key="atty_period")
    atty_days = {"Last 1 month":30,"Last 2 months":60,"Last 3 months":90,"Last 6 months":180}[atty_period]

    role_type = st.radio("Select Attorney Type", ["Partners","Associates"],
                         horizontal=True, key="atty_role")
    atty_key = "partners" if role_type=="Partners" else "associates"

    if ("atty_raw" not in st.session_state or
        st.session_state.get("atty_fetch_days")  != atty_days or
        st.session_state.get("atty_fetch_role")  != atty_key):
        st.session_state["atty_raw"]        = fetch_attorneys_from_api(atty_key, atty_days)
        st.session_state["atty_fetch_days"] = atty_days
        st.session_state["atty_fetch_role"] = atty_key
        st.text(f"{len(st.session_state['atty_raw']):,} placement records fetched from API.")

    atty_df = pd.DataFrame([extract_attorney(a) for a in st.session_state["atty_raw"]])

    # add Am Law
    if not atty_df.empty and not amlaw_df.empty:
        atty_df["Firm ID"] = pd.to_numeric(atty_df["Firm ID"], errors="coerce")
        mapping = dict(zip(amlaw_df["FP ID - Firm"], amlaw_df["AmLaw Rank"]))
        idx = atty_df["Am Law Ranking"].isna()
        atty_df.loc[idx, "Am Law Ranking"] = atty_df.loc[idx,"Firm ID"].map(mapping).astype("Int64")

    # top-level filters
    col1,col2,col3 = st.columns(3)
    with col1:
        amlaw_filter = st.selectbox("Filter by Am Law Ranking",
                                    ["All Firms","Am Law 50","Am Law 100"],
                                    key="atty_amlaw")
    with col2:
        region_filter = st.selectbox("Filter by Region",
                                     ["California Only","Washington Only","All Regions"],
                                     key="atty_region")
    with col3:
        all_atty_areas = sorted({
            a.strip()
            for s in atty_df["Practice Areas"].dropna()
            for a in s.split(",") if a.strip()
        })
        practice_filter = st.selectbox("Filter by Practice Area",
                                       ["All Practice Areas"]+all_atty_areas,
                                       key="atty_practice")

    df = atty_df.copy()
    if amlaw_filter=="Am Law 50":
        df = df[df["Am Law Ranking"].notna() & (df["Am Law Ranking"]<=50)]
    elif amlaw_filter=="Am Law 100":
        df = df[df["Am Law Ranking"].notna() & (df["Am Law Ranking"]<=100)]

    if region_filter.startswith("California"):
        df = df[df["Region"]=="California"]
    elif region_filter.startswith("Washington"):
        df = df[df["Region"]=="Washington"]

    if practice_filter!="All Practice Areas":
        df = df[df["Practice Areas"].str.contains(practice_filter, na=False)]

    if df.empty:
        st.warning("No placements match your filters."); st.stop()

    placements_count = len(df)  # ← live count

    top_firms_tab, top_cities_tab, practice_tab, exp_tab = st.tabs(
        ["Top Firms","Top Cities","Practice Areas","Experience"])

    # ---- Top Destination Firms --------------------------------------------
    with top_firms_tab:
        st.subheader(f"Top Destination Firms ({role_type}) — {placements_count:,} placements")
        s      = df["To Firm"].value_counts().head(10)
        bar_df = pd.DataFrame({"Firm":s.index,"Count":s.values})
        fig = px.bar(bar_df, x="Firm", y="Count",
                     color_discrete_sequence=[ATTY_COLOR])
        fig.update_layout(
            title_text=f"{placements_count:,} {role_type.lower()} placements",
            xaxis=dict(categoryorder="total descending"),
            xaxis_fixedrange=True,yaxis_fixedrange=True,
            margin=dict(t=40,b=10,l=10,r=10)
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False}, key="atty_top_firms_chart")
        detail_cols = ["Name","From Firm","To Firm","Practice Areas",
                       "City","Title","Move Date"]
        st.dataframe(df[df["To Firm"].isin(s.index)][detail_cols],
                     hide_index=True, use_container_width=True)

    # ---- Top Cities --------------------------------------------------------
    with top_cities_tab:
        st.subheader(f"Top Cities for {role_type} Moves — {placements_count:,} placements")
        s      = df["City"].value_counts().head(10)
        bar_df = pd.DataFrame({"City":s.index,"Count":s.values})
        fig = px.bar(bar_df, x="City", y="Count",
                     color_discrete_sequence=[ATTY_COLOR])
        fig.update_layout(
            title_text=f"{placements_count:,} {role_type.lower()} placements",
            xaxis=dict(categoryorder="total descending"),
            xaxis_fixedrange=True,yaxis_fixedrange=True,
            margin=dict(t=40,b=10,l=10,r=10)
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False}, key="atty_top_cities_chart")
        st.dataframe(df[df["City"].isin(s.index)][detail_cols],
                     hide_index=True, use_container_width=True)

    # ---- Practice Areas ----------------------------------------------------
    with practice_tab:
        st.subheader(f"Top Practice Areas ({role_type}) — {placements_count:,} placements")
        areas = [
            a.strip()
            for s in df["Practice Areas"].dropna()
            for a in s.split(",") if a.strip()
        ]
        s      = pd.Series(areas).value_counts().head(10)
        bar_df = pd.DataFrame({"Practice Area":s.index,"Count":s.values})
        fig = px.bar(bar_df, x="Practice Area", y="Count",
                     color_discrete_sequence=[ATTY_COLOR])
        fig.update_layout(
            title_text=f"{placements_count:,} {role_type.lower()} placements",
            xaxis=dict(categoryorder="total descending"),
            xaxis_fixedrange=True,yaxis_fixedrange=True,
            margin=dict(t=40,b=10,l=10,r=10)
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False}, key="atty_practice_areas_chart")

        mask = df["Practice Areas"].fillna("").apply(
            lambda cell: any(pa in cell for pa in s.index)
        )
        st.dataframe(df[mask][detail_cols],
                     hide_index=True, use_container_width=True)

    # ---- Experience --------------------------------------------------------
    with exp_tab:
        st.subheader(f"{role_type} Experience Distribution — {placements_count:,} placements")
        exp = df.copy()
        exp["Graduation Year"] = pd.to_numeric(exp["Graduation Year"], errors="coerce")
        exp = exp.dropna(subset=["Graduation Year"])
        if exp.empty:
            st.info("No experience data available.")
        else:
            current_yr = datetime.now().year
            exp["Years Since JD"] = current_yr - exp["Graduation Year"]
            bins, labels = [0,3,5,8,10,15,20,50], ["0-3","3-5","5-8","8-10","10-15","15-20","20+"]
            exp["Bracket"] = pd.cut(exp["Years Since JD"], bins=bins, labels=labels, right=False)
            s      = exp["Bracket"].value_counts().sort_index()
            bar_df = pd.DataFrame({"Experience":s.index,"Count":s.values})
            fig = px.bar(bar_df, x="Experience", y="Count",
                         color_discrete_sequence=[ATTY_COLOR])
            fig.update_layout(
                title_text=f"{placements_count:,} {role_type.lower()} placements",
                xaxis_fixedrange=True,yaxis_fixedrange=True,
                margin=dict(t=40,b=10,l=10,r=10)
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False}, key="atty_experience_chart")
            exp_cols = ["Name","From Firm","To Firm","Practice Areas","City",
                        "Title","Graduation Year","Years Since JD","Bracket","Move Date"]
            st.dataframe(exp[exp_cols].sort_values("Years Since JD"),
                         hide_index=True, use_container_width=True)
# --------------------------------------------------------------------------- #
#  MONTHLY REPORT TAB
# --------------------------------------------------------------------------- #
with report_tab:
    # Indented block for Monthly Report tab
    st.header("\U0001F4C4 Monthly Report")
    from copy import deepcopy
    # --- Calendar month filter ---
    import calendar
    today = datetime.now()
    months = []
    for i in range(12):
        dt = today.replace(day=1) - pd.DateOffset(months=i)
        months.append((dt.strftime("%B %Y"), dt.year, dt.month))
    month_labels = [m[0] for m in months]
    default_month_idx = 0
    selected_month_label = st.selectbox("Select Month", month_labels, index=default_month_idx, key="monthly_report_month")
    selected_year, selected_month = [(y, m) for lbl, y, m in months if lbl == selected_month_label][0]
    # Calculate start and end date for the selected month (make tz-naive)
    start_date = datetime(selected_year, selected_month, 1)
    end_date = (start_date + pd.DateOffset(months=1)) - pd.Timedelta(days=1)
    # Ensure tz-naive for comparison
    start_date = start_date.replace(tzinfo=None)
    end_date = end_date.replace(tzinfo=None)
    report_type = st.radio(
        "Select Report Type",
        ["Associates", "Partners"],
        horizontal=True,
        key="monthly_report_type_app"
    )
    # --- Fetch data for selected month ---
    days_range = (end_date - start_date).days + 1
    with st.spinner("Loading monthly data..."):
        # Use a session key that includes the month and year for caching
        jobs_key = f"monthly_jobs_raw_{selected_year}_{selected_month}"
        atty_key = "associates" if report_type == "Associates" else "partners"
        atty_data_key = f"monthly_atty_raw_{atty_key}_{selected_year}_{selected_month}"
        if jobs_key not in st.session_state:
            st.session_state[jobs_key] = fetch_jobs_from_api(days_range, start_date, end_date)
        if atty_data_key not in st.session_state or st.session_state.get(f"monthly_atty_type_{selected_year}_{selected_month}") != atty_key:
            st.session_state[atty_data_key] = fetch_attorneys_from_api(atty_key, days_range, start_date, end_date)
            st.session_state[f"monthly_atty_type_{selected_year}_{selected_month}"] = atty_key
    job_df = pd.DataFrame([extract_job(j) for j in st.session_state[jobs_key]])
    atty_df = pd.DataFrame([extract_attorney(a) for a in st.session_state[atty_data_key]])
    amlaw_df = load_amlaw_data()
    if not job_df.empty and not amlaw_df.empty:
        job_df["Firm ID"] = pd.to_numeric(job_df["Firm ID"], errors="coerce")
        mapping = dict(zip(amlaw_df["FP ID - Firm"], amlaw_df["AmLaw Rank"]))
        job_df["Am Law Ranking"] = job_df["Firm ID"].map(mapping).astype("Int64")
    if not atty_df.empty and not amlaw_df.empty:
        atty_df["Firm ID"] = pd.to_numeric(atty_df["Firm ID"], errors="coerce")
        mapping = dict(zip(amlaw_df["FP ID - Firm"], amlaw_df["AmLaw Rank"]))
        atty_df["Am Law Ranking"] = atty_df["Firm ID"].map(mapping).astype("Int64")
    # --- Filter by selected month (Move Date for atty_df, Posted Date for job_df) ---
    if not job_df.empty:
        if report_type == "Associates":
            job_df = job_df[job_df["Job Type"].str.contains("Associate", na=False, case=False)]
        else:
            job_df = job_df[job_df["Job Type"].str.contains("Partner", na=False, case=False)]
        job_df = job_df.drop_duplicates(subset=["Job Title", "Firm"], keep="first")
        # Filter jobs by posted date in selected month
        if "Posted Date" in job_df.columns:
            job_df["Posted Date"] = pd.to_datetime(job_df["Posted Date"], errors="coerce")
            # Remove timezone info if present
            if pd.api.types.is_datetime64_any_dtype(job_df["Posted Date"]):
                job_df["Posted Date"] = job_df["Posted Date"].dt.tz_localize(None)
            job_df = job_df[(job_df["Posted Date"] >= start_date) & (job_df["Posted Date"] <= end_date)]
    if not atty_df.empty:
        # Filter attorneys by move date in selected month
        if "last_move_date" in atty_df.columns:
            atty_df["last_move_date"] = pd.to_datetime(atty_df["last_move_date"], errors="coerce")
            if pd.api.types.is_datetime64_any_dtype(atty_df["last_move_date"]):
                atty_df["last_move_date"] = atty_df["last_move_date"].dt.tz_localize(None)
            atty_df = atty_df[(atty_df["last_move_date"] >= start_date) & (atty_df["last_move_date"] <= end_date)]
    def generate_email_report_text(job_df, atty_df, report_type):
        lines = []
        # Use selected_month_label from outer scope if available, else fallback
        try:
            month_label = selected_month_label
        except NameError:
            month_label = datetime.now().strftime("%B %Y")
        lines.append(f"MONTHLY REPORT – {report_type.upper()} ({month_label})")
        lines.append("")
        lines.append("PLACEMENTS:")
        if atty_df.empty:
            lines.append("  No placements in the last 30 days.")
        else:
            top_firms = atty_df["To Firm"].value_counts().head(10)
            lines.append("  Top 10 Destination Firms:")
            for i, (firm, count) in enumerate(top_firms.items(), 1):
                lines.append(f"    {i}. {firm} ({count})")
            lines.append("")
            areas = [a.strip() for s in atty_df["Practice Areas"].dropna() for a in s.split(",") if a.strip()]
            top_areas = pd.Series(areas).value_counts().head(5)
            lines.append("  Top 5 Practice Areas:")
            for i, (area, count) in enumerate(top_areas.items(), 1):
                lines.append(f"    {i}. {area} ({count})")
            lines.append("")
            specialties = [a.strip() for s in atty_df["Specialties"].dropna() for a in s.split(",") if a.strip()]
            top_specialties = pd.Series(specialties).value_counts().head(5)
            lines.append("  Top 5 Specialties:")
            for i, (spec, count) in enumerate(top_specialties.items(), 1):
                lines.append(f"    {i}. {spec} ({count})")
            lines.append("")
            top_cities = atty_df["City"].value_counts().head(5)
            lines.append("  Top 5 Cities:")
            for i, (city, count) in enumerate(top_cities.items(), 1):
                lines.append(f"    {i}. {city} ({count})")
            lines.append("")
        grad_years = atty_df["Graduation Year"].dropna()
        grad_years_rounded = grad_years.astype(float).round(0).astype(int).astype(str)
        top_years = grad_years_rounded.value_counts().head(5)
        lines.append("  Top 5 JD Year:")
        for i, (year, count) in enumerate(top_years.items(), 1):
            lines.append(f"    {i}. {year} ({count} placements)")
        lines.append("")
        lines.append("")
        lines.append("JOB POSTINGS:")
        if job_df.empty:
            lines.append("  No job postings in the last 30 days.")
        else:
            top_hiring_firms = job_df["Firm"].value_counts().head(10)
            lines.append("  Top 10 Hiring Firms:")
            for i, (firm, count) in enumerate(top_hiring_firms.items(), 1):
                lines.append(f"    {i}. {firm} ({count})")
            lines.append("")
            areas = [a.strip() for s in job_df["Practice Areas"].dropna() for a in s.split(",") if a.strip()]
            top_areas = pd.Series(areas).value_counts().head(5)
            lines.append("  Top 5 Practice Areas:")
            for i, (area, count) in enumerate(top_areas.items(), 1):
                lines.append(f"    {i}. {area} ({count})")
            lines.append("")
            specialties = [a.strip() for s in job_df["Specialties"].dropna() for a in s.split(",") if a.strip()]
            top_specialties = pd.Series(specialties).value_counts().head(5)
            lines.append("  Top 5 Specialties:")
            for i, (spec, count) in enumerate(top_specialties.items(), 1):
                lines.append(f"    {i}. {spec} ({count})")
            lines.append("")
            top_cities = job_df["City"].value_counts().head(5)
            lines.append("  Top 5 Cities:")
            for i, (city, count) in enumerate(top_cities.items(), 1):
                lines.append(f"    {i}. {city} ({count})")
            lines.append("")
            if "Experience Range" in job_df.columns:
                exp_ranges = job_df["Experience Range"].dropna()
                top_exp = exp_ranges.value_counts().head(5)
                lines.append("  Top 5 Experience Requirements:")
                for i, (exp, count) in enumerate(top_exp.items(), 1):
                    lines.append(f"    {i}. {exp} ({count})")
                lines.append("")
        return "\n".join(lines)
    st.subheader("\U0001F4E7 Email Report Format")
    st.text_area(
        "Copy this text for your email:",
        value=generate_email_report_text(job_df, atty_df, report_type),
        height=600,
        help="This report is formatted for easy copy-paste into emails"
    )
    # Tip removed as requested
    st.markdown("---")
    # Table title with month and year
    st.subheader(f"All Lateral Movements ({selected_month_label})")
    if atty_df.empty:
        st.info("No lateral movements in the last 30 days.")
    else:
        # --- Add filters (Am Law 200/Non-Am Law, Am Law Ranking, Region, Practice Area) ---
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            firm_type = st.selectbox(
                "Firm Type",
                ["All Firms", "Am Law 50", "Am Law 100", "Am Law 200", "Non-Am Law"],
                key="monthly_firm_type"
            )
        with col2:
            amlaw_filter = st.selectbox(
                "Filter by Am Law Ranking",
                ["All Firms", "Am Law 50", "Am Law 100"],
                key="monthly_amlaw"
            )
        with col3:
            region_options = ["All Regions"]
            if "Region" in atty_df.columns:
                region_options = sorted(set(atty_df["Region"].dropna().unique()))
                region_options = ["All Regions"] + region_options
            region_filter = st.selectbox(
                "Filter by Region",
                region_options,
                key="monthly_region"
            )
        with col4:
            all_atty_areas = sorted({
                a.strip()
                for s in atty_df["Practice Areas"].dropna()
                for a in s.split(",") if a.strip()
            })
            practice_filter = st.selectbox(
                "Filter by Practice Area",
                ["All Practice Areas"] + all_atty_areas,
                key="monthly_practice"
            )

        # --- Apply filters ---
        filtered_df = atty_df.copy()
        # Firm type filter
        if firm_type == "Am Law 50":
            if "Am Law Ranking" in filtered_df.columns:
                filtered_df = filtered_df[filtered_df["Am Law Ranking"].notna() & (filtered_df["Am Law Ranking"] <= 50)]
        elif firm_type == "Am Law 100":
            if "Am Law Ranking" in filtered_df.columns:
                filtered_df = filtered_df[filtered_df["Am Law Ranking"].notna() & (filtered_df["Am Law Ranking"] <= 100)]
        elif firm_type == "Am Law 200":
            if "Am Law Ranking" in filtered_df.columns:
                filtered_df = filtered_df[filtered_df["Am Law Ranking"].notna()]
        elif firm_type == "Non-Am Law":
            if "Am Law Ranking" in filtered_df.columns:
                filtered_df = filtered_df[filtered_df["Am Law Ranking"].isna()]

        # Am Law Ranking filter (still allow secondary filter)
        if amlaw_filter == "Am Law 50":
            if "Am Law Ranking" in filtered_df.columns:
                filtered_df = filtered_df[filtered_df["Am Law Ranking"].notna() & (filtered_df["Am Law Ranking"] <= 50)]
        elif amlaw_filter == "Am Law 100":
            if "Am Law Ranking" in filtered_df.columns:
                filtered_df = filtered_df[filtered_df["Am Law Ranking"].notna() & (filtered_df["Am Law Ranking"] <= 100)]

        if region_filter != "All Regions" and "Region" in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["Region"] == region_filter]

        if practice_filter != "All Practice Areas":
            filtered_df = filtered_df[filtered_df["Practice Areas"].str.contains(practice_filter, na=False)]

        if filtered_df.empty:
            st.warning("No placements match your filters.")
        else:
            expected_cols = [
                ("id", "ID"),
                ("Name", "Name"),
                ("From Firm", "From Firm"),
                ("To Firm", "To Firm"),
                ("Practice Areas", "Practice Areas"),
                ("City", "City"),
                ("Title", "Title"),
                ("last_move_date", "Move Date")
            ]
            data = {}
            for col, _ in expected_cols:
                if col in filtered_df.columns:
                    data[col] = filtered_df[col]
                else:
                    data[col] = ["" for _ in range(len(filtered_df))]
            display_df = pd.DataFrame(data)
            display_df.columns = [disp for _, disp in expected_cols]
            st.dataframe(display_df.head(2000), use_container_width=True)
    