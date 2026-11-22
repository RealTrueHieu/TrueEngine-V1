import os
import sys
import json
from importlib import resources
import keyring
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials

PUBLIC_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/colaboratory",
    "https://www.googleapis.com/auth/drive.file",
]

REMOTE_REDIRECT_URI = "https://sdk.cloud.google.com/applicationdefaultauthcode.html"
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "colab_flow_state.json")
TOKEN_PATH = os.path.expanduser("~/.config/colab-cli/token.json")
KEYRING_SERVICE_NAME = "google-colab-cli"
KEYRING_USERNAME = "oauth_token"

def get_client_config():
    config_resource = resources.files("colab_cli").joinpath("oauth_config.json")
    return json.loads(config_resource.read_text())

def generate_login_url():
    client_config = get_client_config()
    flow = InstalledAppFlow.from_client_config(client_config, PUBLIC_SCOPES)
    flow.redirect_uri = REMOTE_REDIRECT_URI
    auth_url, _ = flow.authorization_url(prompt="consent", token_usage="remote")

    state_data = {
        "code_verifier": flow.code_verifier,
        "auth_url": auth_url
    }
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state_data, f, indent=2)

    return auth_url

def exchange_auth_code(auth_code: str):
    if not os.path.exists(STATE_FILE):
        raise FileNotFoundError("Flow state not found. Please generate login URL first.")

    with open(STATE_FILE, "r", encoding="utf-8") as f:
        state_data = json.load(f)

    code_verifier = state_data["code_verifier"]
    client_config = get_client_config()

    flow = InstalledAppFlow.from_client_config(client_config, PUBLIC_SCOPES)
    flow.redirect_uri = REMOTE_REDIRECT_URI
    flow.code_verifier = code_verifier

    flow.fetch_token(code=auth_code.strip())
    creds = flow.credentials

    # Save to ~/.config/colab-cli/token.json
    os.makedirs(os.path.dirname(TOKEN_PATH), exist_ok=True)
    creds_json = creds.to_json()
    with open(TOKEN_PATH, "w", encoding="utf-8") as f:
        f.write(creds_json)

    # Save to keyring
    try:
        keyring.set_password(KEYRING_SERVICE_NAME, KEYRING_USERNAME, creds_json)
        print("[Keyring] Successfully saved token to OS Keyring.")
    except Exception as e:
        print(f"[Keyring Warning] Could not save to keyring: {e}")

    print(f"[File] Successfully saved token to {TOKEN_PATH}.")
    return True

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--exchange":
        if len(sys.argv) < 3:
            print("Usage: python colab_auth_tool.py --exchange <AUTH_CODE>")
            sys.exit(1)
        code = sys.argv[2]
        exchange_auth_code(code)
    else:
        url = generate_login_url()
        print("LOGIN_URL:" + url)
