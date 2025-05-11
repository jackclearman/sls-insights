import os
from datetime import datetime, timedelta

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

# ──────────────────────────────────────────────────────────────────────────────
# SLS Insights Dashboard  (2025‑05‑10)
#   • plain‑text counts (no green banners)
#   • working AmLaw filters
#   • complete Experience tabs for Jobs *and* Placements
#   • detailed tables in every placement sub‑view
# ──────────────────────────────────────────────────────────────────────────────

st.set_page_config(page_title="Legal Recruiting Dashboard", layout="wide")
st.title("SLS Insights Dashboard")

JOBS_API_ENDPOINT      = "https://developer.firmprospects.com/v1/jobs"
ATTORNEYS_API_ENDPOINT = "https://developer.firmprospects.com/v1/attorneys"
JOB_COLOR   = "#636EFA"  # plotly blue
ATTY_COLOR  = "#EF553B"  # plotly red

# ──────────────────────────────────────────────────────────────────────────────
# helper functions
# ──────────────────────────────────────────────────────────────────────────────

def get_api_key():
    try:
        return st.secrets["API_CREDENTIALS"]["X_AUTH_TOKEN"]
    except Exception:
        token = os.environ.get("FIRMPROSPECTS_API_TOKEN")
        if token:
            return token
        st.error("API key not found → add to Streamlit secrets or env var.")
        return None

@st.cache_data
def load_amlaw_data():
    try:
        df = pd.read_csv("amlaw_200.csv")
        if not {"FP ID - Firm", "AmLaw Rank"}.issubset(df.columns):
            df.columns = ["AmLaw Rank", "FP ID - Firm"]
        df["FP ID - Firm"] = pd.to_numeric(df["FP ID - Firm"], errors="coerce")
        df["AmLaw Rank"]   = pd.to_numeric(df["AmLaw Rank"],   errors="coerce")
        return df
    except Exception as e:
        st.warning(f"Could not load AmLaw CSV → {e}")
        return pd.DataFrame(columns=["AmLaw Rank", "FP ID - Firm"])

@st.cache_data(ttl=24*3600)
def fetch_jobs(days:int=30):
    key=get_api_key();
    if not key: return []
    headers={"X-AUTH-TOKEN":key,"Content-Type":"application/json"}
    today=datetime.now().strftime("%Y-%m-%d"); start=(datetime.now()-timedelta(days=days)).strftime("%Y-%m-%d")
    base={"regions":{"items":["California","Washington-Seattle"],"condition":"or","use_second_location":True},
          "posted_date":{"min":start,"max":today},"status":1}
    params={"t":"","page[limit]":5000,"page[offset]":0,"condition":"AND"}
    all_jobs=[]
    for t in ("Associate","Partner"):
        r=requests.post(JOBS_API_ENDPOINT,headers=headers,json={**base,"title":[t]},params=params); r.raise_for_status()
        all_jobs.extend(r.json().get("data",[]))
    return all_jobs

@st.cache_data(ttl=24*3600)
def fetch_attorneys(kind:str,days:int=90):
    key=get_api_key();
    if not key: return []
    headers={"X-AUTH-TOKEN":key,"Content-Type":"application/json"}
    today=datetime.now().strftime("%Y-%m-%d"); start=(datetime.now()-timedelta(days=days)).strftime("%Y-%m-%d")
    payload={"regions":{"items":["California"],"condition":"or","use_second_location":True},
             "last_move_date":{"min":start,"max":today},
             "titles":["Associate"] if kind=="associates" else ["Partner"]}
    params={"t":"","page[limit]":5000,"page[offset]":0,"condition":"AND"}
    r=requests.post(ATTORNEYS_API_ENDPOINT,headers=headers,json=payload,params=params); r.raise_for_status()
    return r.json().get("data",[])

# ──────────────────────────────────────────────────────────────────────────────
# extraction helpers
# ──────────────────────────────────────────────────────────────────────────────

def extract_job(j):
    region=city=None
    if j.get("locations"):
        parts=j["locations"][0].split(", ")
        if len(parts)>1: city,region=parts[0],parts[1]
        else: city=parts[0]
    exp=""; minY,maxY=j.get("minYrs"),j.get("maxYrs")
    if minY is not None and maxY is not None:
        exp=f"{minY}-{maxY} years" if minY!=maxY else f"{minY} years"
    firm_id=j.get("firmId") or j.get("firm_id") or (j.get("firm",{}).get("id") if isinstance(j.get("firm"),dict) else None)
    return {"Job Title":j.get("jobTitle",""),"Firm":j.get("firmName",""),
            "Practice Areas":", ".join(j.get("practiceAreas",[]) or []),
            "Specialties":", ".join(j.get("specialty",[]) or []),
            "City":city,"Experience Range":exp,"Posted Date":j.get("postedDate",""),
            "Job Status":j.get("statusLabel",""),"Job Type":(j.get("title") or [""])[0],
            "FirmProspects ID":j.get("id"),"Profile Link":f"[Link]({j.get('pageUrl','')})",
            "Am Law Ranking":None,"Region":region,"Firm ID":firm_id}

def extract_attorney(a):
    recent=a.get("recent_move",{}); move=recent.get("firm",{})
    firm=a.get("firm",{}); ranks=firm.get("ranks",{})
    return {"Name":f"{a.get('first_name','')} {a.get('last_name','')}",
            "From Firm":move.get("old",{}).get("firm_name"),
            "To Firm":move.get("new",{}).get("firm_name"),
            "Practice Areas":", ".join(a.get("attorneys_practice_areas",[]) or []),
            "Specialties":", ".join(a.get("attorneys_specialties",[]) or []),
            "City":a.get("location",{}).get("city"),
            "Graduation Year":a.get("graduation_year"),
            "Law School":a.get("law_school",{}).get("law_school_name"),
            "Current Firm":firm.get("firm_name"),
            "Title":", ".join(a.get("attorneys_titles",[]) or []),
            "FirmProspects ID":a.get("id"),
            "Profile Link":f"[Link](https://engage.firmprospects.com/attorneys/profile/{a.get('id')})",
            "Am Law Ranking":ranks.get("top200"),
            "Region":a.get("location",{}).get("state"),
            "Move Date":recent.get("date"),"Firm ID":firm.get("id")}

# ──────────────────────────────────────────────────────────────────────────────
# UI LAYOUT
# ──────────────────────────────────────────────────────────────────────────────

amlaw_df=load_amlaw_data()
job_tab,atty_tab=st.tabs(["Job Postings","Attorney Placements"])

# ---------------------------------------------------------------------------
# JOBS TAB
# ---------------------------------------------------------------------------
with job_tab:
    period=st.selectbox("Select Time Period",["Last 7 days","Last 14 days","Last 30 days","Last 60 days"],index=2)
    period_days=dict(zip(["Last 7 days","Last 14 days","Last 30 days","Last 60 days"],[7,14,30,60]))[period]
    job_type=st.radio("Select Job Type",["Associates","Partners"],horizontal=True)

    if "jobs_raw" not in st.session_state:
        st.session_state.jobs_raw=fetch_jobs(period_days)
    st.text(f"{len(st.session_state.jobs_raw)} Job Postings")

    job_df=pd.DataFrame([extract_job(j) for j in st.session_state.jobs_raw])
    if not job_df.empty and not amlaw_df.empty:
        job_df["Firm ID"]=pd.to_numeric(job_df["Firm ID"],errors="coerce")
        mapping=dict(zip(amlaw_df["FP ID - Firm"],amlaw_df["AmLaw Rank"]))
        job_df["Am Law Ranking"]=job_df["Firm ID"].map(mapping).astype("Int64")

    job_df=job_df[job_df["Job Type"].str.contains("Associate" if job_type=="Associates" else "Partner",case=False,na=False)]
    if job_df.empty:
        st.warning("No jobs for selected criteria."); st.stop()

    # filters
    c1,c2,c3=st.columns(3)
    with c1:
        amlaw_f=st.selectbox("Filter by Am Law Ranking",["All Firms","Am Law 50","Am Law 100"])
    with c2:
        region_f=st.selectbox("Filter by Region",["California Only","Washington Only","All Regions"],index=2)
    with c3:
        areas=sorted({a.strip() for s in job_df["Practice Areas"].dropna() for a in s.split(",")})
        pa_f=st.selectbox("Filter by Practice Area",["All Practice Areas"]+areas)

    df=job_df.copy()
    if amlaw_f=="Am Law 50": df=df[df["Am Law Ranking"].notna() & (df["Am Law Ranking"]<=50)]
    elif amlaw_f=="Am Law 100": df=df[df["Am Law Ranking"].notna() & (df["Am Law Ranking"]<=100)]
    if region_f.startswith("California"): df=df[df["Region"]=="California"]
    elif region_f.startswith("Washington"): df=df[df["Region"]=="Washington"]
    if pa_f!="All Practice Areas": df=df[df["Practice Areas"].str.contains(pa_f,na=False)]
    if df.empty: st.warning("No jobs after filters."); st.stop()

    tf,tc,pa,exp=st.tabs(["Top Firms","Top Cities","Practice Areas","Experience"])
    # Top Firms
    with tf:
        s=df["Firm"].value_counts().head(10)
        fig=px.bar(pd.DataFrame({"Firm":s.index,"Count":s.values}),x="Firm",y="Count",color_discrete_sequence=[JOB_COLOR])
        fig.update_layout(xaxis=dict(categoryorder="total descending"),margin=dict(t=10,b=10,l=10,r=10),xaxis_fixedrange=True,yaxis_fixedrange=True)
        st.plotly_chart(fig,use_container_width=True,config={"displayModeBar":False})
        st.dataframe(df[df["Firm"].isin(s.index)][["Job Title","Firm","Practice Areas","City","Experience Range","Posted Date"]],hide_index=True)
    # Top Cities
    with tc:
        s=df["City"].value_counts().head(10)
        fig=px.bar(pd.DataFrame({"City":s.index,"Count":s.values}),x="City",y="Count",color_discrete_sequence=[JOB_COLOR])
        fig.update_layout(xaxis=dict(categoryorder="total descending"),margin=dict(t=10,b=10,l=10,r=10),xaxis_fixedrange=True,yaxis_fixedrange=True)
        st.plotly_chart(fig,use_container_width=True,config={"displayModeBar":False})
        st.dataframe(df[df["City"].isin(s.index)][["Job Title","Firm","Practice Areas","City","Experience Range","Posted Date"]],hide_index=True)
    # Practice Areas
    with pa:
        counts=pd.Series([a.strip() for s in df["Practice Areas"].dropna() for a in s.split(",")]).value_counts().head(10)
        fig=px.bar(pd.DataFrame({"Practice Area":counts.index,"Count":counts.values}),x="Practice Area",y="Count",color_discrete_sequence=[JOB_COLOR])
        fig.update_layout(xaxis=dict(categoryorder="total descending"),margin=dict(t=10,b=10,l=10,r=10),xaxis_fixedrange=True,yaxis_fixedrange=True)
        st.plotly_chart(fig,use_container_width=True,config={"displayModeBar":False})
        st.dataframe(pd.DataFrame({"Practice Area":counts.index,"Count":counts.values}),hide_index=True)
    # Experience
    with exp:
        exp_df=df.dropna(subset=["Experience Range"])
        exp_df=exp_df[exp_df["Experience Range"].str.contains(r"\d",regex=True)].copy()
        if exp_df.empty:
            st.info("Experience data missing.")
        else:
            exp_df["Min Years"] = exp_df["Experience Range"].str.extract(r"(\d+)").astype(float)
            counts=exp_df["Experience Range"].value_counts()
            plot=pd.DataFrame({"Experience":counts.index,"Number":counts.values})
            plot["sort"]=plot["Experience"].str.extract(r"(\d+)").astype(float);
            plot=plot.sort_values("sort")[["Experience","Number"]]
            fig=px.bar(plot,x="Experience",y="Number",color_discrete_sequence=[JOB_COLOR])
            fig.update_layout(margin=dict(t=10,b=10,l=10,r=10),xaxis_fixedrange=True,yaxis_fixedrange=True)
            st.plotly_chart(fig,use_container_width=True,config={"displayModeBar":False})
            st.dataframe(exp_df.sort_values("Min Years")[["Job Title","Firm","Practice Areas","City","Experience Range","Posted Date"]],hide_index=True)

# ---------------------------------------------------------------------------
# ATTORNEY PLACEMENTS TAB
# ---------------------------------------------------------------------------
with atty_tab:
    period=st.selectbox("Select Time Period",["Last 1 month","Last 2 months","Last 3 months","Last 6 months"],index=2,key="ap")
    period_days={"Last 1 month":30,"Last 2 months":60,"Last 3 months":90,"Last 6 months":180}[period]
    role_type=st.radio("Select Attorney Type",["Partners","Associates"],horizontal=True,key="role")

    if "atty_raw" not in st.session_state:
        key="partners" if role_type=="Partners" else "associates"
        st.session_state.atty_raw=fetch_attorneys(key,period_days)
    st.text(f"{len(st.session_state.atty_raw)} Placement Records")

    atty_df=pd.DataFrame([extract_attorney(a) for a in st.session_state.atty_raw])
    if not atty_df.empty and not amlaw_df.empty:
        atty_df["Firm ID"]=pd.to_numeric(atty_df["Firm ID"],errors="coerce")
        mapping=dict(zip(amlaw_df["FP ID - Firm"],amlaw_df["AmLaw Rank"]))
        mask=atty_df["Am Law Ranking"].isna()
        atty_df.loc[mask,"Am Law Ranking"]=atty_df.loc[mask,"Firm ID"].map(mapping).astype("Int64")

    if atty_df.empty:
        st.warning("No placement data."); st.stop()

    # filters
    c1,c2,c3=st.columns(3)
    with c1:
        amlaw_f=st.selectbox("Filter by Am Law Ranking",["All Firms","Am Law 50","Am Law 100"],key="af")
    with c2:
        region_f=st.selectbox("Filter by Region",["California Only","Washington Only","All Regions"],index=2,key="rf")
    with c3:
        areas=sorted({a.strip() for s in atty_df["Practice Areas"].dropna() for a in s.split(",")})
        pa_f=st.selectbox("Filter by Practice Area",["All Practice Areas"]+areas,key="pf")

    df=atty_df.copy()
    if amlaw_f=="Am Law 50": df=df[df["Am Law Ranking"].notna() & (df["Am Law Ranking"]<=50)]
    elif amlaw_f=="Am Law 100": df=df[df["Am Law Ranking"].notna() & (df["Am Law Ranking"]<=100)]
    if region_f.startswith("California"): df=df[df["Region"]=="California"]
    elif region_f.startswith("Washington"): df=df[df["Region"]=="Washington"]
    if pa_f!="All Practice Areas": df=df[df["Practice Areas"].str.contains(pa_f,na=False)]
    if df.empty: st.warning("No placements after filters."); st.stop()

    tf,tc,pa,exp=st.tabs(["Top Firms","Top Cities","Practice Areas","Experience"])

    # --- Top Firms (destination or departure) -------------------------------
    with tf:
        view=st.selectbox("Select View",["Top Destination Firms","Top Departure Firms"],index=0)
        if view.startswith("Top Destination"):
            s=df["To Firm"].value_counts().head(10)
            title_var="To Firm"
        else:
            s=df["From Firm"].value_counts().head(10)
            title_var="From Firm"
        fig=px.bar(pd.DataFrame({"Firm":s.index,"Count":s.values}),x="Firm",y="Count",color_discrete_sequence=[ATTY_COLOR])
        fig.update_layout(xaxis=dict(categoryorder="total descending"),margin=dict(t=10,b=10,l=10,r=10),xaxis_fixedrange=True,yaxis_fixedrange=True)
        st.plotly_chart(fig,use_container_width=True,config={"displayModeBar":False})
        cols=["Name","From Firm","To Firm","Practice Areas","City","Title","Move Date"]
        st.dataframe(df[df[title_var].isin(s.index)][cols],hide_index=True)

    # --- Top Cities ---------------------------------------------------------
    with tc:
        s=df["City"].value_counts().head(10)
        fig=px.bar(pd.DataFrame({"City":s.index,"Count":s.values}),x="City",y="Count",color_discrete_sequence=[ATTY_COLOR])
        fig.update_layout(xaxis=dict(categoryorder="total descending"),margin=dict(t=10,b=10,l=10,r=10),xaxis_fixedrange=True,yaxis_fixedrange=True)
        st.plotly_chart(fig,use_container_width=True,config={"displayModeBar":False})
        st.dataframe(df[df["City"].isin(s.index)][["Name","From Firm","To Firm","Practice Areas","City","Title","Move Date"]],hide_index=True)

    # --- Practice Areas -----------------------------------------------------
    with pa:
        counts=pd.Series([a.strip() for s in df["Practice Areas"].dropna() for a in s.split(",")]).value_counts().head(10)
        fig=px.bar(pd.DataFrame({"Practice Area":counts.index,"Count":counts.values}),x="Practice Area",y="Count",color_discrete_sequence=[ATTY_COLOR])
        fig.update_layout(xaxis=dict(categoryorder="total descending"),margin=dict(t=10,b=10,l=10,r=10),xaxis_fixedrange=True,yaxis_fixedrange=True)
        st.plotly_chart(fig,use_container_width=True,config={"displayModeBar":False})
        st.dataframe(pd.DataFrame({"Practice Area":counts.index,"Count":counts.values}),hide_index=True)

    # --- Experience ---------------------------------------------------------
    with exp:
        current_year=datetime.now().year
        df["Graduation Year"]=pd.to_numeric(df["Graduation Year"],errors="coerce")
        exp_df=df.dropna(subset=["Graduation Year"]).copy()
        exp_df["Experience Years"]=current_year-exp_df["Graduation Year"]
        if exp_df.empty:
            st.info("No experience data available.")
        else:
            bins=[0,3,5,8,10,15,20,50]
            labels=["0-3 years","3-5 years","5-8 years","8-10 years","10-15 years","15-20 years","20+ years"]
            exp_df["Experience Bracket"]=pd.cut(exp_df["Experience Years"],bins=bins,labels=labels,right=False)
            counts=exp_df["Experience Bracket"].value_counts().sort_index()
            plot=pd.DataFrame({"Experience":counts.index,"Count":counts.values})
            fig=px.bar(plot,x="Experience",y="Count",color_discrete_sequence=[ATTY_COLOR])
            fig.update_layout(margin=dict(t=10,b=10,l=10,r=10),xaxis_fixedrange=True,yaxis_fixedrange=True)
            st.plotly_chart(fig,use_container_width=True,config={"displayModeBar":False})
            cols=["Name","From Firm","To Firm","Practice Areas","Graduation Year","Experience Years","Experience Bracket","Move Date"]
            st.dataframe(exp_df[cols].sort_values("Experience Years",ascending=False),hide_index=True)
