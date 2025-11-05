import streamlit as st
import pandas as pd
import plotly.express as px
import os
from datetime import datetime, timedelta
import requests

# ─── constants ──────────────────────────────────────────────────────────────
TABLE_LIMIT = 2000  # Maximum rows to display in tables

# ─── API endpoints ────────────────────────────────────────────────────────────
JOBS_API_ENDPOINT      = "https://developer.firmprospects.com/v1/jobs"
ATTORNEYS_API_ENDPOINT = "https://developer.firmprospects.com/v1/attorneys"

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
def fetch_jobs_from_api(days_range=30):
    key = get_api_key()
    if not key:
        return []
    headers = {"X-AUTH-TOKEN": key, "Content-Type": "application/json"}
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
        try:
            r.raise_for_status()
        except requests.exceptions.HTTPError as e:
            st.error(f"Jobs API request failed: {e}\nResponse:\n{getattr(r, 'text', '')}")
            continue
        try:
            data = r.json().get("data", [])
        except ValueError:
            st.error(f"Jobs API returned non-JSON response:\n{r.text}")
            continue
        for rec in data:
            jobs_by_id[rec["id"]] = rec
    return list(jobs_by_id.values())

@st.cache_data(ttl=24*3600)
def fetch_jobs_from_api_custom_dates(start_date, end_date):
    """Fetch jobs with custom date range"""
    key = get_api_key()
    if not key:
        return []
    headers = {"X-AUTH-TOKEN": key, "Content-Type": "application/json"}
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")
    params = {"t": "", "page[limit]": 5000, "page[offset]": 0, "condition": "AND"}

    def payload(role):
        return {
            "regions": {"items": ["California", "Washington-Seattle"],
                        "condition": "or", "use_second_location": True},
            "posted_date": {"min": start_str, "max": end_str},
            "titles": [role]
        }
    
    jobs_by_id = {}
    for role in ("Associate", "Partner"):
        r = requests.post(JOBS_API_ENDPOINT, headers=headers,
                          json=payload(role), params=params)
        try:
            r.raise_for_status()
        except requests.exceptions.HTTPError as e:
            st.error(f"Jobs API request failed: {e}\nResponse:\n{getattr(r, 'text', '')}")
            continue
        try:
            data = r.json().get("data", [])
        except ValueError:
            st.error(f"Jobs API returned non-JSON response:\n{r.text}")
            continue
        for rec in data:
            jobs_by_id[rec["id"]] = rec
    return list(jobs_by_id.values())

@st.cache_data(ttl=24*3600)
def fetch_attorneys_from_api(attorney_type="associates", days_range=90):
    key = get_api_key()
    if not key:
        return []
    headers = {"X-AUTH-TOKEN": key, "Content-Type": "application/json"}
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
    try:
        r.raise_for_status()
    except requests.exceptions.HTTPError as e:
        st.error(f"Attorneys API request failed: {e}\nResponse:\n{getattr(r, 'text', '')}")
        return []
    try:
        return r.json().get("data", [])
    except ValueError:
        st.error(f"Attorneys API returned non-JSON response:\n{r.text}")
        return []

@st.cache_data(ttl=24*3600)
def fetch_attorneys_from_api_custom_dates(start_date, end_date, attorney_type="associates"):
    """Fetch attorneys with custom date range"""
    key = get_api_key()
    if not key:
        return []
    headers = {"X-AUTH-TOKEN": key, "Content-Type": "application/json"}
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")
    params = {"t": "", "page[limit]": 5000, "page[offset]": 0, "condition": "AND"}

    payload = {
        "regions": {"items": ["California"], "condition": "or",
                    "use_second_location": True},
        "last_move_date": {"min": start_str, "max": end_str},
        "titles": ["Associate"] if attorney_type == "associates" else ["Partner"],
    }
    r = requests.post(ATTORNEYS_API_ENDPOINT, headers=headers,
                      json=payload, params=params)
    try:
        r.raise_for_status()
    except requests.exceptions.HTTPError as e:
        st.error(f"Attorneys API request failed: {e}\nResponse:\n{getattr(r, 'text', '')}")
        return []
    try:
        return r.json().get("data", [])
    except ValueError:
        st.error(f"Attorneys API returned non-JSON response:\n{r.text}")
        return []

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

    # Ensure 'Practice Areas' is populated even if missing
    practice_areas = j.get("practiceAreas", []) or []

    return {
        "Job Title": j.get("jobTitle", ""),
        "Firm": j.get("firmName", ""),
        "Practice Areas": ", ".join(practice_areas),
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
    # Try recent_move.date, then experience.last_move_date
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

def display_limited_dataframe(df, cols, limit=TABLE_LIMIT):
    """Display dataframe with row limit and warning if truncated"""
    if len(df) > limit:
        st.warning(f"⚠️ Showing first {limit:,} rows of {len(df):,} total results. Use filters to narrow your search.")
        st.dataframe(df.head(limit)[cols], hide_index=True, use_container_width=True)
    else:
        st.dataframe(df[cols], hide_index=True, use_container_width=True)

def dashboard_insights():
    """Insights Dashboard Logic"""
    
    # ─── Insights Dashboard Logic ────────────────────────────────────────────────
    job_tab, atty_tab = st.tabs(["Job Postings", "Attorney Placements"])

    # Job Postings Tab
    with job_tab:
        period_options = ["Last 7 days", "Last 14 days", "Last 30 days", "Last 60 days", "Select Dates"]
        period_label = st.selectbox("Select Time Period", period_options, index=2)
        
        if period_label == "Select Dates":
            col1, col2 = st.columns(2)
            with col1:
                start_date = st.date_input("Start Date", value=datetime.now() - timedelta(days=30))
            with col2:
                end_date = st.date_input("End Date", value=datetime.now())
            
            # Calculate days between dates
            period_days = (end_date - start_date).days
            if period_days <= 0:
                st.error("End date must be after start date.")
                return
        else:
            period_days = {"Last 7 days":7,"Last 14 days":14,"Last 30 days":30,"Last 60 days":60}[period_label]
            start_date = end_date = None

        job_type = st.radio("Select Job Type", ["Associates", "Partners"], horizontal=True)

        # Use custom dates or period_days for API fetch
        cache_key = f"{period_days}_{start_date}_{end_date}" if period_label == "Select Dates" else str(period_days)
        
        if ("job_raw" not in st.session_state or
            st.session_state.get("jobs_fetch_key") != cache_key):
            if period_label == "Select Dates":
                st.session_state["job_raw"] = fetch_jobs_from_api_custom_dates(start_date, end_date)
            else:
                st.session_state["job_raw"] = fetch_jobs_from_api(period_days)
            st.session_state["jobs_fetch_key"] = cache_key
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
            st.warning("No jobs match your filters.")
            return

        jobs_count = len(df)

        top_firms_tab, top_cities_tab, practice_tab, exp_tab = st.tabs(
            ["Top Firms","Top Cities","Practice Areas","Experience"])

        # ---- Top Firms ---------------------------------------------------------
        with top_firms_tab:
            st.subheader(f"Top Hiring Firms ({job_type}) — {jobs_count:,} jobs")
            s      = df["Firm"].value_counts().head(10)
            bar_df = pd.DataFrame({"Firm":s.index,"Count":s.values})
            fig = px.bar(bar_df, x="Firm", y="Count",
                         color_discrete_sequence=["#636EFA"])
            fig.update_layout(
                title_text=f"{jobs_count:,} {job_type.lower()} jobs",
                xaxis=dict(categoryorder="total descending"),
                xaxis_fixedrange=True, yaxis_fixedrange=True,
                margin=dict(t=40,b=10,l=10,r=10)
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False})
            detail_cols = ["Job Title","Firm","Practice Areas","City",
                          "Experience Range","Posted Date","Job Status"]
            display_limited_dataframe(df[df["Firm"].isin(s.index)], detail_cols)

        # ---- Top Cities --------------------------------------------------------
        with top_cities_tab:
            st.subheader(f"Top Cities for {job_type} Jobs — {jobs_count:,} jobs")
            s      = df["City"].value_counts().head(10)
            bar_df = pd.DataFrame({"City":s.index,"Count":s.values})
            fig = px.bar(bar_df, x="City", y="Count",
                         color_discrete_sequence=["#636EFA"])
            fig.update_layout(
                title_text=f"{jobs_count:,} {job_type.lower()} jobs",
                xaxis=dict(categoryorder="total descending"),
                xaxis_fixedrange=True, yaxis_fixedrange=True,
                margin=dict(t=40,b=10,l=10,r=10)
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False})
            detail_cols = ["Job Title","Firm","Practice Areas","City",
                          "Experience Range","Posted Date","Job Status"]
            display_limited_dataframe(df[df["City"].isin(s.index)], detail_cols)

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
                         color_discrete_sequence=["#636EFA"])
            fig.update_layout(
                title_text=f"{jobs_count:,} {job_type.lower()} jobs",
                xaxis=dict(categoryorder="total descending"),
                xaxis_fixedrange=True,yaxis_fixedrange=True,
                margin=dict(t=40,b=10,l=10,r=10)
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False})

            mask = df["Practice Areas"].fillna("").apply(
                lambda cell: any(pa in cell for pa in s.index)
            )
            detail_cols = ["Job Title","Firm","Practice Areas","City",
                          "Experience Range","Posted Date","Job Status"]
            display_limited_dataframe(df[mask], detail_cols)

        # ---- Experience --------------------------------------------------------
        with exp_tab:
            st.subheader(f"{job_type} Job Listings by Experience — {jobs_count:,} jobs")
            exp_df = df[df["Experience Range"].str.contains(r"\d", na=False)].copy()
            if exp_df.empty:
                st.warning("No experience data available.")
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
                             color_discrete_sequence=["#636EFA"])
                fig.update_layout(
                    title_text=f"{jobs_count:,} {job_type.lower()} jobs",
                    xaxis_fixedrange=True, yaxis_fixedrange=True,
                    margin=dict(t=40,b=10,l=10,r=10)
                )
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False})
                detail_cols = ["Job Title","Firm","Practice Areas","City",
                              "Experience Range","Posted Date","Job Status"]
                display_limited_dataframe(exp_df.sort_values("Min Years"), detail_cols)

    # Attorney Placements Tab
    with atty_tab:
        atty_period_options = ["Last 1 month", "Last 2 months", "Last 3 months", "Last 6 months", "Select Dates"]
        atty_period = st.selectbox("Select Time Period", atty_period_options, index=2, key="atty_period")
        
        if atty_period == "Select Dates":
            col1, col2 = st.columns(2)
            with col1:
                atty_start_date = st.date_input("Start Date", value=datetime.now() - timedelta(days=90), key="atty_start")
            with col2:
                atty_end_date = st.date_input("End Date", value=datetime.now(), key="atty_end")
            
            atty_days = (atty_end_date - atty_start_date).days
            if atty_days <= 0:
                st.error("End date must be after start date.")
                return
        else:
            atty_days = {"Last 1 month": 30, "Last 2 months": 60, "Last 3 months": 90, "Last 6 months": 180}[atty_period]
            atty_start_date = atty_end_date = None

        role_type = st.radio("Select Attorney Type", ["Partners", "Associates"], horizontal=True)
        atty_key = "partners" if role_type == "Partners" else "associates"

        # Use custom dates or period_days for API fetch
        atty_cache_key = f"{atty_days}_{atty_start_date}_{atty_end_date}_{atty_key}" if atty_period == "Select Dates" else f"{atty_days}_{atty_key}"
        
        if "atty_raw" not in st.session_state or st.session_state.get("atty_fetch_key") != atty_cache_key:
            if atty_period == "Select Dates":
                st.session_state["atty_raw"] = fetch_attorneys_from_api_custom_dates(atty_start_date, atty_end_date, atty_key)
            else:
                st.session_state["atty_raw"] = fetch_attorneys_from_api(atty_key, atty_days)
            st.session_state["atty_fetch_key"] = atty_cache_key

        atty_df = pd.DataFrame([extract_attorney(a) for a in st.session_state["atty_raw"]])

        # Add Am Law Rankings
        amlaw_df = load_amlaw_data()
        if not atty_df.empty and not amlaw_df.empty:
            atty_df["Firm ID"] = pd.to_numeric(atty_df["Firm ID"], errors="coerce")
            mapping = dict(zip(amlaw_df["FP ID - Firm"], amlaw_df["AmLaw Rank"]))
            atty_df["Am Law Ranking"] = atty_df["Firm ID"].map(mapping).astype("Int64")

        # Filters and Visualizations
        col1, col2, col3 = st.columns(3)
        with col1:
            amlaw_filter = st.selectbox("Filter by Am Law Ranking", ["All Firms", "Am Law 50", "Am Law 100"], key="atty_amlaw")
        with col2:
            region_filter = st.selectbox("Filter by Region", ["California Only", "Washington Only", "All Regions"], key="atty_region")
        with col3:
            all_areas = sorted({a.strip() for s in atty_df["Practice Areas"].dropna() for a in s.split(",") if a.strip()})
            practice_filter = st.selectbox("Filter by Practice Area", ["All Practice Areas"] + all_areas, key="atty_practice")

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
            st.warning("No attorneys match your filters.")
            return

        placements_count = len(df)

        top_firms_tab, top_cities_tab, practice_tab, exp_tab = st.tabs(["Top Firms", "Top Cities", "Practice Areas", "Experience"])

        # Top Destination Firms Visualization
        with top_firms_tab:
            st.subheader(f"Top Destination Firms ({role_type}) — {placements_count:,} placements")
            s = df["To Firm"].value_counts().head(10)
            bar_df = pd.DataFrame({"Firm": s.index, "Count": s.values})
            fig = px.bar(bar_df, x="Firm", y="Count", color_discrete_sequence=["#EF553B"])
            fig.update_layout(
                title_text=f"{placements_count:,} {role_type.lower()} placements",
                xaxis=dict(categoryorder="total descending"),
                xaxis_fixedrange=True,yaxis_fixedrange=True,
                margin=dict(t=40,b=10,l=10,r=10)
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False})
            detail_cols = ["Name","From Firm","To Firm","Practice Areas",
                           "City","Title","Move Date"]
            display_limited_dataframe(df[df["To Firm"].isin(s.index)], detail_cols)

        # Top Cities Visualization
        with top_cities_tab:
            st.subheader(f"Top Cities for {role_type} Placements — {placements_count:,} placements")
            s = df["City"].value_counts().head(10)
            bar_df = pd.DataFrame({"City": s.index, "Count": s.values})
            fig = px.bar(bar_df, x="City", y="Count", color_discrete_sequence=["#EF553B"])
            fig.update_layout(
                title_text=f"{placements_count:,} {role_type.lower()} placements",
                xaxis=dict(categoryorder="total descending"),
                xaxis_fixedrange=True,yaxis_fixedrange=True,
                margin=dict(t=40,b=10,l=10,r=10)
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False})
            detail_cols = ["Name","From Firm","To Firm","Practice Areas",
                           "City","Title","Move Date"]
            display_limited_dataframe(df[df["City"].isin(s.index)], detail_cols)

        # Practice Areas Visualization
        with practice_tab:
            st.subheader(f"Top Practice Areas ({role_type}) — {placements_count:,} placements")
            areas = [a.strip() for s in df["Practice Areas"].dropna() for a in s.split(",") if a.strip()]
            s = pd.Series(areas).value_counts().head(10)
            bar_df = pd.DataFrame({"Practice Area": s.index, "Count": s.values})
            fig = px.bar(bar_df, x="Practice Area", y="Count", color_discrete_sequence=["#EF553B"])
            fig.update_layout(
                title_text=f"{placements_count:,} {role_type.lower()} placements",
                xaxis=dict(categoryorder="total descending"),
                xaxis_fixedrange=True,yaxis_fixedrange=True,
                margin=dict(t=40,b=10,l=10,r=10)
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False})

            mask = df["Practice Areas"].fillna("").apply(
                lambda cell: any(pa in cell for pa in s.index)
            )
            detail_cols = ["Name","From Firm","To Firm","Practice Areas",
                           "City","Title","Move Date"]
            display_limited_dataframe(df[mask], detail_cols)

        # Experience Visualization
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
                             color_discrete_sequence=["#EF553B"])
                fig.update_layout(
                    title_text=f"{placements_count:,} {role_type.lower()} placements",
                    xaxis_fixedrange=True,yaxis_fixedrange=True,
                    margin=dict(t=40,b=10,l=10,r=10)
                )
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False})
                exp_cols = ["Name","From Firm","To Firm","Practice Areas","City",
                            "Title","Graduation Year","Years Since JD","Bracket","Move Date"]
                display_limited_dataframe(exp.sort_values("Years Since JD"), exp_cols)
