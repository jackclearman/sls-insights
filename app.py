import streamlit as st
import pandas as pd
import json

st.set_page_config(page_title="Legal Recruiting Dashboard", layout="wide")
st.title("Legal Recruiting Dashboard - Q1 2025")

# --- Styling: Force visible horizontal scrollbars on all tables ---
st.markdown("""
    <style>
    /* Show scrollbar always for horizontal tables */
    .stDataFrame div[data-testid="stDataFrameScrollableWrapper"] {
        overflow-x: scroll !important;
    }

    .stDataFrame div[data-testid="stDataFrameScrollableWrapper"]::-webkit-scrollbar {
        height: 12px;
        display: block !important;
    }

    .stDataFrame div[data-testid="stDataFrameScrollableWrapper"]::-webkit-scrollbar-thumb {
        background-color: #888;
        border-radius: 6px;
    }

    .stDataFrame div[data-testid="stDataFrameScrollableWrapper"]::-webkit-scrollbar-thumb:hover {
        background-color: #555;
    }

    .stDataFrame div[data-testid="stDataFrameScrollableWrapper"] {
        scrollbar-width: auto;
        scrollbar-color: #888 #222;
    }
    </style>
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

# --- Tabs ---
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Top Firms", "Top Cities", "Practice Areas", "Experience", "Am Law 50"
])

with tab1:
    st.subheader("Top Destination Firms")
    top_firms = df["To Firm"].value_counts().head(10)
    st.bar_chart(top_firms)
    st.dataframe(df[df["To Firm"].isin(top_firms.index)], use_container_width=True)

with tab2:
    st.subheader("Top Cities for Moves")
    top_cities = df["City"].value_counts().head(10)
    st.bar_chart(top_cities)
    st.dataframe(df[df["City"].isin(top_cities.index)], use_container_width=True)

with tab3:
    st.subheader("Top Practice Areas")
    exploded = df.assign(Practice_Area=df["Practice Areas"].str.split(", ")).explode("Practice_Area")
    top_areas = exploded["Practice_Area"].value_counts().head(10)
    st.bar_chart(top_areas)
    st.dataframe(exploded[exploded["Practice_Area"].isin(top_areas.index)], use_container_width=True)

with tab4:
    st.subheader("Graduation Year Distribution")
    st.bar_chart(df["Graduation Year"].dropna().value_counts().sort_index())
    st.dataframe(df[df["Graduation Year"].notna()], use_container_width=True)

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
    st.dataframe(amlaw_df[amlaw_df["To Firm"].isin(top_firms.index)], use_container_width=True)

    st.markdown("#### Top Cities")
    top_cities = amlaw_df["City"].value_counts().head(10)
    st.bar_chart(top_cities)
    st.dataframe(amlaw_df[amlaw_df["City"].isin(top_cities.index)], use_container_width=True)

    st.markdown("#### Top Practice Areas")
    exploded = amlaw_df.assign(Practice_Area=amlaw_df["Practice Areas"].str.split(", ")).explode("Practice_Area")
    top_areas = exploded["Practice_Area"].value_counts().head(10)
    st.bar_chart(top_areas)
    st.dataframe(exploded[exploded["Practice_Area"].isin(top_areas.index)], use_container_width=True)

    st.markdown("#### Graduation Year Distribution")
    st.bar_chart(amlaw_df["Graduation Year"].dropna().value_counts().sort_index())
    st.dataframe(amlaw_df[amlaw_df["Graduation Year"].notna()], use_container_width=True)
