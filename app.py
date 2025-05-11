import streamlit as st
import pandas as pd
import json
import plotly.express as px
from datetime import datetime, timedelta
import requests
import os

st.set_page_config(page_title="Legal Recruiting Dashboard", layout="wide")
st.title("SLS Insights Dashboard")

# --- API Configuration ---
JOBS_API_ENDPOINT = "https://developer.firmprospects.com/v1/jobs"
ATTORNEYS_API_ENDPOINT = "https://developer.firmprospects.com/v1/attorneys"

# --- Function to get API key from Streamlit secrets or environment ---
def get_api_key():
    # Try to get from Streamlit secrets (recommended for production)
    try:
        return st.secrets["API_CREDENTIALS"]["X_AUTH_TOKEN"]
    except:
        # Fallback to environment variable (for development)
        token = os.environ.get("FIRMPROSPECTS_API_TOKEN")
        if token:
            return token
        # For demo purposes
        st.error("API key not found. Please configure it in Streamlit secrets.")
        return None

# --- Load AmLaw 200 CSV data ---
@st.cache_data
def load_amlaw_data():
    try:
        amlaw_df = pd.read_csv("amlaw_200.csv")
        # Ensure column names are correct
        if "AmLaw Rank" not in amlaw_df.columns or "FP ID - Firm" not in amlaw_df.columns:
            # Try to fix column names if they're different
            amlaw_df.columns = ["AmLaw Rank", "FP ID - Firm"]
        
        # Convert ID to numeric for proper matching
        amlaw_df["FP ID - Firm"] = pd.to_numeric(amlaw_df["FP ID - Firm"], errors='coerce')
        amlaw_df["AmLaw Rank"] = pd.to_numeric(amlaw_df["AmLaw Rank"], errors='coerce')
        
        return amlaw_df
    except Exception as e:
        st.warning(f"Could not load AmLaw 200 data: {str(e)}")
        return pd.DataFrame(columns=["AmLaw Rank", "FP ID - Firm"])

# --- Function to fetch jobs from the API ---
@st.cache_data(ttl=24*3600)  # Cache data for 24 hours
def fetch_jobs_from_api(days_range=30):
    api_key = get_api_key()
    if not api_key:
        return []
        
    headers = {
        "X-AUTH-TOKEN": api_key,
        "Content-Type": "application/json"
    }
    
    # Calculate dates based on the selected time range
    today = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days_range)).strftime("%Y-%m-%d")
    
    # Create payload for associate jobs
    associate_payload = {
        "regions": {
            "items": ["California","Washington-Seattle"],
            "condition": "or",
            "use_second_location": True
        },
        "posted_date": {
            "min": start_date,
            "max": today
        },
        "status": 1,
        "title": ["Associate"]
    }
    
    # Create payload for partner jobs
    partner_payload = {
        "regions": {
            "items": ["California","Washington-Seattle"],
            "condition": "or",
            "use_second_location": True
        },
        "posted_date": {
            "min": start_date,
            "max": today
        },
        "status": 1,
        "title": ["Partners"]
    }
    
    all_jobs = []
    
    try:
        # Make request for associate jobs
        params = {"t": "", "page[limit]": 5000, "page[offset]": 0, "condition": "AND"}
        associate_response = requests.post(JOBS_API_ENDPOINT, headers=headers, json=associate_payload, params=params)
        associate_response.raise_for_status()
        associate_jobs = associate_response.json().get("data", [])
        all_jobs.extend(associate_jobs)
        
        # Make request for partner jobs
        partner_response = requests.post(JOBS_API_ENDPOINT, headers=headers, json=partner_payload, params=params)
        partner_response.raise_for_status()
        partner_jobs = partner_response.json().get("data", [])
        all_jobs.extend(partner_jobs)
        
        return all_jobs
    
    except Exception as e:
        st.error(f"❌ Error fetching jobs from API: {str(e)}")
        return []

# --- Function to fetch attorney data from the API ---
@st.cache_data(ttl=24*3600)  # Cache data for 24 hours
def fetch_attorneys_from_api(attorney_type, days_range=90):
    api_key = get_api_key()
    if not api_key:
        return []
        
    headers = {
        "X-AUTH-TOKEN": api_key,
        "Content-Type": "application/json"
    }
    
    # Calculate dates based on the selected time range
    today = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days_range)).strftime("%Y-%m-%d")
    
    # Set titles based on attorney type
    titles = ["Associate"] if attorney_type == "associates" else ["Partner"]
    
    # Create API payload
    payload = {
        "regions": {
            "items": ["California"],
            "condition": "or",
            "use_second_location": True
        },
        "last_move_date": {
            "min": start_date,
            "max": today
        },
        "titles": titles
    }
    
    try:
        # Make API request
        params = {"t": "", "page[limit]": 5000, "page[offset]": 0, "condition": "AND"}
        response = requests.post(ATTORNEYS_API_ENDPOINT, headers=headers, json=payload, params=params)
        response.raise_for_status()
        attorneys = response.json().get("data", [])
        
        return attorneys
    
    except Exception as e:
        st.error(f"❌ Error fetching {attorney_type} from API: {str(e)}")
        return []

# --- Extract Functions ---
def extract_attorney(attorney):
    recent = attorney.get("recent_move") or {}
    move = recent.get("firm") or {}
    
    # Get the proper AmLaw ranking from firm -> ranks -> top200
    firm_data = attorney.get("firm", {})
    ranks = firm_data.get("ranks", {})
    am_law_ranking = ranks.get("top200")
    
    return {
        "Name": f"{attorney.get('first_name', '')} {attorney.get('last_name', '')}",
        "From Firm": move.get("old", {}).get("firm_name"),
        "To Firm": move.get("new", {}).get("firm_name"),
        "Practice Areas": ", ".join(attorney.get("attorneys_practice_areas", [])) if attorney.get("attorneys_practice_areas") else "",
        "Specialties": ", ".join(attorney.get("attorneys_specialties", [])) if attorney.get("attorneys_specialties") else "",
        "City": attorney.get("location", {}).get("city"),
        "Graduation Year": attorney.get("graduation_year"),
        "Law School": attorney.get("law_school", {}).get("law_school_name"),
        "Current Firm": attorney.get("firm", {}).get("firm_name"),
        "Title": ", ".join(attorney.get("attorneys_titles", [])) if attorney.get("attorneys_titles") else "",
        "FirmProspects ID": attorney.get("id"),
        "Profile Link": f"[Link](https://engage.firmprospects.com/attorneys/profile/{attorney.get('id')})",
        "Am Law Ranking": am_law_ranking,
        "Region": attorney.get("location", {}).get("state"),
        "Move Date": recent.get("date"),
        "Firm ID": firm_data.get("id")
    }

def extract_job(job):
    # Extract the state from locations
    region = None
    if job.get("locations") and len(job["locations"]) > 0:
        location_parts = job["locations"][0].split(", ")
        if len(location_parts) > 1:
            region = location_parts[1]
    
    # Extract city from locations
    city = None
    if job.get("locations") and len(job["locations"]) > 0:
        location_parts = job["locations"][0].split(", ")
        if len(location_parts) > 0:
            city = location_parts[0]
    
    # Format practice areas and specialties
    practice_areas = ", ".join(job.get("practiceAreas", [])) if job.get("practiceAreas") else ""
    specialties = ", ".join(job.get("specialty", [])) if job.get("specialty") else ""
    
    # Calculate experience range
    experience_range = ""
    if job.get("minYrs") is not None and job.get("maxYrs") is not None:
        if job["minYrs"] == job["maxYrs"]:
            experience_range = f"{job['minYrs']} years"
        else:
            experience_range = f"{job['minYrs']}-{job['maxYrs']} years"
    
    # Try different possible fields for firm ID
    firm_id = None
    if "firmId" in job:
        firm_id = job["firmId"]
    elif "firm_id" in job:
        firm_id = job["firm_id"]
    elif "firm" in job and isinstance(job["firm"], dict) and "id" in job["firm"]:
        firm_id = job["firm"]["id"]
    
    return {
        "Job Title": job.get("jobTitle", ""),
        "Firm": job.get("firmName", ""),
        "Practice Areas": practice_areas,
        "Specialties": specialties,
        "City": city,
        "Experience Range": experience_range,
        "Posted Date": job.get("postedDate", ""),
        "Job Status": job.get("statusLabel", ""),
        "Job Type": job.get("title", [""])[0] if job.get("title") else "",
        "FirmProspects ID": job.get("id"),
        "Profile Link": f"[Link]({job.get('pageUrl', '')})",
        "Am Law Ranking": None,  # Will be updated after matching with AmLaw data
        "Region": region,
        "Firm ID": firm_id
    }

# --- Main UI Section ---
# Create tabs for the main views
tab_labels = ["Job Listings", "Attorney Placements"]
main_tabs = st.tabs(tab_labels)

# Load AmLaw data once
amlaw_df = load_amlaw_data()

# Variables to track API success messages
job_data = None
attorney_data = None
api_message_container = st.empty()

# Specific processing for Job Listings tab (first tab)
with main_tabs[0]:  # Job Listings tab
    # Time period selector for jobs
    job_time_options = ["Last 7 days", "Last 14 days", "Last 30 days", "Last 60 days"]
    job_time_values = [7, 14, 30, 60]
    
    selected_job_period = st.selectbox(
        "Select Time Period",
        options=job_time_options,
        index=2  # Default to 30 days
    )
    job_time_period_days = job_time_values[job_time_options.index(selected_job_period)]
    
    # Add job type toggle similar to attorney type
    job_type = st.radio("Select Job Type", ["Associates", "Partners"], horizontal=True)
    
    # Load job data - only if not already loaded
    if job_data is None:
        job_data = fetch_jobs_from_api(job_time_period_days)
        if job_data:
            with api_message_container:
                st.success(f"{len(job_data)} Job Postings")
    
    # Create the job DataFrame
    job_df = pd.DataFrame([extract_job(j) for j in job_data])
    
    # Update AmLaw ranking based on Firm ID
    if not job_df.empty and not amlaw_df.empty:
        # Convert to appropriate types to ensure matching works
        job_df["Firm ID"] = pd.to_numeric(job_df["Firm ID"], errors='coerce')
        
        # Create a mapping dictionary from firm ID to AmLaw rank
        amlaw_mapping = dict(zip(amlaw_df["FP ID - Firm"], amlaw_df["AmLaw Rank"]))
        
        # Apply mapping to get AmLaw rankings (using .loc to avoid SettingWithCopyWarning)
        job_df.loc[:, "Am Law Ranking"] = job_df["Firm ID"].map(amlaw_mapping)
    
    # Filter job_df based on job_type (using .copy() to avoid SettingWithCopyWarning)
    if job_type == "Associates":
        filtered_job_df = job_df[job_df["Job Type"].str.contains("Associate", case=False, na=False)].copy()
    else:  # Partners
        filtered_job_df = job_df[job_df["Job Type"].str.contains("Partner", case=False, na=False)].copy()
    
    # Check if dataframe is empty after filtering
    if filtered_job_df.empty:
        st.warning(f"No {job_type.lower()} job data available for the selected criteria in the selected time period.")
    else:
        # --- Filter UI ---
        # Extract all unique practice areas for filter
        job_practice_areas = []
        for practice_areas_str in filtered_job_df["Practice Areas"].dropna():
            areas = practice_areas_str.split(", ")
            job_practice_areas.extend(areas)
        
        # Convert to a set to get unique values, then sort
        unique_job_practice_areas = sorted(set(job_practice_areas))
        unique_job_practice_areas.insert(0, "All Practice Areas")
        
        # Create filter container
        filter_container = st.container()
        
        with filter_container:
            col1, col2, col3 = st.columns(3)
            
            with col1:
                # Am Law ranking filter
                amlaw_options = ["All Firms", "Am Law 50", "Am Law 100"]
                amlaw_filter = st.selectbox("Filter by Am Law Ranking", amlaw_options, key="job_amlaw")
            
            with col2:
                # Region filter
                region_options = ["California Only", "Washington Only", "All Regions"]
                region_filter = st.selectbox("Filter by Region", region_options, index=0, key="job_region")
                
            with col3:
                # Practice area filter
                practice_area_filter = st.selectbox("Filter by Practice Area", unique_job_practice_areas, key="job_practice")
        
        # Apply filters to job dataframe
        filtered_filtered_job_df = filtered_job_df.copy()
        
        # Apply Am Law filter with proper handling of missing values
        if amlaw_filter == "Am Law 50":
            filtered_filtered_job_df = filtered_filtered_job_df[filtered_filtered_job_df["Am Law Ranking"].notna() & (filtered_filtered_job_df["Am Law Ranking"] <= 50)]
        elif amlaw_filter == "Am Law 100":
            filtered_filtered_job_df = filtered_filtered_job_df[filtered_filtered_job_df["Am Law Ranking"].notna() & (filtered_filtered_job_df["Am Law Ranking"] <= 100)]
        
        # Apply Region filter
        if region_filter == "California Only":
            filtered_filtered_job_df = filtered_filtered_job_df[filtered_filtered_job_df["Region"] == "California"]
        elif region_filter == "Washington Only":
            filtered_filtered_job_df = filtered_filtered_job_df[filtered_filtered_job_df["Region"] == "Washington"]
        
        # Apply Practice Area filter
        if practice_area_filter != "All Practice Areas":
            filtered_filtered_job_df = filtered_filtered_job_df[filtered_filtered_job_df["Practice Areas"].str.contains(practice_area_filter, na=False)]
        
        # Check if filtered dataframe is empty
        if filtered_filtered_job_df.empty:
            st.warning(f"No {job_type.lower()} job data available with the current filters. Try adjusting your filters.")
        else:
            # --- Job data visualization tabs ---
            job_tabs = st.tabs(["Top Firms", "Top Cities", "Practice Areas", "Experience"])
            
            # Define a consistent color for the job tabs
            JOB_COLOR = '#636EFA'  # Plotly's default blue
            
            # Tab 1: Top Firms
            with job_tabs[0]:
                # Get top firms and sort in descending order
                top_firms = filtered_filtered_job_df["Firm"].value_counts().head(10).sort_values(ascending=False)
                st.subheader(f"Top {len(top_firms)} Hiring Firms")
                
                # Handle empty dataframe case
                if len(top_firms) > 0:
                    # Convert Series to DataFrame for plotly
                    plot_df = pd.DataFrame({'Firms': top_firms.index, 'Count': top_firms.values})
                    
                    # Create a bar chart with properly sorted values
                    fig = px.bar(
                        plot_df,
                        x='Firms',
                        y='Count',
                        labels={"Count": f"Number of {job_type} Job Listings", "Firms": ""},
                        color_discrete_sequence=[JOB_COLOR]
                    )
                    
                    # Customize layout to disable interactivity but keep responsiveness
                    fig.update_layout(
                        xaxis=dict(categoryorder='total descending'),
                        margin=dict(t=10, b=10, l=10, r=10),
                        xaxis_fixedrange=True,
                        yaxis_fixedrange=True
                    )
                    
                    # Render chart with container width responsiveness but disabled toolbar
                    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
                else:
                    st.info("No data available with current filters.")
                
                # Show the detailed job listings
                st.subheader("Job Details")
                columns_order = ["Job Title", "Firm", "Practice Areas", "City", "Experience Range", "Posted Date"]
                display_df = filtered_filtered_job_df[filtered_filtered_job_df["Firm"].isin(top_firms.index.tolist())][columns_order] if not top_firms.empty else pd.DataFrame(columns=columns_order)
                if not display_df.empty:
                    st.dataframe(display_df, hide_index=True)
                else:
                    st.info("No detailed data available with current filters.")
            
            # Tab 2: Top Cities
            with job_tabs[1]:  # Top Cities
                st.subheader(f"Top Cities for {job_type} Job Listings")
                
                # Get top cities with job postings
                job_top_cities = filtered_filtered_job_df["City"].value_counts().head(10).sort_values(ascending=False)
                
                if len(job_top_cities) > 0:
                    # Convert Series to DataFrame for plotting
                    job_city_df = pd.DataFrame({"Cities": job_top_cities.index, "Count": job_top_cities.values})
                    
                    # Create bar chart (same style as Top Firms)
                    fig = px.bar(
                        job_city_df,
                        x="Cities",
                        y="Count",
                        labels={"Count": f"Number of {job_type} Jobs", "Cities": ""},
                        color_discrete_sequence=[JOB_COLOR]  # Use consistent color
                    )
                    
                    # Customize layout to match Top Firms
                    fig.update_layout(
                        xaxis=dict(categoryorder='total descending'),
                        margin=dict(t=10, b=10, l=10, r=10),
                        xaxis_fixedrange=True,
                        yaxis_fixedrange=True
                    )
                    
                    # Render chart
                    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
                    
                    # Show table of jobs by city
                    st.subheader("Job Details by City")
                    job_city_columns = ["Job Title", "Firm", "Practice Areas", "City", "Experience Range", "Posted Date"]
                    job_city_df_details = filtered_filtered_job_df[filtered_filtered_job_df["City"].isin(job_top_cities.index.tolist())][job_city_columns]
                    if not job_city_df_details.empty:
                        st.dataframe(job_city_df_details, hide_index=True)
                else:
                    st.info("No city data available with current filters.")
            
            # Tab 3: Practice Areas
            with job_tabs[2]:  # Practice Areas
                st.subheader(f"Top Practice Areas in {job_type} Job Listings")
                
                # Process practice areas (they're comma-separated in the dataframe)
                job_all_areas = []
                for areas in filtered_filtered_job_df["Practice Areas"].dropna():
                    job_all_areas.extend([area.strip() for area in areas.split(",")])
                
                # Count occurrences and get top practice areas
                job_practice_counts = pd.Series(job_all_areas).value_counts().head(10)
                
                if len(job_practice_counts) > 0:
                    # Convert to DataFrame for plotting
                    job_practice_df = pd.DataFrame({"Practice Area": job_practice_counts.index, "Count": job_practice_counts.values})
                    
                    # Create bar chart to match Top Firms style
                    fig = px.bar(
                        job_practice_df,
                        x="Practice Area",
                        y="Count",
                        labels={"Count": f"Number of {job_type} Jobs", "Practice Area": ""},
                        color_discrete_sequence=[JOB_COLOR]  # Use consistent color
                    )
                    
                    # Update layout to match Top Firms
                    fig.update_layout(
                        xaxis=dict(categoryorder='total descending'),
                        margin=dict(t=10, b=10, l=10, r=10),
                        xaxis_fixedrange=True,
                        yaxis_fixedrange=True
                    )
                    
                    # Render chart
                    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
                    
                    # Show table view too
                    st.subheader(f"Practice Area Distribution in {job_type} Job Listings")
                    st.dataframe(job_practice_df, hide_index=True)
                else:
                    st.info("No practice area data available with current filters.")
            
            # Tab 4: Experience
            with job_tabs[3]:  # Experience
                st.subheader(f"{job_type} Job Listings by Experience Level")
                
                # Create a copy for modifications
                experience_job_df = filtered_filtered_job_df.copy()
                
                # Group by experience range and count
                if "Experience Range" in experience_job_df.columns and not experience_job_df.empty:
                    # Remove any rows with missing or invalid experience range
                    valid_exp_df = experience_job_df.dropna(subset=["Experience Range"])
                    valid_exp_df = valid_exp_df[valid_exp_df["Experience Range"].str.contains(r'\d+', regex=True)]
                    
                    if not valid_exp_df.empty:
                        # Create a new column for min years of experience (for sorting)
                        valid_exp_df.loc[:, "Min Experience"] = valid_exp_df["Experience Range"].str.extract(r'(\d+)').astype(float)
                        
                        exp_job_counts = valid_exp_df["Experience Range"].value_counts().sort_index()
                        
                        # Create DataFrame for plotting
                        exp_job_df = pd.DataFrame({"Experience Required": exp_job_counts.index, "Number of Jobs": exp_job_counts.values})
                        
                        # Sort the DataFrame by min experience
                        exp_job_df.loc[:, "Min Years"] = exp_job_df["Experience Required"].str.extract(r'(\d+)').astype(float)
                        exp_job_df = exp_job_df.sort_values("Min Years")
                        
                        # Create a bar chart to match Top Firms style
                        fig = px.bar(
                            exp_job_df,
                            x="Experience Required",
                            y="Number of Jobs",
                            labels={"Number of Jobs": "Count", "Experience Required": "Years of Experience Required"},
                            color_discrete_sequence=[JOB_COLOR]  # Use consistent color
                        )
                        
                        # Update layout to match Top Firms
                        fig.update_layout(
                            margin=dict(t=10, b=10, l=10, r=10),
                            xaxis_fixedrange=True,
                            yaxis_fixedrange=True
                        )
                        
                        # Render chart
                        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
                        
                        # Show table with job details by experience
                        st.subheader("Job Details by Experience Requirement")
                        job_exp_columns = ["Job Title", "Firm", "Practice Areas", "City", "Experience Range", "Posted Date"]
                        job_exp_df_details = valid_exp_df.sort_values("Min Experience")[job_exp_columns]
                        if not job_exp_df_details.empty:
                            st.dataframe(job_exp_df_details, hide_index=True)
                    else:
                        st.info("No experience data available with current filters.")
                else:
                    st.info("No experience data available with current filters.")

# Specific processing for Attorney Placements tab (second tab)
with main_tabs[1]:  # Attorney Placements tab
    # Time period selector for attorneys
    attorney_time_options = ["Last 1 month", "Last 2 months", "Last 3 months", "Last 6 months"]
    attorney_time_values = [30, 60, 90, 180]
    
    selected_attorney_period = st.selectbox(
        "Select Time Period",
        options=attorney_time_options,
        index=2,  # Default to 3 months
        key="atty_time_period"
    )
    attorney_time_period_days = attorney_time_values[attorney_time_options.index(selected_attorney_period)]
    
    # Attorney type selector
    role_type = st.radio("Select Attorney Type", ["Partners", "Associates"], horizontal=True, key="atty_type")
    
    # Load data based on selections - only if we haven't loaded it yet
    if attorney_data is None:
        if role_type == "Partners":
            attorney_data = fetch_attorneys_from_api("partners", attorney_time_period_days)
            if attorney_data and "job_data" not in st.session_state:
                with api_message_container:
                    st.success(f"{len(attorney_data)} Placement Records")
                st.session_state.job_data = True
        else:  # Associates
            attorney_data = fetch_attorneys_from_api("associates", attorney_time_period_days)
            if attorney_data and "job_data" not in st.session_state:
                with api_message_container:
                    st.success(f"{len(attorney_data)} Placement Records")
                st.session_state.job_data = True
    
    # Create attorney DataFrame
    attorney_df = pd.DataFrame([extract_attorney(a) for a in attorney_data])
    
    # Update AmLaw ranking based on Firm ID (if not already set)
    if not attorney_df.empty and not amlaw_df.empty:
        # Convert to appropriate types to ensure matching works
        attorney_df["Firm ID"] = pd.to_numeric(attorney_df["Firm ID"], errors='coerce')
        
        # Create a mapping dictionary from firm ID to AmLaw rank
        amlaw_mapping = dict(zip(amlaw_df["FP ID - Firm"], amlaw_df["AmLaw Rank"]))
        
        # Only update AmLaw rankings that are not already set (using .loc to avoid SettingWithCopyWarning)
        attorney_df.loc[attorney_df["Am Law Ranking"].isna(), "Am Law Ranking"] = attorney_df.loc[attorney_df["Am Law Ranking"].isna(), "Firm ID"].map(amlaw_mapping)
    
    # Check if dataframe is empty
    if attorney_df.empty:
        st.warning(f"No attorney data available for the selected criteria in the selected time period.")
    else:
        # --- Filter UI ---
        # Extract all unique practice areas for filter
        atty_practice_areas = []
        for practice_areas_str in attorney_df["Practice Areas"].dropna():
            areas = practice_areas_str.split(", ")
            atty_practice_areas.extend(areas)
        
        # Convert to a set to get unique values, then sort
        unique_atty_practice_areas = sorted(set(atty_practice_areas))
        unique_atty_practice_areas.insert(0, "All Practice Areas")
        
        # Create filter container
        filter_container = st.container()
        
        with filter_container:
            col1, col2, col3 = st.columns(3)
            
            with col1:
                # Am Law ranking filter
                amlaw_options = ["All Firms", "Am Law 50", "Am Law 100"]
                amlaw_filter = st.selectbox("Filter by Am Law Ranking", amlaw_options, key="atty_amlaw")
            
            with col2:
                # Region filter
                region_options = ["California Only", "Washington Only", "All Regions"]
                region_filter = st.selectbox("Filter by Region", region_options, index=0, key="atty_region")
                
            with col3:
                # Practice area filter
                practice_area_filter = st.selectbox("Filter by Practice Area", unique_atty_practice_areas, key="atty_practice")
        
        # Apply filters to attorney dataframe (using .copy() to avoid SettingWithCopyWarning)
        filtered_attorney_df = attorney_df.copy()
        
        # Apply Am Law filter with proper handling of missing values
        if amlaw_filter == "Am Law 50":
            filtered_attorney_df = filtered_attorney_df[filtered_attorney_df["Am Law Ranking"].notna() & (filtered_attorney_df["Am Law Ranking"] <= 50)]
        elif amlaw_filter == "Am Law 100":
            filtered_attorney_df = filtered_attorney_df[filtered_attorney_df["Am Law Ranking"].notna() & (filtered_attorney_df["Am Law Ranking"] <= 100)]
        
        # Apply Region filter
        if region_filter == "California Only":
            filtered_attorney_df = filtered_attorney_df[filtered_attorney_df["Region"] == "California"]
        elif region_filter == "Washington Only":
