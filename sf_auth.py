import requests
import streamlit as st

def authenticate_salesforce():
    # These should be set in .streamlit/secrets.toml or env vars
    client_id     = st.secrets["SALESFORCE"]["CLIENT_ID"]
    client_secret = st.secrets["SALESFORCE"]["CLIENT_SECRET"]
    username      = st.secrets["SALESFORCE"]["USERNAME"]
    password      = st.secrets["SALESFORCE"]["PASSWORD"]
    security_token= st.secrets["SALESFORCE"]["SECURITY_TOKEN"]
    auth_url      = st.secrets["SALESFORCE"]["AUTH_URL"]

    data = {
        "grant_type": "password",
        "client_id": client_id,
        "client_secret": client_secret,
        "username": username,
        "password": password + security_token,
    }
    resp = requests.post(auth_url, data=data)
    resp.raise_for_status()
    result = resp.json()
    return result["access_token"], result["instance_url"]
