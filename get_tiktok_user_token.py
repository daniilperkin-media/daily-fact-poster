import os
import urllib.parse
import webbrowser

import requests
from dotenv import load_dotenv

load_dotenv()

CLIENT_KEY = os.environ.get("TIKTOK_CLIENT_KEY")
CLIENT_SECRET = os.environ.get("TIKTOK_CLIENT_SECRET")
REDIRECT_URI = "https://github.com/daniilperkin/photo-video-editing"

def get_user_token():
    if not CLIENT_KEY or not CLIENT_SECRET:
        print("❌ Please set TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET in .env first.")
        return

    # Build Auth URL
    scopes = "user.info.basic,video.upload,video.publish"
    auth_url = (
        f"https://www.tiktok.com/v2/auth/authorize/"
        f"?client_key={CLIENT_KEY}"
        f"&scope={scopes}"
        f"&response_type=code"
        f"&redirect_uri={urllib.parse.quote(REDIRECT_URI)}"
    )

    print("=" * 60)
    print("🔑 TIKTOK ONE-CLICK AUTHORIZATION TOOL")
    print("=" * 60)
    print("\nOpening TikTok login in your browser...")
    print(f"URL: {auth_url}\n")

    webbrowser.open(auth_url)

    print("1. Log in with your TikTok account (beaty4you) in the browser.")
    print("2. Click 'Authorize'.")
    print("3. You will be redirected to GitHub with a URL containing '?code=XXXXXX'.")
    print("4. Copy that 'code' from your browser URL bar and paste it below:\n")

    code = input("Paste your authorization code here: ").strip()

    if not code:
        print("❌ No code provided.")
        return

    # Clean code if user pasted full URL
    if "code=" in code:
        parsed = urllib.parse.urlparse(code)
        params = urllib.parse.parse_qs(parsed.query)
        code = params.get("code", [code])[0]

    token_url = "https://open.tiktokapis.com/v2/oauth/token/"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    payload = {
        "client_key": CLIENT_KEY,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI
    }

    print("\nExchanging code for TikTok User Access Token...")
    res = requests.post(token_url, data=payload, headers=headers, timeout=30)
    res_json = res.json()

    access_token = res_json.get("access_token")
    if access_token:
        print("\n🎉 SUCCESS! Received User Access Token!")

        # Save to .env file automatically
        env_path = os.path.join(os.path.dirname(__file__), ".env")
        with open(env_path, "a", encoding="utf-8") as f:
            f.write(f"\nTIKTOK_ACCESS_TOKEN={access_token}\n")

        print("Token automatically saved to .env as TIKTOK_ACCESS_TOKEN!")
    else:
        print(f"\n❌ Error fetching token: {res_json}")

if __name__ == "__main__":
    get_user_token()
