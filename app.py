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
            
            # Additional tabs implementation for attorneys (simplified for brevity
            ATTORNEY_COLOR = '#636EFA'  # Plotly's default blue
            
 
            # Tab 2: Top Cities
            with attorney_tabs[1]:  # Top Cities
                st.subheader("Top Cities for Attorney Movements")
                
                # Get the top cities with attorney movements
                top_cities = filtered_attorney_df["City"].value_counts().head(10).sort_values(ascending=False)
                
                if len(top_cities) > 0:
                    # Convert Series to DataFrame for plotting
                    city_df = pd.DataFrame({"Cities": top_cities.index, "Count": top_cities.values})
                    
                    # Create a bar chart (same style as Top Firms)
                    fig = px.bar(
                        city_df,
                        x="Cities",
                        y="Count",
                        labels={"Count": "Number of Attorneys", "Cities": ""},
                        color_discrete_sequence=[ATTORNEY_COLOR]  # Use consistent color
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
                    
                    # Show table of attorneys by city
                    st.subheader("Attorney Details by City")
                    city_columns = ["Name", "From Firm", "To Firm", "Practice Areas", "City", "Move Date"]
                    city_df_details = filtered_attorney_df[filtered_attorney_df["City"].isin(top_cities.index.tolist())][city_columns]
                    if not city_df_details.empty:
                        st.dataframe(city_df_details, hide_index=True)
                else:
                    st.info("No city data available with current filters.")
            
            # Tab 3: Practice Areas
            with attorney_tabs[2]:  # Practice Areas
                st.subheader("Top Practice Areas")
                
                # Process practice areas (they're comma-separated in the dataframe)
                all_areas = []
                for areas in filtered_attorney_df["Practice Areas"].dropna():
                    all_areas.extend([area.strip() for area in areas.split(",")])
                
                # Count occurrences and get top practice areas
                practice_counts = pd.Series(all_areas).value_counts().head(10)
                
                if len(practice_counts) > 0:
                    # Convert to DataFrame for plotting
                    practice_df = pd.DataFrame({"Practice Area": practice_counts.index, "Count": practice_counts.values})
                    
                    # Create bar chart instead of pie chart to match Top Firms style
                    fig = px.bar(
                        practice_df,
                        x="Practice Area",
                        y="Count",
                        labels={"Count": "Number of Attorneys", "Practice Area": ""},
                        color_discrete_sequence=[ATTORNEY_COLOR]  # Use consistent color
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
                    st.subheader("Practice Area Distribution")
                    st.dataframe(practice_df, hide_index=True)
                else:
                    st.info("No practice area data available with current filters.")
            
            # Tab 4: Experience
            with attorney_tabs[3]:  # Experience
                st.subheader("Attorney Experience Distribution")
                
                # Calculate years since graduation to estimate experience level
                current_year = datetime.now().year
                
                # Clean and convert graduation year to numeric
                filtered_attorney_df["Graduation Year"] = pd.to_numeric(filtered_attorney_df["Graduation Year"], errors="coerce")
                
                # Calculate experience for attorneys with valid graduation years
                valid_exp_df = filtered_attorney_df.dropna(subset=["Graduation Year"])
                valid_exp_df["Experience"] = current_year - valid_exp_df["Graduation Year"]
                
                if not valid_exp_df.empty:
                    # Create experience bins
                    bins = [0, 3, 5, 8, 10, 15, 20, 50]
                    labels = ["0-3 years", "3-5 years", "5-8 years", "8-10 years", "10-15 years", "15-20 years", "20+ years"]
                    
                    valid_exp_df["Experience Bracket"] = pd.cut(valid_exp_df["Experience"], bins=bins, labels=labels, right=False)
                    
                    # Count attorneys in each experience bracket
                    exp_counts = valid_exp_df["Experience Bracket"].value_counts().sort_index()
                    
                    # Create DataFrame for plotting
                    exp_df = pd.DataFrame({"Experience": exp_counts.index, "Count": exp_counts.values})
                    
                    # Create a bar chart to match style
                    fig = px.bar(
                        exp_df,
                        x="Experience",
                        y="Count",
                        labels={"Count": "Number of Attorneys", "Experience": "Years of Experience"},
                        color_discrete_sequence=[ATTORNEY_COLOR]  # Use consistent color
                    )
                    
                    # Update layout to match Top Firms
                    fig.update_layout(
                        margin=dict(t=10, b=10, l=10, r=10),
                        xaxis_fixedrange=True,
                        yaxis_fixedrange=True
                    )
                    
                    # Render chart
                    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
                    
                    # Show table with attorney details by experience
                    st.subheader("Attorney Details by Experience")
                    exp_columns = ["Name", "From Firm", "To Firm", "Practice Areas", "Graduation Year", "Experience", "Experience Bracket"]
                    exp_df_details = valid_exp_df[exp_columns].sort_values("Experience", ascending=False)
                    if not exp_df_details.empty:
                        st.dataframe(exp_df_details, hide_index=True)
                else:
                    st.info("No experience data available with current filters.")



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
            JOB_COLOR = '#636EFA'  # Plotly's default blue - same as attorney tabs for consistency
            
            # Tab 1: Top Firms (Already implemented with default styling)
            
            # Tab 2: Top Cities
            with job_tabs[1]:  # Top Cities
                st.subheader("Top Cities for Job Listings")
                
                # Get top cities with job postings
                job_top_cities = filtered_job_df["City"].value_counts().head(10).sort_values(ascending=False)
                
                if len(job_top_cities) > 0:
                    # Convert Series to DataFrame for plotting
                    job_city_df = pd.DataFrame({"Cities": job_top_cities.index, "Count": job_top_cities.values})
                    
                    # Create bar chart (same style as Top Firms)
                    fig = px.bar(
                        job_city_df,
                        x="Cities",
                        y="Count",
                        labels={"Count": "Number of Jobs", "Cities": ""},
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
                    job_city_df_details = filtered_job_df[filtered_job_df["City"].isin(job_top_cities.index.tolist())][job_city_columns]
                    if not job_city_df_details.empty:
                        st.dataframe(job_city_df_details, hide_index=True)
                else:
                    st.info("No city data available with current filters.")
            
            # Tab 3: Practice Areas
            with job_tabs[2]:  # Practice Areas
                st.subheader("Top Practice Areas in Job Listings")
                
                # Process practice areas (they're comma-separated in the dataframe)
                job_all_areas = []
                for areas in filtered_job_df["Practice Areas"].dropna():
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
                        labels={"Count": "Number of Jobs", "Practice Area": ""},
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
                    st.subheader("Practice Area Distribution in Job Listings")
                    st.dataframe(job_practice_df, hide_index=True)
                else:
                    st.info("No practice area data available with current filters.")
            
            # Tab 4: Experience
            with job_tabs[3]:  # Experience
                st.subheader("Job Listings by Experience Level")
                
                # Create a new column for min years of experience (for sorting)
                filtered_job_df["Min Experience"] = filtered_job_df["Experience Range"].str.extract(r'(\d+)').astype(float)
                
                # Group by experience range
                if "Experience Range" in filtered_job_df.columns and not filtered_job_df.empty:
                    exp_job_counts = filtered_job_df["Experience Range"].value_counts().sort_index()
                    
                    # Create DataFrame for plotting
                    exp_job_df = pd.DataFrame({"Experience Required": exp_job_counts.index, "Number of Jobs": exp_job_counts.values})
                    
                    # Sort the DataFrame by min experience
                    exp_job_df["Min Years"] = exp_job_df["Experience Required"].str.extract(r'(\d+)').astype(float)
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
                    job_exp_df_details = filtered_job_df.sort_values("Min Experience")[job_exp_columns]
                    if not job_exp_df_details.empty:
                        st.dataframe(job_exp_df_details, hide_index=True)
                else:
                    st.info("No experience data available with current filters.")
