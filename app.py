import streamlit as st
import pandas as pd
import json

st.set_page_config(page_title="Legal Recruiting Dashboard", layout="wide")
st.title("Legal Recruiting Dashboard - Q1 2025")

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

# --- Selector ---
role_type = st.radio("Select Attorney Type", ["Partners", "Associates"])

# --- Summary Text ---
if role_type == "Partners":
    df = pd.DataFrame([extract(a) for a in partners])
    st.markdown("""
    ### Partner Market Trends – Q1 2025 (Detailed Stats & Movers)

    Partner mobility remained strong in Q1 2025, with **Orrick, Herrington & Sutcliffe LLP** emerging as one of the top destination firms, making three notable partner hires this quarter. One of the most high-profile moves was **Matt Nesburn**, a Chambers- and Legal 500-recognized project finance attorney with deep expertise in renewable energy. Nesburn joined Orrick from **A&O Shearman**, bringing with him extensive experience across solar, wind, and storage sectors, and a resume that includes deals with **SunPower**, **AES Clean Energy**, and **JERA North America**.

    Other firms with significant activity included **Cleary Gottlieb**, which added two new partners, including **Justin “J.T.” Ho**, a governance and ESG expert known for his work on shareholder activism and executive compensation. He previously held partner roles at Orrick and is a graduate of **UC Berkeley School of Law** with multiple recognitions, including Super Lawyers and The Legal 500’s Next Generation Partner.

    Overall, **68%** of partner moves were to Am Law 100 firms, and **42%** of those laterals specialized in corporate, energy, or project finance. **61%** of all movers had national or international honors such as **Chambers**, **Legal 500**, or **Super Lawyers**, and nearly **70%** graduated from top 20 law schools, with **UCLA**, **UC Berkeley**, and **Columbia** among the most frequent alma maters.
    """)
else:
    df = pd.DataFrame([extract(a) for a in associates])
    st.markdown("""
    ### Associate Market Trends – Q1 2025 (Detailed Stats & Movers)

    Associate lateral moves increased **18%** compared to Q4 2024, with **litigation (43%)**, **labor and employment (29%)**, and **education law (13%)** making up the majority of practice areas. **Seyfarth Shaw LLP** stood out as both a top destination and source of associate movement, adding two experienced associates and losing one to a boutique competitor.

    Among the standout movers was **Ryan Dyer**, who joined **Byrnes Keller Cromwell LLP**. A magna cum laude graduate of Seattle University School of Law and former Law Review editor, Dyer brought a strong background in commercial litigation and trial work. Another notable transition was **Daniel Culicover**, who moved from **Gordon & Rees** to **Seyfarth Shaw**. A cum laude graduate of American University’s law program, Culicover has developed a niche in education law and administrative defense.

    Over **55%** of associate movers had honors like Law Review or Super Lawyers Rising Star, and nearly **65%** were alumni of top 50 law schools. While national firms were still attractive, **61%** of associates moved to regional or boutique firms, often for greater autonomy, deeper specialization, or a better work-life balance.
    """)

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
