import requests
import string
import random
from .sf_auth import authenticate_salesforce

def generate_candidate_password(candidate_name):
    """Generate password: first 4 characters of last name + 5 deterministic characters/symbols"""
    try:
        # Get last name (assume format: "First Last" or "First Middle Last")
        name_parts = candidate_name.strip().split()
        last_name = name_parts[-1] if name_parts else "USER"
        
        # First 4 characters of last name (pad with 'X' if shorter)
        first_part = (last_name[:4]).ljust(4, 'X')
        
        # Generate 5 deterministic characters based on the candidate name
        # This ensures the same password is generated every time for the same name
        import hashlib
        name_hash = hashlib.md5(candidate_name.encode()).hexdigest()
        chars = string.ascii_letters + string.digits + "!@#$%&*"
        
        # Use hash to pick 5 characters deterministically
        deterministic_part = ""
        for i in range(5):
            index = int(name_hash[i*2:i*2+2], 16) % len(chars)
            deterministic_part += chars[index]
        
        return first_part + deterministic_part
    except:
        # Fallback password if name parsing fails
        return "USER12345"

def salesforce_query(soql):
    access_token, instance_url = authenticate_salesforce()
    headers = {"Authorization": f"Bearer {access_token}"}
    url = f"{instance_url}/services/data/v57.0/query"
    resp = requests.get(url, headers=headers, params={"q": soql})
    try:
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        print(f"[DEBUG] Salesforce query failed: {e}\nURL: {url}\nSOQL: {soql}\nResponse: {resp.text}")
        raise
    return resp.json()["records"]

def get_engaged_candidates():
    soql = (
        "SELECT Id, Name, OwnerId "
        "FROM Account "
        "WHERE Status__c = 'Active/Green Flag'"
    )
    return salesforce_query(soql)

def get_candidate_by_token(token):
    # token is the Account ID directly
    soql = (
        "SELECT Id, Name, OwnerId "
        "FROM Account "
        "WHERE Id = '{token}' AND Status__c = 'Active/Green Flag'"
    ).format(token=token)
    records = salesforce_query(soql)
    return records[0] if records else None

def get_opportunities_for_candidate(candidate_id):
    # candidate_id is Account.Id, match to Opportunity.Candidate__c
    print(f"[DEBUG] get_opportunities_for_candidate: candidate_id={candidate_id}")
    
    soql = (
        "SELECT Id, Name, Account_Name__c, StageName, Open_Job__c, Open_Job__r.Name, Candidate_User_Id__c, Status__c "
        "FROM Opportunity "
        f"WHERE Candidate__c = '{candidate_id}'"
    )
    print(f"[DEBUG] SOQL: {soql}")
    results = salesforce_query(soql)
    print(f"[DEBUG] Opportunities found: {results}")
    return results

def get_all_candidates():
    soql = "SELECT Id, Name FROM Account WHERE Status__c = 'Active/Green Flag'"
    return salesforce_query(soql)

def get_candidates_for_recruiter(owner_id):
    # Update to use Account object, assuming candidates are Accounts with a custom Status__c field and OwnerId
    soql = (
        "SELECT Id, Name, Status__c "
        "FROM Account "
        "WHERE Status__c = 'Active/Green Flag' AND OwnerId = '{owner_id}'"
    ).format(owner_id=owner_id)
    return salesforce_query(soql)

def get_engaged_candidates_for_admin():
    soql = (
        "SELECT Id, Name, Public_Token__c, OwnerId "
        "FROM Candidate__c "
        "WHERE Account.Status__c = 'Active/Green Flag'"
    )
    return salesforce_query(soql)
