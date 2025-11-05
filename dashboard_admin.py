import streamlit as st
from streamlit_app.sf_queries import get_engaged_candidates

def dashboard_admin():
    st.header("Recruiter Dashboard")
    candidates = get_engaged_candidates()
    st.subheader("Engaged Candidates")
    st.table([
        {
            "Name": c["Name"],
            "Token": c["Public_Token__c"],
            "Recruiter (OwnerId)": c["OwnerId"]
        }
        for c in candidates
    ])
