import streamlit as st
import pandas as pd
import numpy as np
import json
import plotly.express as px
import plotly.graph_objects as go
import altair as alt
from streamlit.logger import get_logger

# Set up logger for debugging
logger = get_logger(__name__)

# Set page configuration with more space
st.set_page_config(page_title="Legal Recruiting Dashboard", layout="wide")

# Custom CSS to improve font sizes and spacing
st.markdown("""
<style>
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    h1 {
        font-size: 2.5rem !important;
        margin-bottom: 1.5rem !important;
    }
    h2, h3 {
        margin-top: 1.5rem !important;
        margin-bottom: 1rem !important;
    }
    .stPlotlyChart, .stChart {
        height: 450px !important;
    }
    .dataframe {
        font-size: 1rem !important;
    }
    .stTabs [data-baseweb="tab"] {
        font-size: 1.1rem !important;
    }
</style>
""", unsafe_allow_html=True)

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

# --- Selector with more space ---
st.markdown("### Select Attorney Type")
role_type = st.radio("", ["Partners", "Associates"], horizontal=True, label_visibility="collapsed")

# Add some spacing
st.markdown("<br>", unsafe_allow_html=True)

# --- Summary Text ---
if role_type == "Partners":
    df = pd.DataFrame([extract(a) for a in partners])
    st.markdown("""
    ### Partner Market Trends – Q1 2025 (Detailed Stats & Movers)

    Partner mobility remained strong in Q1 2025, with **Orrick, Herrington & Sutcliffe LLP** emerging as the top destination firm, making three notable partner hires this quarter. One of the most high-profile moves was **Matt Nesburn**, a Chambers- and Legal 500-recognized project finance attorney with deep expertise in renewable energy. Nesburn joined Orrick from **A&O Shearman**, bringing with him extensive experience across solar, wind, and storage sectors, and a resume that includes deals with **SunPower**, **AES Clean Energy**, and **JERA North America**.

    Other firms with significant activity included **Cleary Gottlieb**, which added two new partners, including **Justin "J.T." Ho**, a governance and ESG expert known for his work on shareholder activism and executive compensation. He previously held partner roles at Orrick and is a graduate of **UC Berkeley School of Law** with multiple recognitions, including Super Lawyers and The Legal 500's Next Generation Partner.

    Overall, **68%** of partner moves were to Am Law 100 firms, and **42%** of those laterals specialized in corporate, energy, or project finance. **61%** of all movers had national or international honors such as **Chambers**, **Legal 500**, or **Super Lawyers**, and nearly **70%** graduated from top 20 law schools, with **UCLA**, **UC Berkeley**, and **Columbia** among the most frequent alma maters.
    """)
else:
    df = pd.DataFrame([extract(a) for a in associates])
    st.markdown("""
    ### Associate Market Trends – Q1 2025 (Detailed Stats & Movers)

    Associate lateral moves increased **18%** compared to Q4 2024, with **litigation (43%)**, **labor and employment (29%)**, and **education law (13%)** making up the majority of practice areas. **Seyfarth Shaw LLP** stood out as both a top destination and source of associate movement, adding two experienced associates and losing one to a boutique competitor.

    Among the standout movers was **Ryan Dyer**, who joined **Byrnes Keller Cromwell LLP**. A magna cum laude graduate of Seattle University School of Law and former Law Review editor, Dyer brought a strong background in commercial litigation and trial work. Another notable transition was **Daniel Culicover**, who moved from **Gordon & Rees** to **Seyfarth Shaw**. A cum laude graduate of American University's law program, Culicover has developed a niche in education law and administrative defense.

    Over **55%** of associate movers had honors like Law Review or Super Lawyers Rising Star, and nearly **65%** were alumni of top 50 law schools. While national firms were still attractive, **61%** of associates moved to regional or boutique firms, often for greater autonomy, deeper specialization, or a better work-life balance.
    """)

# Add more spacing
st.markdown("<br>", unsafe_allow_html=True)

# --- Tabs with improved charts ---
tab1, tab2, tab3, tab4 = st.tabs(["Top Firms", "Top Cities", "Practice Areas", "Experience"])

# Function to create better charts with Plotly
def create_bar_chart(data, title, x_label, y_label, height=500):
    # Handle empty data case
    if len(data) == 0:
        return px.bar(title="No data available")
    
    # Convert data to DataFrame if it's a Series
    if isinstance(data, pd.Series):
        df = data.reset_index()
        df.columns = ['index', 'value']
        x_col = 'index'
        y_col = 'value'
    else:
        df = data
        x_col = df.columns[0]
        y_col = df.columns[1]
    
    # Create the figure
    fig = px.bar(
        df,
        x=x_col,
        y=y_col,
        labels={x_col: x_label, y_col: y_label},
        title=title,
        height=height,
        text=y_col  # Display values on bars
    )
    
    fig.update_layout(
        title={
            'font': {'size': 20},
            'y': 0.95,
            'x': 0.5,
            'xanchor': 'center',
            'yanchor': 'top'
        },
        xaxis_tickangle=-45,
        xaxis_title_font={'size': 16},
        yaxis_title_font={'size': 16},
        font={'size': 14},
        margin=dict(l=60, r=60, t=80, b=80),
        bargap=0.2
    )
    
    fig.update_traces(
        textposition='outside',
        textfont_size=14
    )
    
    return fig

with tab1:
    st.markdown("### Top Destination Firms")
    # Get top firms, handle missing values
    firm_counts = df["To Firm"].dropna().value_counts().head(10)
    
    # Fall back to Altair if Plotly has issues
    try:
        # Try with Plotly
        st.plotly_chart(create_bar_chart(firm_counts, "Top Destination Firms", "Firm", "Number of Attorneys"), use_container_width=True)
    except Exception as e:
        st.warning(f"Using fallback chart renderer due to an issue with the primary renderer.")
        # Fallback to Altair
        chart = alt.Chart(firm_counts.reset_index()).mark_bar().encode(
            x=alt.X('index:N', title='Firm', sort='-y'),
            y=alt.Y('To Firm:Q', title='Number of Attorneys')
        ).properties(
            height=400
        )
        st.altair_chart(chart, use_container_width=True)
    
    # More readable data table with custom formatting
    st.markdown("#### Attorneys Moving to Top Firms")
    filtered_df = df[df["To Firm"].isin(firm_counts.index)][["Name", "To Firm", "From Firm", "Practice Areas", "City"]]
    st.dataframe(
        filtered_df,
        use_container_width=True,
        height=400
    )

with tab2:
    st.markdown("### Top Cities for Moves")
    # Get top cities, handle missing values
    city_counts = df["City"].dropna().value_counts().head(10)
    
    # Fall back to Altair if Plotly has issues
    try:
        # Try with Plotly
        st.plotly_chart(create_bar_chart(city_counts, "Top Cities for Attorney Moves", "City", "Number of Attorneys"), use_container_width=True)
    except Exception as e:
        st.warning(f"Using fallback chart renderer due to an issue with the primary renderer.")
        # Fallback to Altair
        chart = alt.Chart(city_counts.reset_index()).mark_bar().encode(
            x=alt.X('index:N', title='City', sort='-y'),
            y=alt.Y('City:Q', title='Number of Attorneys')
        ).properties(
            height=400
        )
        st.altair_chart(chart, use_container_width=True)
    
    st.markdown("#### Attorneys Moving in Top Cities")
    filtered_df = df[df["City"].isin(city_counts.index)][["Name", "City", "To Firm", "From Firm", "Practice Areas"]]
    st.dataframe(
        filtered_df,
        use_container_width=True,
        height=400
    )

with tab3:
    st.markdown("### Top Practice Areas")
    # Create a safer version of exploding practice areas
    try:
        exploded = df.assign(Practice_Area=df["Practice Areas"].str.split(", ")).explode("Practice_Area")
        exploded = exploded[exploded["Practice_Area"].notna() & (exploded["Practice_Area"] != "")]
        top_areas = exploded["Practice_Area"].value_counts().head(10)
        
        # Fall back to Altair if Plotly has issues
        try:
            # Try with Plotly
            st.plotly_chart(create_bar_chart(top_areas, "Top Attorney Practice Areas", "Practice Area", "Number of Attorneys"), use_container_width=True)
        except Exception as e:
            st.warning(f"Using fallback chart renderer due to an issue with the primary renderer.")
            # Fallback to Altair
            chart = alt.Chart(top_areas.reset_index()).mark_bar().encode(
                x=alt.X('index:N', title='Practice Area', sort='-y'),
                y=alt.Y('Practice_Area:Q', title='Number of Attorneys')
            ).properties(
                height=400
            )
            st.altair_chart(chart, use_container_width=True)
        
        st.markdown("#### Attorneys in Top Practice Areas")
        filtered_df = exploded[exploded["Practice_Area"].isin(top_areas.index)][["Name", "Practice_Area", "To Firm", "From Firm", "City"]]
        st.dataframe(
            filtered_df,
            use_container_width=True,
            height=400
        )
    except Exception as e:
        st.error(f"Error processing practice areas: {str(e)}")
        # Show raw practice areas as fallback
        st.markdown("#### Practice Areas (Raw)")
        st.dataframe(
            df[["Name", "Practice Areas", "To Firm", "From Firm", "City"]],
            use_container_width=True,
            height=400
        )

with tab4:
    st.markdown("### Graduation Year Distribution")
    try:
        # Safely process graduation years with error handling
        grad_years_raw = df["Graduation Year"].dropna()
        
        # Handle potential non-numeric values
        valid_years = pd.to_numeric(grad_years_raw, errors='coerce').dropna()
        
        if len(valid_years) > 0:
            # Convert to integer format
            grad_years = valid_years.astype(int)
            year_counts = grad_years.value_counts().sort_index()
            
            # Fall back to Altair if Plotly has issues
            try:
                # Try with a simpler Plotly chart approach
                year_df = year_counts.reset_index()
                year_df.columns = ['Year', 'Count']
                
                fig = px.bar(
                    year_df,
                    x='Year',
                    y='Count',
                    labels={"Year": "Graduation Year", "Count": "Number of Attorneys"},
                    title="Attorney Distribution by Graduation Year",
                    height=500,
                    text='Count'
                )
                
                fig.update_layout(
                    title_font_size=20,
                    xaxis_title_font={'size': 16},
                    yaxis_title_font={'size': 16},
                    font={'size': 14},
                    bargap=0.2,
                    margin=dict(l=60, r=60, t=80, b=60)
                )
                
                fig.update_traces(
                    textposition='outside',
                    textfont_size=14
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
            except Exception as e:
                st.warning(f"Using fallback chart renderer due to an issue with the primary renderer.")
                # Fallback to Altair
                chart = alt.Chart(year_counts.reset_index()).mark_bar().encode(
                    x=alt.X('index:N', title='Graduation Year', sort='x'),
                    y=alt.Y('Graduation Year:Q', title='Number of Attorneys')
                ).properties(
                    height=400
                )
                st.altair_chart(chart, use_container_width=True)
            
            st.markdown("#### Attorney Details by Graduation Year")
            # Calculate experience in years for clarity
            current_year = 2025
            
            # Display with custom formatting and additional useful columns
            display_df = df[df["Graduation Year"].notna()].copy()
            
            # Safely convert to numeric for experience calculation
            display_df["Graduation Year"] = pd.to_numeric(display_df["Graduation Year"], errors='coerce')
            display_df = display_df.dropna(subset=["Graduation Year"])
            
            # Calculate years of experience
            display_df["Experience (Years)"] = current_year - display_df["Graduation Year"]
            display_df["Experience (Years)"] = display_df["Experience (Years)"].astype(int)
            
            # Format graduation year as integer for display
            display_df["Graduation Year"] = display_df["Graduation Year"].astype(int)
            
            st.dataframe(
                display_df[["Name", "Graduation Year", "Experience (Years)", "Law School", "To Firm", "From Firm"]].sort_values("Graduation Year", ascending=False),
                use_container_width=True,
                height=400
            )
        else:
            st.warning("No valid graduation year data available to display.")
    except Exception as e:
        st.error(f"Error processing graduation years: {str(e)}")
        st.dataframe(
            df[["Name", "Graduation Year", "Law School", "To Firm", "From Firm"]],
            use_container_width=True,
            height=400
        )

# Add a footer with additional information
st.markdown("---")
st.markdown("""
<div style="text-align: center; padding: 20px; opacity: 0.8; font-size: 0.9rem;">
    Data source: FirmProspects | Dashboard last updated: April 8, 2025
</div>
""", unsafe_allow_html=True)
