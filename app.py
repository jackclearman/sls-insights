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
        
        st.success(f"✅ Successfully fetched {len(all_jobs)} jobs from API!")
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
        
        st.success(f"✅ Successfully fetched {len(attorneys)} {attorney_type} from API!")
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
        "Move Date": recent.get("date")
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
        "Am Law Ranking": None,  # Placeholder as this data isn't in the job listings
        "Region": region
    }

# --- Main UI Section ---
# Create tabs for the main views
tab_labels = ["Job Listings", "Attorney Placements"]
main_tabs = st.tabs(tab_labels)

# Specific processing for Attorney Placements tab
with main_tabs[0]:  # Attorney Placements tab
    # Time period selector for attorneys
    attorney_time_options = ["Last 1 month", "Last 2 months", "Last 3 months", "Last 6 months"]
    attorney_time_values = [30, 60, 90, 180]
    
    selected_attorney_period = st.selectbox(
        "Select Time Period",
        options=attorney_time_options,
        index=2  # Default to 3 months
    )
    attorney_time_period_days = attorney_time_values[attorney_time_options.index(selected_attorney_period)]
    
    # Attorney type selector
    role_type = st.radio("Select Attorney Type", ["Partners", "Associates"], horizontal=True)
    
    # Load data based on selections
    if role_type == "Partners":
        attorney_data = fetch_attorneys_from_api("partners", attorney_time_period_days)
        attorney_df = pd.DataFrame([extract_attorney(a) for a in attorney_data])
    else:  # Associates
        attorney_data = fetch_attorneys_from_api("associates", attorney_time_period_days)
        attorney_df = pd.DataFrame([extract_attorney(a) for a in attorney_data])
    
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
        
        # Apply filters to attorney dataframe
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
            filtered_attorney_df = filtered_attorney_df[filtered_attorney_df["Region"] == "Washington"]
        
        # Apply Practice Area filter
        if practice_area_filter != "All Practice Areas":
            filtered_attorney_df = filtered_attorney_df[filtered_attorney_df["Practice Areas"].str.contains(practice_area_filter, na=False)]
        
        # Check if filtered dataframe is empty
        if filtered_attorney_df.empty:
            st.warning("No attorney data available with the current filters. Try adjusting your filters.")
        else:
            # --- Attorney data visualization tabs ---
            attorney_tabs = st.tabs(["Top Firms", "Top Cities", "Practice Areas", "Experience"])
            
            # Tab 1: Top Firms
            with attorney_tabs[0]:
                # Add dropdown to select between destination and departure firms
                firm_view = st.selectbox("Select View", ["Top Destination Firms", "Top Departure Firms"], index=0)
                
                if firm_view == "Top Destination Firms":
                    # Get top firms and sort in descending order
                    top_firms = filtered_attorney_df["To Firm"].value_counts().head(10).sort_values(ascending=False)
                    st.subheader(f"Top {len(top_firms)} Destination Firms")
                    
                    # Handle empty dataframe case
                    if len(top_firms) > 0:
                        # Convert Series to DataFrame for plotly
                        plot_df = pd.DataFrame({'Firms': top_firms.index, 'Count': top_firms.values})
                        
                        # Create a bar chart with properly sorted values
                        fig = px.bar(
                            plot_df,
                            x='Firms',
                            y='Count',
                            labels={"Count": "Number of Attorneys", "Firms": ""}
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
                    
                    # Show the detailed attorney moves
                    st.subheader("Attorney Details")
                    columns_order = ["Name", "From Firm", "To Firm", "Practice Areas", "City", "Title", "Move Date"]
                    display_df = filtered_attorney_df[filtered_attorney_df["To Firm"].isin(top_firms.index.tolist())][columns_order] if not top_firms.empty else pd.DataFrame(columns=columns_order)
                    if not display_df.empty:
                        st.dataframe(display_df, hide_index=True)
                    else:
                        st.info("No detailed data available with current filters.")
                else:
                    # Get top departure firms and sort in descending order
                    top_departure_firms = filtered_attorney_df["From Firm"].value_counts().head(10).sort_values(ascending=False)
                    st.subheader(f"Top {len(top_departure_firms)} Departure Firms")
                    
                    # Handle empty dataframe case
                    if len(top_departure_firms) > 0:
                        # Convert Series to DataFrame for plotly
                        plot_df = pd.DataFrame({'Firms': top_departure_firms.index, 'Count': top_departure_firms.values})
                        
                        # Create a bar chart with properly sorted values
                        fig = px.bar(
                            plot_df,
                            x='Firms',
                            y='Count',
                            labels={"Count": "Number of Attorneys", "Firms": ""}
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
                    
                    # Show the detailed attorney moves
                    st.subheader("Attorney Details")
                    columns_order = ["Name", "From Firm", "To Firm", "Practice Areas", "City", "Title", "Move Date"]
                    display_df = filtered_attorney_df[filtered_attorney_df["From Firm"].isin(top_departure_firms.index.tolist())][columns_order] if not top_departure_firms.empty else pd.DataFrame(columns=columns_order)
                    if not display_df.empty:
                        st.dataframe(display_df, hide_index=True)
                    else:
                        st.info("No detailed data available with current filters.")
            
            # Additional tabs implementation for attorneys (simplified for brevity)
            with attorney_tabs[1]:  # Top Cities
                st.write("Top Cities visualization will go here")
                
            with attorney_tabs[2]:  # Practice Areas
                st.write("Practice Areas visualization will go here")
                
            with attorney_tabs[3]:  # Experience
                st.write("Experience visualization will go here")

# Specific processing for Job Listings tab
with main_tabs[1]:  # Job Listings tab
    # Time period selector for jobs
    job_time_options = ["Last 7 days", "Last 14 days", "Last 30 days", "Last 60 days"]
    job_time_values = [7, 14, 30, 60]
    
    selected_job_period = st.selectbox(
        "Select Time Period",
        options=job_time_options,
        index=2  # Default to 30 days
    )
    job_time_period_days = job_time_values[job_time_options.index(selected_job_period)]
    
    # Load job data
    job_data = fetch_jobs_from_api(job_time_period_days)
    job_df = pd.DataFrame([extract_job(j) for j in job_data])
    
    # Check if dataframe is empty
    if job_df.empty:
        st.warning(f"No job data available for the selected criteria in the selected time period.")
    else:
        # --- Filter UI ---
        # Extract all unique practice areas for filter
        job_practice_areas = []
        for practice_areas_str in job_df["Practice Areas"].dropna():
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
        filtered_job_df = job_df.copy()
        
        # Apply Region filter
        if region_filter == "California Only":
            filtered_job_df = filtered_job_df[filtered_job_df["Region"] == "California"]
        elif region_filter == "Washington Only":
            filtered_job_df = filtered_job_df[filtered_job_df["Region"] == "Washington"]
        
        # Apply Practice Area filter
        if practice_area_filter != "All Practice Areas":
            filtered_job_df = filtered_job_df[filtered_job_df["Practice Areas"].str.contains(practice_area_filter, na=False)]
        
        # Check if filtered dataframe is empty
        if filtered_job_df.empty:
            st.warning("No job data available with the current filters. Try adjusting your filters.")
        else:
            # --- Job data visualization tabs ---
            job_tabs = st.tabs(["Top Firms", "Top Cities", "Practice Areas", "Experience"])
            
            # Tab 1: Top Firms
            with job_tabs[0]:
                # Get top firms and sort in descending order
                top_firms = filtered_job_df["Firm"].value_counts().head(10).sort_values(ascending=False)
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
                        labels={"Count": "Number of Job Listings", "Firms": ""}
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
                display_df = filtered_job_df[filtered_job_df["Firm"].isin(top_firms.index.tolist())][columns_order] if not top_firms.empty else pd.DataFrame(columns=columns_order)
                if not display_df.empty:
                    st.dataframe(display_df, hide_index=True)
                else:
                    st.info("No detailed data available with current filters.")
            
            # Additional tabs implementation for jobs (simplified for brevity)
            with job_tabs[1]:  # Top Cities
                st.write("Top Cities visualization will go here")
                
            with job_tabs[2]:  # Practice Areas
                st.write("Practice Areas visualization will go here")
                
            with job_tabs[3]:  # Experience
                st.write("Experience visualization will go here")
