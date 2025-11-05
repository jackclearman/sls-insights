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
    try:
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        # Log response for debugging
        print(f"[DEBUG] Salesforce auth failed: {e}\nURL: {auth_url}\nResponse: {resp.text}")
        raise
    try:
        result = resp.json()
    except ValueError:
        print(f"[DEBUG] Salesforce auth returned non-JSON response:\n{resp.text}")
        raise
    return result.get("access_token"), result.get("instance_url")
