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
        "titles": ["Associate"]
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
        "titles": ["Partners"]
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

# --- UI Layout ---
# This is a completely new approach to avoid circular references
tabs = ["Attorney Placements", "Job Listings"]
view_type = st.radio("Select View", tabs, horizontal=True)

# Define the time period options OUTSIDE of any conditional logic
job_time_options = ["Last 7 days", "Last 14 days", "Last 30 days", "Last 60 days"]
job_time_values = [7, 14, 30, 60]
job_time_default = 2  # Index for 30 days

attorney_time_options = ["Last 1 month", "Last 2 months", "Last 3 months", "Last 6 months"]
attorney_time_values = [30, 60, 90, 180]
attorney_time_default = 2  # Index for 3 months

# Choose which time options to show based on the selected view
if view_type == tabs[0]:  # Attorney Placements
    selected_index = st.selectbox("Select Time Period", attorney_time_options, index=attorney_time_default)
    time_period_days = attorney_time_values[attorney_time_options.index(selected_index)]
    
    # Load attorney data
    role_type = st.radio("Select Attorney Type", ["Partners", "Associates"], horizontal=True)
    
    if role_type == "Partners":
        data = fetch_attorneys_from_api("partners", time_period_days)
        df = pd.DataFrame([extract_attorney(a) for a in data])
    else:
        data = fetch_attorneys_from_api("associates", time_period_days)
        df = pd.DataFrame([extract_attorney(a) for a in data])
else:  # Job Listings
    selected_index = st.selectbox("Select Time Period", job_time_options, index=job_time_default)
    time_period_days = job_time_values[job_time_options.index(selected_index)]
    
    # Load job data
    data = fetch_jobs_from_api(time_period_days)
    df = pd.DataFrame([extract_job(j) for j in data])

# Check if dataframe is empty
if df.empty:
    st.warning(f"No data available for the selected criteria in the selected time period.")
    st.stop()

# --- Extract all unique practice areas for filter ---
# First create a list of all practice areas
all_practice_areas = []
for practice_areas_str in df["Practice Areas"].dropna():
    practice_areas = practice_areas_str.split(", ")
    all_practice_areas.extend(practice_areas)

# Convert to a set to get unique values, then sort and add "All Practice Areas" option
unique_practice_areas = sorted(set(all_practice_areas))
unique_practice_areas.insert(0, "All Practice Areas")

# --- Create Filter Container ---
filter_container = st.container()

with filter_container:
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Am Law ranking filter
        amlaw_options = ["All Firms", "Am Law 50", "Am Law 100"]
        amlaw_filter = st.selectbox("Filter by Am Law Ranking", amlaw_options)
    
    with col2:
        # Region filter
        region_options = ["California Only", "Washington Only", "All Regions"]
        region_filter = st.selectbox("Filter by Region", region_options, index=0)
        
    with col3:
        # Practice area filter
        practice_area_filter = st.selectbox("Filter by Practice Area", unique_practice_areas)

# --- Apply Filters Function ---
def apply_filters(dataframe):
    filtered_df = dataframe.copy()
    
    # Apply Am Law filter with proper handling of missing values
    if amlaw_filter == "Am Law 50":
        # Only include rows where Am Law Ranking is not null and <= 50
        filtered_df = filtered_df[filtered_df["Am Law Ranking"].notna() & (filtered_df["Am Law Ranking"] <= 50)]
    elif amlaw_filter == "Am Law 100":
        # Only include rows where Am Law Ranking is not null and <= 100
        filtered_df = filtered_df[filtered_df["Am Law Ranking"].notna() & (filtered_df["Am Law Ranking"] <= 100)]
    
    # Apply Region filter
    if region_filter == "California Only":
        filtered_df = filtered_df[filtered_df["Region"] == "California"]
    elif region_filter == "Washington Only":
        filtered_df = filtered_df[filtered_df["Region"] == "Washington"]
    
    # Apply Practice Area filter
    if practice_area_filter != "All Practice Areas":
        # Filter rows where the practice area string contains the selected practice area
        filtered_df = filtered_df[filtered_df["Practice Areas"].str.contains(practice_area_filter, na=False)]
    
    return filtered_df

# Apply filters to dataframe
filtered_df = apply_filters(df)

# Check if filtered dataframe is empty
if filtered_df.empty:
    st.warning("No data available with the current filters. Try adjusting your filters.")
    st.stop()

# --- Tabs ---
tab1, tab2, tab3, tab4 = st.tabs(["Top Firms", "Top Cities", "Practice Areas", "Experience"])

# Adjust column names and analysis based on view type
if view_type == "Attorney Placements":
    with tab1:
        # Add dropdown to select between destination and departure firms
        firm_view = st.selectbox("Select View", ["Top Destination Firms", "Top Departure Firms"], index=0)
        
        if firm_view == "Top Destination Firms":
            # Get top firms and sort in descending order
            top_firms = filtered_df["To Firm"].value_counts().head(10).sort_values(ascending=False)
            st.subheader(f"Top {len(top_firms)} Destination Firms")
            
            # Handle empty dataframe case
            if len(top_firms) > 0:
                # Convert Series to DataFrame for plotly
                plot_df = pd.DataFrame({'Firms': top_firms.index, 'Count': top_firms.values})
                
                # Create a bar chart with properly sorted values
                fig = px.bar(
                    plot_df,
                x='Year',
                y='Count',
                labels={"Count": "Number of Attorneys", "Year": "Graduation Year"}
            )
            
            # Customize layout - note: we keep chronological order for years
            fig.update_layout(
                margin=dict(t=10, b=10, l=10, r=10),
                xaxis_fixedrange=True,
                yaxis_fixedrange=True
            )
            
            # Render chart with container width responsiveness but disabled toolbar
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        else:
            st.info("No data available with current filters.")
        
        # Show attorneys with graduation years with reordered columns
        columns_order = ["Name", "From Firm", "To Firm", "Practice Areas", "Specialties", "City", "Graduation Year", "Law School", "Current Firm", "Title", "Move Date", "FirmProspects ID", "Profile Link"]
        display_df = filtered_df[filtered_df["Graduation Year"].notna()][columns_order]
        if not display_df.empty:
            st.dataframe(display_df, hide_index=True)
        else:
            st.info("No detailed data available with current filters.")
else:  # Job Listings view
    with tab1:
        # Get top firms and sort in descending order
        top_firms = filtered_df["Firm"].value_counts().head(10).sort_values(ascending=False)
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
        
        # Create a summary table for top 10 hiring firms
        st.subheader("Top 10 Hiring Firms - Detailed Analysis")
        top_20_firms = filtered_df["Firm"].value_counts().head(10).sort_values(ascending=False).index.tolist()
        
        # Create a firm summary dataframe
        firm_summaries = []
        for firm in top_20_firms:
            firm_data = filtered_df[filtered_df["Firm"] == firm]
            practice_areas_df = firm_data.assign(Practice_Area=firm_data["Practice Areas"].str.split(", ")).explode("Practice_Area")
            top_practice_areas = practice_areas_df["Practice_Area"].value_counts().head(3).index.tolist() if not practice_areas_df.empty else []
            
            # Get top job types
            top_job_types = firm_data["Job Type"].value_counts().head(2).index.tolist() if not firm_data["Job Type"].empty else []
            
            summary = {
                "Firm": firm,
                "Total Openings": len(firm_data),
                "Top Practice Areas Hiring": ", ".join(top_practice_areas) if top_practice_areas else "N/A",
                "Most Common Job Types": ", ".join(top_job_types) if top_job_types else "N/A",
                "Cities": ", ".join(firm_data["City"].unique()) if not firm_data["City"].empty else "N/A",
            }
            firm_summaries.append(summary)
        
        if firm_summaries:
            firm_summary_df = pd.DataFrame(firm_summaries)
            st.dataframe(firm_summary_df, hide_index=True)
        else:
            st.info("No summary data available with current filters.")
        
        # Show the detailed job listings for reference
        st.subheader("Job Details (From Top 10 Firms Above)")
        columns_order = ["Job Title", "Firm", "Practice Areas", "Specialties", "City", "Experience Range", "Job Type", "Job Status", "Posted Date", "FirmProspects ID", "Profile Link"]
        display_df = filtered_df[filtered_df["Firm"].isin(top_firms.index.tolist())][columns_order] if not top_firms.empty else pd.DataFrame(columns=columns_order)
        if not display_df.empty:
            st.dataframe(display_df, hide_index=True)
        else:
            st.info("No detailed data available with current filters.")
    
    with tab2:
        # Get top cities and sort in descending order
        top_cities = filtered_df["City"].value_counts().head(10).sort_values(ascending=False)
        st.subheader(f"Top {len(top_cities)} Cities for Job Listings")
        
        # Handle empty dataframe case
        if len(top_cities) > 0:
            # Convert Series to DataFrame for plotly
            plot_df = pd.DataFrame({'Cities': top_cities.index, 'Count': top_cities.values})
            
            # Create a bar chart with properly sorted values
            fig = px.bar(
                plot_df,
                x='Cities',
                y='Count',
                labels={"Count": "Number of Job Listings", "Cities": ""}
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
        
        # Show jobs in top cities with reordered columns
        columns_order = ["Job Title", "Firm", "Practice Areas", "Specialties", "City", "Experience Range", "Job Type", "Job Status", "Posted Date", "FirmProspects ID", "Profile Link"]
        display_df = filtered_df[filtered_df["City"].isin(top_cities.index.tolist())][columns_order] if not top_cities.empty else pd.DataFrame(columns=columns_order)
        if not display_df.empty:
            st.dataframe(display_df, hide_index=True)
        else:
            st.info("No detailed data available with current filters.")
    
    with tab3:
        # Get top practice areas and sort in descending order
        exploded = filtered_df.assign(Practice_Area=filtered_df["Practice Areas"].str.split(", ")).explode("Practice_Area")
        top_areas = exploded["Practice_Area"].value_counts().head(10).sort_values(ascending=False)
        st.subheader(f"Top {len(top_areas)} Practice Areas")
        
        # Handle empty dataframe case
        if len(top_areas) > 0:
            # Convert Series to DataFrame for plotly
            plot_df = pd.DataFrame({'Areas': top_areas.index, 'Count': top_areas.values})
            
            # Create a bar chart with properly sorted values
            fig = px.bar(
                plot_df,
                x='Areas',
                y='Count',
                labels={"Count": "Number of Job Listings", "Areas": ""}
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
        
        # Show jobs in top practice areas with reordered columns
        columns_order = ["Job Title", "Firm", "Practice Areas", "Specialties", "City", "Experience Range", "Job Type", "Job Status", "Posted Date", "FirmProspects ID", "Profile Link"]
        display_df = exploded[exploded["Practice_Area"].isin(top_areas.index.tolist())][columns_order] if not top_areas.empty else pd.DataFrame(columns=columns_order)
        if not display_df.empty:
            st.dataframe(display_df, hide_index=True)
        else:
            st.info("No detailed data available with current filters.")
    
    with tab4:
        # For jobs, show experience ranges instead of graduation years
        # Extract min and max years from experience range
        experience_counts = {}
        for exp_range in filtered_df["Experience Range"].dropna():
            if "-" in exp_range:
                min_exp, max_exp = exp_range.split("-")
                min_exp = min_exp.strip()
                max_exp = max_exp.strip().split(" ")[0]  # Remove " years" part
                range_name = f"{min_exp}-{max_exp} years"
            else:
                range_name = exp_range.strip()
            
            if range_name in experience_counts:
                experience_counts[range_name] += 1
            else:
                experience_counts[range_name] = 1
        
        # Sort by experience level
        sorted_exp = sorted(experience_counts.items(), key=lambda x: int(x[0].split(" ")[0].split("-")[0]))
        exp_series = pd.Series({k: v for k, v in sorted_exp})
        
        st.subheader("Experience Requirements Distribution")
        
        # Handle empty dataframe case
        if len(exp_series) > 0:
            # Convert Series to DataFrame for plotly
            plot_df = pd.DataFrame({'Experience': exp_series.index, 'Count': exp_series.values})
            
            # Create a bar chart for experience ranges
            fig = px.bar(
                plot_df,
                x='Experience',
                y='Count',
                labels={"Count": "Number of Job Listings", "Experience": "Experience Required"}
            )
            
            # Customize layout
            fig.update_layout(
                margin=dict(t=10, b=10, l=10, r=10),
                xaxis_fixedrange=True,
                yaxis_fixedrange=True
            )
            
            # Render chart with container width responsiveness but disabled toolbar
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        else:
            st.info("No data available with current filters.")
        
        # Show jobs by experience range with reordered columns
        columns_order = ["Job Title", "Firm", "Practice Areas", "Specialties", "City", "Experience Range", "Job Type", "Job Status", "Posted Date", "FirmProspects ID", "Profile Link"]
        display_df = filtered_df[filtered_df["Experience Range"].notna()][columns_order]
        if not display_df.empty:
            st.dataframe(display_df, hide_index=True)
        else:
            st.info("No detailed data available with current filters.")
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
            
            # Create a summary table for top 10 destination firms
            st.subheader("Top 10 Destination Firms - Detailed Analysis")
            top_20_firms = filtered_df["To Firm"].value_counts().head(10).sort_values(ascending=False).index.tolist()
            
            # Create a firm summary dataframe
            firm_summaries = []
            for firm in top_20_firms:
                firm_data = filtered_df[filtered_df["To Firm"] == firm]
                practice_areas_df = firm_data.assign(Practice_Area=firm_data["Practice Areas"].str.split(", ")).explode("Practice_Area")
                top_practice_areas = practice_areas_df["Practice_Area"].value_counts().head(3).index.tolist() if not practice_areas_df.empty else []
                
                # Safely calculate average with error handling
                avg_experience = None
                if not firm_data["Graduation Year"].empty and firm_data["Graduation Year"].notna().any():
                    try:
                        avg_experience = 2025 - firm_data["Graduation Year"].mean()
                    except:
                        avg_experience = None
                
                summary = {
                    "Firm": firm,
                    "Total Hires": len(firm_data),
                    "Top Source Firm": firm_data["From Firm"].value_counts().head(1).index.tolist()[0] if not firm_data["From Firm"].empty else "N/A",
                    "Top Practice Areas": ", ".join(top_practice_areas) if top_practice_areas else "N/A",
                    "Average Experience (Years)": avg_experience if avg_experience is not None else "N/A",
                    "Cities": ", ".join(firm_data["City"].unique()) if not firm_data["City"].empty else "N/A",
                    "Top Schools": ", ".join(firm_data["Law School"].value_counts().head(2).index.tolist()) if not firm_data["Law School"].empty else "N/A"
                }
                firm_summaries.append(summary)
            
            if firm_summaries:
                firm_summary_df = pd.DataFrame(firm_summaries)
                st.dataframe(firm_summary_df, hide_index=True)
            else:
                st.info("No summary data available with current filters.")
            
            # Show the detailed attorney moves for reference
            st.subheader("Attorney Details (Moved to Top 10 Firms Above)")
            columns_order = ["Name", "From Firm", "To Firm", "Practice Areas", "Specialties", "City", "Graduation Year", "Law School", "Current Firm", "Title", "Move Date", "FirmProspects ID", "Profile Link"]
            display_df = filtered_df[filtered_df["To Firm"].isin(top_firms.index.tolist())][columns_order] if not top_firms.empty else pd.DataFrame(columns=columns_order)
            if not display_df.empty:
                st.dataframe(display_df, hide_index=True)
            else:
                st.info("No detailed data available with current filters.")
        else:
            # Get top departure firms and sort in descending order
            top_departure_firms = filtered_df["From Firm"].value_counts().head(10).sort_values(ascending=False)
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
            
            # Create a summary table for top 10 departure firms
            st.subheader("Top 10 Departure Firms - Detailed Analysis")
            top_20_departures = filtered_df["From Firm"].value_counts().head(10).sort_values(ascending=False).index.tolist()
            
            # Create a firm summary dataframe
            departure_summaries = []
            for firm in top_20_departures:
                firm_data = filtered_df[filtered_df["From Firm"] == firm]
                practice_areas_df = firm_data.assign(Practice_Area=firm_data["Practice Areas"].str.split(", ")).explode("Practice_Area")
                top_practice_areas = practice_areas_df["Practice_Area"].value_counts().head(3).index.tolist() if not practice_areas_df.empty else []
                
                # Safely calculate average with error handling
                avg_experience = None
                if not firm_data["Graduation Year"].empty and firm_data["Graduation Year"].notna().any():
                    try:
                        avg_experience = 2025 - firm_data["Graduation Year"].mean()
                    except:
                        avg_experience = None
                
                summary = {
                    "Firm": firm,
                    "Total Departures": len(firm_data),
                    "Top Destination Firm": firm_data["To Firm"].value_counts().head(1).index.tolist()[0] if not firm_data["To Firm"].empty else "N/A",
                    "Top Practice Areas Lost": ", ".join(top_practice_areas) if top_practice_areas else "N/A",
                    "Average Experience (Years)": avg_experience if avg_experience is not None else "N/A",
                    "Cities Affected": ", ".join(firm_data["City"].unique()) if not firm_data["City"].empty else "N/A",
                    "Schools of Departing Attorneys": ", ".join(firm_data["Law School"].value_counts().head(2).index.tolist()) if not firm_data["Law School"].empty else "N/A"
                }
                departure_summaries.append(summary)
            
            if departure_summaries:
                departure_summary_df = pd.DataFrame(departure_summaries)
                st.dataframe(departure_summary_df, hide_index=True)
            else:
                st.info("No summary data available with current filters.")
            
            # Show the detailed attorney moves for reference
            st.subheader("Attorney Details (Moved From Top 10 Firms Above)")
            columns_order = ["Name", "From Firm", "To Firm", "Practice Areas", "Specialties", "City", "Graduation Year", "Law School", "Current Firm", "Title", "Move Date", "FirmProspects ID", "Profile Link"]
            display_df = filtered_df[filtered_df["From Firm"].isin(top_departure_firms.index.tolist())][columns_order] if not top_departure_firms.empty else pd.DataFrame(columns=columns_order)
            if not display_df.empty:
                st.dataframe(display_df, hide_index=True)
            else:
                st.info("No detailed data available with current filters.")
    
    with tab2:
        # Get top cities and sort in descending order
        top_cities = filtered_df["City"].value_counts().head(10).sort_values(ascending=False)
        st.subheader(f"Top {len(top_cities)} Cities for Moves")
        
        # Handle empty dataframe case
        if len(top_cities) > 0:
            # Convert Series to DataFrame for plotly
            plot_df = pd.DataFrame({'Cities': top_cities.index, 'Count': top_cities.values})
            
            # Create a bar chart with properly sorted values
            fig = px.bar(
                plot_df,
                x='Cities',
                y='Count',
                labels={"Count": "Number of Attorneys", "Cities": ""}
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
        
        # Show attorneys in top cities with reordered columns
        columns_order = ["Name", "From Firm", "To Firm", "Practice Areas", "Specialties", "City", "Graduation Year", "Law School", "Current Firm", "Title", "Move Date", "FirmProspects ID", "Profile Link"]
        display_df = filtered_df[filtered_df["City"].isin(top_cities.index.tolist())][columns_order] if not top_cities.empty else pd.DataFrame(columns=columns_order)
        if not display_df.empty:
            st.dataframe(display_df, hide_index=True)
        else:
            st.info("No detailed data available with current filters.")
    
    with tab3:
        # Get top practice areas and sort in descending order
        exploded = filtered_df.assign(Practice_Area=filtered_df["Practice Areas"].str.split(", ")).explode("Practice_Area")
        top_areas = exploded["Practice_Area"].value_counts().head(10).sort_values(ascending=False)
        st.subheader(f"Top {len(top_areas)} Practice Areas")
        
        # Handle empty dataframe case
        if len(top_areas) > 0:
            # Convert Series to DataFrame for plotly
            plot_df = pd.DataFrame({'Areas': top_areas.index, 'Count': top_areas.values})
            
            # Create a bar chart with properly sorted values
            fig = px.bar(
                plot_df,
                x='Areas',
                y='Count',
                labels={"Count": "Number of Attorneys", "Areas": ""}
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
        
        # Show attorneys in top practice areas with reordered columns
        columns_order = ["Name", "From Firm", "To Firm", "Practice Areas", "Specialties", "City", "Graduation Year", "Law School", "Current Firm", "Title", "Move Date", "FirmProspects ID", "Profile Link"]
        display_df = exploded[exploded["Practice_Area"].isin(top_areas.index.tolist())][columns_order] if not top_areas.empty else pd.DataFrame(columns=columns_order)
        if not display_df.empty:
            st.dataframe(display_df, hide_index=True)
        else:
            st.info("No detailed data available with current filters.")
    
    with tab4:
        # Get graduation year distribution
        grad_years_series = filtered_df["Graduation Year"].dropna().value_counts().sort_index()
        st.subheader("Graduation Year Distribution")
        
        # Handle empty dataframe case
        if len(grad_years_series) > 0:
            # Convert Series to DataFrame for plotly
            plot_df = pd.DataFrame({'Year': grad_years_series.index.astype(str), 'Count': grad_years_series.values})
            
            # Create a bar chart for graduation years
            fig = px.bar(
                plot_df,
