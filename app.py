import streamlit as st
from login import login_form, logout_button
from sf_queries import get_candidate_by_token
from dashboard_candidate import dashboard_candidate
from dashboard_recruiter import dashboard_recruiter
# Email tracking dashboard (new)
from dashboard_email_tracking import render_email_tracking

def main():
    # Ensure `st.set_page_config()` is the first Streamlit command in the script.
    st.set_page_config(page_title="SLS Portal", layout="wide")
    # Validate required secrets and show clear message in UI if missing
    missing = []
    try:
        if "SALESFORCE" not in st.secrets:
            missing.append("SALESFORCE")
    except Exception:
        missing.append("SALESFORCE")
    try:
        if "API_CREDENTIALS" not in st.secrets:
            # optional for some flows, but warn
            missing.append("API_CREDENTIALS")
    except Exception:
        missing.append("API_CREDENTIALS")
    if missing:
        st.error(f"Missing required secrets: {', '.join(missing)}. If running locally, create .streamlit/secrets.toml; if deployed, add them in Streamlit Cloud Secrets.")
        # Continue so developer can still see UI, but many features will be disabled
    
    # Check for candidate token first
    token = st.query_params.get("token")
    
    # Show logout button if user is logged in
    logout_button()
    
    if token:
        # Candidate portal
        candidate = get_candidate_by_token(token)
        if candidate:
            dashboard_candidate(candidate)
        else:
            st.error("Invalid or expired token.")
    else:
        # Show login form for recruiters
        st.title("SLS Portal")
        
        # Check if user is already logged in
        if "salesforce_token" in st.session_state and st.session_state["salesforce_token"]:
            # User is logged in, show recruiter dashboard
            token = st.session_state.get("salesforce_token", {})
            user_id = None
            id_url = token.get("id", "")
            if id_url:
                import re
                match = re.search(r'/([^/]+)$', id_url)
                if match:
                    user_id = match.group(1)
            if user_id:
                # Allow recruiters to choose between their dashboard and the Email Tracking page
                page = st.selectbox("Select Page", ["Recruiter Dashboard", "Email Tracking"], index=0)
                if page == "Email Tracking":
                    # render the new email tracking dashboard (uses st.session_state['user_email'])
                    render_email_tracking()
                else:
                    dashboard_recruiter(user_id)
            else:
                st.error("Could not extract Salesforce user ID from token.")
        else:
            # Show login form
            if login_form():
                # Login successful, rerun to show dashboard
                st.rerun()

if __name__ == "__main__":
    main()
