import streamlit as st
import pandas as pd
import json

st.set_page_config(page_title="Legal Recruiting Dashboard", layout="wide")
st.title("Legal Recruiting Dashboard - Q1 2025")

# --- Custom Scrollbar Implementation ---
st.markdown("""
    <style>
    /* Custom scrollbar implementation */
    /* First, hide the default Streamlit scrollbar completely */
    .stDataFrame div[data-testid="stDataFrameScrollableWrapper"] {
        overflow-x: hidden !important;
        overflow-y: hidden !important;
        position: relative !important;
        max-width: 100% !important;
    }
    
    /* Custom scrollbar container that's always visible */
    .stDataFrame {
        position: relative !important;
        margin-bottom: 25px !important;
    }
    
    /* Add custom scrollbar that's always visible */
    .stDataFrame::after {
        content: "";
        display: block;
        position: absolute;
        bottom: -20px;
        left: 0;
        right: 0;
        height: 16px;
        background-color: #e1e1e1;
        border-radius: 8px;
        z-index: 1000;
    }
    
    /* Add custom scrollbar thumb that's always visible */
    .stDataFrame::before {
        content: "";
        display: block;
        position: absolute;
        bottom: -20px;
        left: 5%;
        width: 30%;
        height: 16px;
        background-color: #888;
        border-radius: 8px;
        z-index: 1001;
    }
    
    /* Add wrapper div for horizontal scrolling */
    .scroll-wrapper {
        width: 100%;
        overflow-x: auto;
        padding-bottom: 20px;
    }
    
    /* Style the wrapper scrollbar */
    .scroll-wrapper::-webkit-scrollbar {
        height: 16px;
        background-color: #e1e1e1;
        border-radius: 8px;
    }
    
    .scroll-wrapper::-webkit-scrollbar-thumb {
        background-color: #888;
        border-radius: 8px;
    }
    </style>
    
    <script>
    // Add JavaScript to handle synchronizing scroll positions
    // This will be executed once the page loads
    document.addEventListener('DOMContentLoaded', function() {
        // Find all Streamlit DataFrame containers
        const dataFrames = document.querySelectorAll('.stDataFrame');
        
        dataFrames.forEach(function(df) {
            // Create a wrapper for horizontal scrolling
            const wrapper = document.createElement('div');
            wrapper.className = 'scroll-wrapper';
            
            // Move the table inside the wrapper
            const table = df.querySelector('table');
            if (table) {
                const scrollable = df.querySelector('[data-testid="stDataFrameScrollableWrapper"]');
                if (scrollable) {
                    // Fix the width of the table to be wide enough to scroll
                    table.style.width = '150%';
                    
                    // Wrap in our custom scroll container
                    scrollable.parentNode.insertBefore(wrapper, scrollable);
                    wrapper.appendChild(scrollable);
                }
            }
        });
    });
    </script>
""", unsafe_allow_html=True)

# --- Load Data ---
@st.cache_data
def load_data():
    with open("partner_moves_q1_2025.json") as f:
        partners = json.load(f)["data"]
    with open("associate_moves_q1_2025.json") as f:
        associates = json.load(f)["data"]
    return partners, associates

partners, associates = load_data()

# --- Extract Function ---
def extract(attorney):
    recent = attorney.get("recent_move") or {}
    move = recent.get("firm") or {}
    return {
        "Name": f"{attorney.get('first_name', '')} {attorney.get('last_name', '')}",
        "Current Firm": attorney.get("firm", {}).get("firm_name"),
        "City": attorney.get("location", {}).get("city"),
        "Practice Areas": ", ".join(attorney.get("attorneys_practice_areas", [])),
        "Specialties": ", ".join(attorney.get("attorneys_specialties", [])),
        "Law School": attorney.get("law_school", {}).get("law_school_name"),
        "Graduation Year": attorney.get("graduation_year"),
        "Title": ", ".join(attorney.get("attorneys_titles", [])),
        "From Firm": move.get("old", {}).get("firm_name"),
        "To Firm": move.get("new", {}).get("firm_name"),
        "FirmProspects ID": attorney.get("id"),
        "Profile Link": f"[Link](https://engage.firmprospects.com/attorneys/profile/{attorney.get('id')})"
    }

# --- Main Role Selector ---
role_type = st.radio("Select Attorney Type", ["Partners", "Associates"])

# --- Summary + Base DataFrame ---
if role_type == "Partners":
    st.markdown("### Partner Market Trends – Q1 2025 (Detailed Stats & Movers)")
    st.markdown("*Partner summary goes here...*")
    df = pd.DataFrame([extract(a) for a in partners])
else:
    st.markdown("### Associate Market Trends – Q1 2025 (Detailed Stats & Movers)")
    st.markdown("*Associate summary goes here...*")
    df = pd.DataFrame([extract(a) for a in associates])

# --- Alternative approach using HTML tables with custom scrolling ---
def display_df_as_html_table(df, max_rows=1000):
    # Convert DataFrame to HTML table with custom scrolling
    table_html = df.head(max_rows).to_html(escape=False, index=True)
    
    # Wrap in a div with custom scrolling
    html = f"""
    <div style="width:100%; overflow-x:auto; margin-bottom:30px;">
        <div style="min-width:150%; width:max-content;">
            {table_html}
        </div>
    </div>
    <div style="height:20px; width:100%; background:#e1e1e1; border-radius:8px; position:relative; margin-top:-25px; margin-bottom:25px;">
        <div style="height:20px; width:30%; background:#888; border-radius:8px; position:absolute; left:5%;"></div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

# --- Tabs ---
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Top Firms", "Top Cities", "Practice Areas", "Experience", "Am Law 50"
])

with tab1:
    st.subheader("Top Destination Firms")
    top_firms = df["To Firm"].value_counts().head(10)
    st.bar_chart(top_firms)
    # Use custom HTML table instead of st.dataframe
    display_df_as_html_table(df[df["To Firm"].isin(top_firms.index)])

with tab2:
    st.subheader("Top Cities for Moves")
    top_cities = df["City"].value_counts().head(10)
    st.bar_chart(top_cities)
    display_df_as_html_table(df[df["City"].isin(top_cities.index)])

with tab3:
    st.subheader("Top Practice Areas")
    exploded = df.assign(Practice_Area=df["Practice Areas"].str.split(", ")).explode("Practice_Area")
    top_areas = exploded["Practice_Area"].value_counts().head(10)
    st.bar_chart(top_areas)
    display_df_as_html_table(exploded[exploded["Practice_Area"].isin(top_areas.index)])

with tab4:
    st.subheader("Graduation Year Distribution")
    st.bar_chart(df["Graduation Year"].dropna().value_counts().sort_index())
    display_df_as_html_table(df[df["Graduation Year"].notna()])

with tab5:
    st.subheader("Am Law 50 Movers")

    amlaw_type = st.selectbox("View Am Law 50 Moves For:", ["Partners", "Associates"])

    if amlaw_type == "Partners":
        source = partners
    else:
        source = associates

    amlaw_df = pd.DataFrame([
        extract(a) for a in source
        if (a.get("firm", {}).get("ranks", {}).get("top200") or 1000) <= 50
    ])

    st.markdown(f"Showing attorneys who **joined firms ranked 1–50** in the Am Law 200 ({amlaw_type}).")

    st.markdown("#### Top Am Law 50 Destination Firms")
    top_firms = amlaw_df["To Firm"].value_counts().head(10)
    st.bar_chart(top_firms)
    display_df_as_html_table(amlaw_df[amlaw_df["To Firm"].isin(top_firms.index)])

    st.markdown("#### Top Cities")
    top_cities = amlaw_df["City"].value_counts().head(10)
    st.bar_chart(top_cities)
    display_df_as_html_table(amlaw_df[amlaw_df["City"].isin(top_cities.index)])

    st.markdown("#### Top Practice Areas")
    exploded = amlaw_df.assign(Practice_Area=amlaw_df["Practice Areas"].str.split(", ")).explode("Practice_Area")
    top_areas = exploded["Practice_Area"].value_counts().head(10)
    st.bar_chart(top_areas)
    display_df_as_html_table(exploded[exploded["Practice_Area"].isin(top_areas.index)])

    st.markdown("#### Graduation Year Distribution")
    st.bar_chart(amlaw_df["Graduation Year"].dropna().value_counts().sort_index())
    display_df_as_html_table(amlaw_df[amlaw_df["Graduation Year"].notna()])
