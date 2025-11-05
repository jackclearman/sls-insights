import streamlit as st
from dashboard_insights import dashboard_insights
from sf_queries import get_candidates_for_recruiter, get_opportunities_for_candidate, generate_candidate_password
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

def dashboard_recruiter(owner_id):
    # Navigation buttons with fixed width container
    if "current_page" not in st.session_state:
        st.session_state.current_page = "insights"
    
    # Use a container with fixed button styling
    with st.container():
        col1, col2, col3, col4 = st.columns([2, 2, 2, 6])
        
        with col1:
            if st.button("📊 Insights", 
                         key="insights_btn",
                         type="primary" if st.session_state.current_page == "insights" else "secondary"):
                st.session_state.current_page = "insights"
                st.rerun()
        
        with col2:
            if st.button("👥 Opportunities",
                         key="opportunities_btn", 
                         type="primary" if st.session_state.current_page == "opportunities" else "secondary"):
                st.session_state.current_page = "opportunities"
                st.rerun()
        
        with col3:
            if st.button("📄 Monthly Report",
                         key="report_btn", 
                         type="primary" if st.session_state.current_page == "monthly_report" else "secondary"):
                st.session_state.current_page = "monthly_report"
                st.rerun()
    
    st.markdown("---")
    
    # Show content based on selected page
    if st.session_state.current_page == "insights":
        dashboard_insights()
    elif st.session_state.current_page == "monthly_report":
        monthly_report_dashboard()
    else:  # opportunities
        st.header("Your Active Candidates")
        candidates = get_candidates_for_recruiter(owner_id)
        if not candidates:
            st.info("No active candidates.")
            return
        # Dropdown of all candidate names
        candidate_names = [c["Name"] for c in candidates]
        selected_name = st.selectbox("Select Candidate", candidate_names) if candidate_names else None
        selected_candidate = next((c for c in candidates if c["Name"] == selected_name), None)
        if selected_candidate:
            st.subheader(f"Opportunities for {selected_candidate['Name']}")
            
            # Candidate Portal Link and Password
            candidate_portal_url = f"{st.secrets.get('APP_URL', 'https://silver-space-tribble-wvwq6q4v9qjfg44w-8501.app.github.dev')}?token={selected_candidate['Id']}"
            candidate_password = generate_candidate_password(selected_candidate['Name'])
            
            st.info(f"**Candidate Portal Link:** {candidate_portal_url}")
            st.info(f"**Candidate Password:** `{candidate_password}`")
            st.caption("Share both the link and password with the candidate to access their portal.")
            
            opps = get_opportunities_for_candidate(selected_candidate["Id"])
            # Get instance_url from the Salesforce token in session
            instance_url = None
            token = st.session_state.get("salesforce_token", {})
            if isinstance(token, dict):
                instance_url = token.get("instance_url")
            if not opps:
                st.write("No opportunities found.")
            else:
                def opp_salesforce_url(opp):
                    if instance_url and opp.get("Id"):
                        return f"{instance_url}/lightning/r/Opportunity/{opp['Id']}/view"
                    return ""
                
                # Display opportunities table
                st.table([
                    {
                        "Name": o.get("Name", ""),
                        "Account Name": o.get("Account_Name__c", ""),
                        "Stage": o.get("StageName", ""),
                        "Status": o.get("Status__c", ""),
                        "Open Job": o.get("Open_Job__r", {}).get("Name", "") if o.get("Open_Job__r") else "",
                        "Salesforce URL": opp_salesforce_url(o)
                    }
                    for o in opps
                ])
                
                # Notes section for each opportunity
                st.markdown("---")
                st.subheader("Opportunity Notes")
                
                # Create tabs for each opportunity
                if len(opps) == 1:
                    # If only one opportunity, don't use tabs
                    opp = opps[0]
                    opp_id = opp.get("Id", "")
                    opp_name = opp.get("Name", "Unnamed Opportunity")
                    
                    st.write(f"**Notes for:** {opp_name}")
                    
                    # Initialize notes storage if not exists
                    if "opportunity_notes" not in st.session_state:
                        st.session_state.opportunity_notes = {}
                    
                    # Get existing note or empty string
                    current_note = st.session_state.opportunity_notes.get(opp_id, "")
                    
                    # Text area for notes
                    note = st.text_area(
                        "Add your notes about this opportunity:",
                        value=current_note,
                        height=150,
                        key=f"note_{opp_id}",
                        help="Notes are saved automatically as you type and persist during your session."
                    )
                    
                    # Save note to session state
                    st.session_state.opportunity_notes[opp_id] = note
                    
                    if note.strip():
                        st.success(f"Note saved for {opp_name}")
                        
                else:
                    # Multiple opportunities - use tabs
                    tab_names = [f"{o.get('Name', 'Opportunity')} ({o.get('StageName', 'No Stage')})" for o in opps]
                    tabs = st.tabs(tab_names)
                    
                    for i, (tab, opp) in enumerate(zip(tabs, opps)):
                        with tab:
                            opp_id = opp.get("Id", "")
                            opp_name = opp.get("Name", "Unnamed Opportunity")
                            
                            # Initialize notes storage if not exists
                            if "opportunity_notes" not in st.session_state:
                                st.session_state.opportunity_notes = {}
                            
                            # Get existing note or empty string
                            current_note = st.session_state.opportunity_notes.get(opp_id, "")
                            
                            # Display opportunity details
                            col1, col2 = st.columns(2)
                            with col1:
                                st.metric("Company", opp.get("Account_Name__c", "N/A"))
                                st.metric("Stage", opp.get("StageName", "N/A"))
                            with col2:
                                st.metric("Status", opp.get("Status__c", "N/A"))
                                st.metric("Open Job", opp.get("Open_Job__r", {}).get("Name", "N/A") if opp.get("Open_Job__r") else "N/A")
                                if opp_salesforce_url(opp):
                                    st.markdown(f"[View in Salesforce]({opp_salesforce_url(opp)})")
                            
                            # Text area for notes
                            note = st.text_area(
                                "Add your notes about this opportunity:",
                                value=current_note,
                                height=150,
                                key=f"note_{opp_id}_{i}",  # Include index to ensure uniqueness
                                help="Notes are saved automatically as you type and persist during your session."
                            )
                            
                            # Save note to session state
                            st.session_state.opportunity_notes[opp_id] = note
                            
                            if note.strip():
                                st.success(f"Note saved for {opp_name}")

def monthly_report_dashboard():
    # ...existing code...
    # (Move debug output below after atty_df is defined)
    """Monthly Report Dashboard - Last 30 Days Summary"""
    
    # Import necessary functions from dashboard_insights
    from dashboard_insights import (
        fetch_jobs_from_api, fetch_attorneys_from_api, 
        extract_job, extract_attorney, load_amlaw_data
    )
    
    st.header("📄 Monthly Report - Last 30 Days")
    
    # Attorney/Job Type Toggle
    report_type = st.radio(
        "Select Report Type", 
        ["Associates", "Partners"], 
        horizontal=True,
        key="monthly_report_type"
    )
    
    # Fetch data for last 30 days
    with st.spinner("Loading monthly data..."):
        # Get jobs data
        if "monthly_jobs_raw" not in st.session_state:
            st.session_state["monthly_jobs_raw"] = fetch_jobs_from_api(30)
        
        # Get attorneys data
        atty_key = "associates" if report_type == "Associates" else "partners"
        if "monthly_atty_raw" not in st.session_state or st.session_state.get("monthly_atty_type") != atty_key:
            st.session_state["monthly_atty_raw"] = fetch_attorneys_from_api(atty_key, 30)
            st.session_state["monthly_atty_type"] = atty_key
    
    # Process data
    job_df = pd.DataFrame([extract_job(j) for j in st.session_state["monthly_jobs_raw"]])
    atty_df = pd.DataFrame([extract_attorney(a) for a in st.session_state["monthly_atty_raw"]])

    # DEBUG: Show available columns and a sample row for troubleshooting
    if not atty_df.empty:
        st.expander("[Debug] Attorney DataFrame Columns & Sample").write({
            "columns": list(atty_df.columns),
            "sample_row": atty_df.iloc[0].to_dict() if len(atty_df) > 0 else {}
        })
    
    # Add Am Law rankings
    amlaw_df = load_amlaw_data()
    if not job_df.empty and not amlaw_df.empty:
        job_df["Firm ID"] = pd.to_numeric(job_df["Firm ID"], errors="coerce")
        mapping = dict(zip(amlaw_df["FP ID - Firm"], amlaw_df["AmLaw Rank"]))
        job_df["Am Law Ranking"] = job_df["Firm ID"].map(mapping).astype("Int64")
    
    if not atty_df.empty and not amlaw_df.empty:
        atty_df["Firm ID"] = pd.to_numeric(atty_df["Firm ID"], errors="coerce")
        mapping = dict(zip(amlaw_df["FP ID - Firm"], amlaw_df["AmLaw Rank"]))
        atty_df["Am Law Ranking"] = atty_df["Firm ID"].map(mapping).astype("Int64")
    
    # Filter by job/attorney type
    if not job_df.empty:
        if report_type == "Associates":
            job_df = job_df[job_df["Job Type"].str.contains("Associate", na=False, case=False)]
        else:
            job_df = job_df[job_df["Job Type"].str.contains("Partner", na=False, case=False)]
        
        # Remove duplicate job names
        job_df = job_df.drop_duplicates(subset=["Job Title", "Firm"], keep="first")
    
    # Generate Email Report Text
    email_report = generate_email_report_text(job_df, atty_df, report_type)
    
    # Display the email-formatted report
    st.subheader("📧 Email Report Format")
    st.text_area(
        "Copy this text for your email:",
        value=email_report,
        height=600,
        help="This report is formatted for easy copy-paste into emails"
    )
    

    # Add a copy button (visual indicator)
    st.info("💡 **Tip**: Select all text above (Ctrl+A) and copy (Ctrl+C) to paste into your email")

    # --- Lateral Movements Table (Placements Table Style) ---
    st.markdown("---")
    st.subheader("All Lateral Movements (Last 30 Days)")
    if atty_df.empty:
        st.info("No lateral movements in the last 30 days.")
    else:
        # Use the same columns as the placements table in insights, with id and last_move_date
        # Define the expected columns and their display names
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
        # Build the DataFrame with all expected columns, filling missing ones with empty string
        data = {}
        for col, _ in expected_cols:
            if col in atty_df.columns:
                data[col] = atty_df[col]
            else:
                data[col] = ["" for _ in range(len(atty_df))]
        display_df = pd.DataFrame(data)
        # Rename columns for display
        display_df.columns = [disp for _, disp in expected_cols]
        st.dataframe(display_df.head(2000), use_container_width=True)

def generate_email_report_text(job_df, atty_df, report_type):
    """Generate a text-based monthly report for email."""
    lines = []
    lines.append(f"MONTHLY REPORT – {report_type.upper()} (Last 30 Days)")
    lines.append("")
    lines.append("PLACEMENTS:")
    if atty_df.empty:
        lines.append("  No placements in the last 30 days.")
    else:
        # Top 10 destination firms
        top_firms = atty_df["To Firm"].value_counts().head(10)
        lines.append("  Top 10 Destination Firms:")
        for i, (firm, count) in enumerate(top_firms.items(), 1):
            lines.append(f"    {i}. {firm} ({count})")
        lines.append("")
        # Top 5 practice areas
        areas = [a.strip() for s in atty_df["Practice Areas"].dropna() for a in s.split(",") if a.strip()]
        top_areas = pd.Series(areas).value_counts().head(5)
        lines.append("  Top 5 Practice Areas:")
        for i, (area, count) in enumerate(top_areas.items(), 1):
            lines.append(f"    {i}. {area} ({count})")
        lines.append("")
        # Top 5 specialties (subcategory)
        specialties = [a.strip() for s in atty_df["Specialties"].dropna() for a in s.split(",") if a.strip()]
        top_specialties = pd.Series(specialties).value_counts().head(5)
        lines.append("  Top 5 Specialties:")
        for i, (spec, count) in enumerate(top_specialties.items(), 1):
            lines.append(f"    {i}. {spec} ({count})")
        lines.append("")
        # Top 5 cities
        top_cities = atty_df["City"].value_counts().head(5)
        lines.append("  Top 5 Cities:")
        for i, (city, count) in enumerate(top_cities.items(), 1):
            lines.append(f"    {i}. {city} ({count})")
        lines.append("")
        # Top 5 JD Year (rounded, no decimals)
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
        # Top 10 hiring firms
        top_hiring_firms = job_df["Firm"].value_counts().head(10)
        lines.append("  Top 10 Hiring Firms:")
        for i, (firm, count) in enumerate(top_hiring_firms.items(), 1):
            lines.append(f"    {i}. {firm} ({count})")
        lines.append("")
        # Top 5 practice areas
        areas = [a.strip() for s in job_df["Practice Areas"].dropna() for a in s.split(",") if a.strip()]
        top_areas = pd.Series(areas).value_counts().head(5)
        lines.append("  Top 5 Practice Areas:")
        for i, (area, count) in enumerate(top_areas.items(), 1):
            lines.append(f"    {i}. {area} ({count})")
        lines.append("")
        # Top 5 specialties (subcategory)
        specialties = [a.strip() for s in job_df["Specialties"].dropna() for a in s.split(",") if a.strip()]
        top_specialties = pd.Series(specialties).value_counts().head(5)
        lines.append("  Top 5 Specialties:")
        for i, (spec, count) in enumerate(top_specialties.items(), 1):
            lines.append(f"    {i}. {spec} ({count})")
        lines.append("")
        # Top 5 cities
        top_cities = job_df["City"].value_counts().head(5)
        lines.append("  Top 5 Cities:")
        for i, (city, count) in enumerate(top_cities.items(), 1):
            lines.append(f"    {i}. {city} ({count})")
        lines.append("")
        # Top 5 experience requirements (if available, skip blank)
        if "Experience Range" in job_df.columns:
            exp_ranges = job_df["Experience Range"].dropna()
            exp_ranges = exp_ranges[exp_ranges.str.strip() != ""]  # Exclude blank/empty
            top_exp = exp_ranges.value_counts().head(5)
            if not top_exp.empty:
                lines.append("  Top 5 Experience Requirements:")
                for i, (exp, count) in enumerate(top_exp.items(), 1):
                    lines.append(f"    {i}. {exp} ({count})")
                lines.append("")
    return "\n".join(lines)
