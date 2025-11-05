import streamlit as st
from streamlit_app.sf_queries import get_opportunities_for_candidate, generate_candidate_password

def dashboard_candidate(candidate_record):
    st.header(f"Welcome, {candidate_record['Name']}")
    
    # Generate the expected password for this candidate
    expected_password = generate_candidate_password(candidate_record['Name'])
    
    # Check if password is already verified in session
    session_key = f"candidate_authenticated_{candidate_record['Id']}"
    
    if not st.session_state.get(session_key, False):
        # Show password form
        st.subheader("Please enter your password to access your opportunities with SLS")
        
        with st.form("password_form"):
            entered_password = st.text_input("Password", type="password")
            submit_button = st.form_submit_button("Access Portal")
            
            if submit_button:
                if entered_password == expected_password:
                    st.session_state[session_key] = True
                    st.success("Access granted!")
                    st.rerun()
                else:
                    st.error("Incorrect password. Please contact your recruiter for assistance.")
        
        # Don't show opportunities until authenticated
        return
    
    # Show opportunities if authenticated
    opps = get_opportunities_for_candidate(candidate_record["Id"])
    st.subheader("Opportunities You've Been Submitted To")
    if not opps:
        st.info("No opportunities found for you.")
        return
    
    # Display opportunities table
    st.table([
        {
            "Name": o.get("Name", ""),
            "Account Name": o.get("Account_Name__c", ""),
            "Stage": o.get("StageName", ""),
            "Status": o.get("Status__c", ""),
            "Open Job": o.get("Open_Job__r", {}).get("Name", "") if o.get("Open_Job__r") else ""
        }
        for o in opps
    ])
    
    # Notes section for candidate feedback
    st.markdown("---")
    st.subheader("Your Notes & Feedback")
    
    # Create tabs for each opportunity if multiple, otherwise single text area
    if len(opps) == 1:
        # Single opportunity - simple text area
        opp = opps[0]
        opp_id = opp.get("Id", "")
        opp_name = opp.get("Name", "Unnamed Opportunity")
        
        st.write(f"**Notes for:** {opp_name}")
        
        # Initialize candidate notes storage if not exists
        if "candidate_notes" not in st.session_state:
            st.session_state.candidate_notes = {}
        
        # Get existing note or empty string
        current_note = st.session_state.candidate_notes.get(opp_id, "")
        
        # Text area for candidate notes
        note = st.text_area(
            "Add your thoughts, questions, or feedback about this opportunity:",
            value=current_note,
            height=150,
            key=f"candidate_note_{opp_id}",
            help="Share your thoughts about this opportunity. Your recruiter may follow up based on your feedback."
        )
        
        # Save note to session state
        st.session_state.candidate_notes[opp_id] = note
        
        if note.strip():
            st.success(f"Your feedback has been saved for {opp_name}")
            
    else:
        # Multiple opportunities - use tabs
        tab_names = [f"{o.get('Name', 'Opportunity')} ({o.get('StageName', 'No Stage')})" for o in opps]
        tabs = st.tabs(tab_names)
        
        for i, (tab, opp) in enumerate(zip(tabs, opps)):
            with tab:
                opp_id = opp.get("Id", "")
                opp_name = opp.get("Name", "Unnamed Opportunity")
                
                # Initialize candidate notes storage if not exists
                if "candidate_notes" not in st.session_state:
                    st.session_state.candidate_notes = {}
                
                # Get existing note or empty string
                current_note = st.session_state.candidate_notes.get(opp_id, "")
                
                # Display opportunity details
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Company", opp.get("Account_Name__c", "N/A"))
                    st.metric("Stage", opp.get("StageName", "N/A"))
                with col2:
                    st.metric("Status", opp.get("Status__c", "N/A"))
                    st.metric("Open Job", opp.get("Open_Job__r", {}).get("Name", "N/A") if opp.get("Open_Job__r") else "N/A")
                
                # Text area for candidate notes
                note = st.text_area(
                    "Add your thoughts, questions, or feedback about this opportunity:",
                    value=current_note,
                    height=150,
                    key=f"candidate_note_{opp_id}_{i}",  # Include index to ensure uniqueness
                    help="Share your thoughts about this opportunity. Your recruiter may follow up based on your feedback."
                )
                
                # Save note to session state
                st.session_state.candidate_notes[opp_id] = note
                
                if note.strip():
                    st.success(f"Your feedback has been saved for {opp_name}")
