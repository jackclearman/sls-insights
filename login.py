import streamlit as st
import requests
import urllib.parse

def get_salesforce_secrets():
    try:
        secrets = st.secrets["SALESFORCE"]
        return secrets
    except Exception:
        st.error("Salesforce secrets not found. Please check your .streamlit/secrets.toml file.")
        return None

def get_login_url():
    secrets = get_salesforce_secrets()
    if not secrets:
        return ""
    params = {
        "response_type": "code",
        "client_id": secrets["CLIENT_ID"],
        "redirect_uri": secrets.get("SALESFORCE_REDIRECT_URI", "http://localhost:8501"),
        "scope": "openid",
    }
    return f"https://login.salesforce.com/services/oauth2/authorize?{urllib.parse.urlencode(params)}"

def exchange_code_for_token(code):
    secrets = get_salesforce_secrets()
    if not secrets:
        return None
    redirect_uri = secrets.get("SALESFORCE_REDIRECT_URI", "http://localhost:8501")
    data = {
        "grant_type": "authorization_code",
        "client_id": secrets["CLIENT_ID"],
        "client_secret": secrets["CLIENT_SECRET"],
        "redirect_uri": redirect_uri,
        "code": code,
    }
    response = requests.post(secrets["AUTH_URL"], data=data)
    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        st.error(f"Salesforce token exchange failed: {e}\nResponse: {response.text}")
        print(f"Salesforce token exchange failed: {e}\nResponse: {response.text}")
        return None
    try:
        return response.json()
    except ValueError:
        st.error(f"Salesforce token exchange returned non-JSON response:\n{response.text}")
        print(f"Salesforce token exchange returned non-JSON response:\n{response.text}")
        return None

def login_form():
    query_params = st.query_params
    if "code" in query_params:
        code = query_params["code"][0] if isinstance(query_params["code"], list) else query_params["code"]
        # Prevent accidental reuse: only exchange if not already used in session
        if st.session_state.get("last_oauth_code") == code:
            st.warning("This Salesforce login link has already been used. Please log in again if needed.")
            return False
        token_data = exchange_code_for_token(code)
        if token_data:
            st.session_state["logged_in"] = True
            st.session_state["salesforce_token"] = token_data
            # Try to fetch user info (email) from the identity URL returned by Salesforce
            access_token = token_data.get("access_token") or token_data.get("accessToken")
            id_url = token_data.get("id")
            if access_token and id_url:
                try:
                    resp = requests.get(id_url, headers={"Authorization": f"Bearer {access_token}"})
                    resp.raise_for_status()
                    try:
                        userinfo = resp.json()
                    except ValueError:
                        st.warning("Salesforce identity endpoint returned non-JSON response.")
                        userinfo = {}
                    # common fields: email, preferred_username
                    user_email = userinfo.get("email") or userinfo.get("preferred_username")
                    if user_email:
                        st.session_state["user_email"] = user_email
                        st.session_state["salesforce_user"] = userinfo
                except requests.exceptions.HTTPError as e:
                    # Non-fatal: we still have a token, but user_email won't be present until later
                    st.warning(f"Could not fetch Salesforce user info: {e}\nResponse: {getattr(resp, 'text', '')}")
                except Exception as e:
                    st.warning(f"Could not fetch Salesforce user info: {e}")
            st.session_state["last_oauth_code"] = code
            st.success("Logged in with Salesforce!")
            # Remove code from URL to prevent reuse on rerun (Streamlit >=1.32)
            st.query_params.clear()
            return True
        else:
            st.error("Failed to log in with Salesforce.")
            return False
    else:
        login_url = get_login_url()
        if login_url:
            st.markdown(f'<a href="{login_url}" target="_blank"><button>Recruiter Login with Salesforce</button></a>', unsafe_allow_html=True)
        return False
def logout_button():
    if st.button("Logout"):
        st.session_state.clear()  # Clear all session state keys
        st.rerun()

def debug_secrets():
    try:
        secrets = st.secrets["SALESFORCE"]
        st.write("Secrets loaded successfully:", secrets)
    except KeyError:
        st.error("Salesforce secrets not found.")

# Call debug_secrets at the top level for testing
if __name__ == "__main__":
    debug_secrets()
