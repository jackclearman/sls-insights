import os
from datetime import datetime, timedelta

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

# ──────────────────────────────────────────────────────────────────────────────
# SLS Insights Dashboard  (2025‑05‑11)
#   • robust None‑handling in extract_attorney (fixes recent_move=None crash)
#   • plain‑text counts, AmLaw filters, full Experience tabs & detail tables
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
    """Safely turn an attorney JSON blob into a flat dict.
    Handles cases where `a` itself is None or missing sub-objects.
    """
    if not isinstance(a, dict):  # guard against unexpected None values
        return {}

    recent = a.get("recent_move") or {}
    move   = recent.get("firm") or {}
    firm   = a.get("firm") or {}
    ranks  = firm.get("ranks") or {}

    return {
        "Name": f"{a.get('first_name','')} {a.get('last_name','')}",
        "From Firm": move.get("old", {}).get("firm_name"),
        "To Firm":   move.get("new", {}).get("firm_name"),
        "Practice Areas": ", ".join(a.get("attorneys_practice_areas", []) or []),
        "Specialties":    ", ".join(a.get("attorneys_specialties",   []) or []),
        "City":            (a.get("location") or {}).get("city"),
        "Graduation Year": a.get("graduation_year"),
        "Law School":      (a.get("law_school") or {}).get("law_school_name"),
        "Current Firm":    firm.get("firm_name"),
        "Title":           ", ".join(a.get("attorneys_titles", []) or []),
        "FirmProspects ID": a.get("id"),
        "Profile Link":    f"[Link](https://engage.firmprospects.com/attorneys/profile/{a.get('id')})",
        "Am Law Ranking":  ranks.get("top200"),
        "Region":          (a.get("location") or {}).get("state"),
        "Move Date":       recent.get("date"),
        "Firm ID":         firm.get("id"),
    } {"Name":f"{a.get('first_name','')} {a.get('last_name','')}",
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
# UI LAYOUT (unchanged below)
# ──────────────────────────────────────────────────────────────────────────────

amlaw_df=load_amlaw_data()
job_tab,atty_tab=st.tabs(["Job Postings","Attorney Placements"])
# (rest of file unchanged from previous version)
