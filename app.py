import streamlit as st
import pandas as pd
import json
import matplotlib.pyplot as plt

st.title("Legal Recruiting Dashboard - Q1 2025")

# --- Load Data ---
with open("partner_moves_q1_2025.json") as f:
    data = json.load(f)["data"]

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
        "To Firm": move.get("new", {}).get("firm_name")
    }

df = pd.DataFrame([extract(a) for a in data])

# --- Tabs ---
tab1, tab2, tab3, tab4 = st.tabs(["Top Firms", "Top Cities", "Practice Areas", "Experience"])

with tab1:
    st.subheader("Top Destination Firms")
    top_firms = df["To Firm"].value_counts().head(10)
    st.bar_chart(top_firms)
    st.dataframe(df[df["To Firm"].isin(top_firms.index)])

with tab2:
    st.subheader("Top Cities for Moves")
    top_cities = df["City"].value_counts().head(10)
    st.bar_chart(top_cities)
    st.dataframe(df[df["City"].isin(top_cities.index)])

with tab3:
    st.subheader("Top Practice Areas")
    exploded = df.assign(Practice_Area=df["Practice Areas"].str.split(", ")).explode("Practice_Area")
    top_areas = exploded["Practice_Area"].value_counts().head(10)
    st.bar_chart(top_areas)
    st.dataframe(exploded[exploded["Practice_Area"].isin(top_areas.index)])

with tab4:
    st.subheader("Graduation Year Distribution")
    st.bar_chart(df["Graduation Year"].dropna().value_counts().sort_index())
    st.dataframe(df[df["Graduation Year"].notna()])
