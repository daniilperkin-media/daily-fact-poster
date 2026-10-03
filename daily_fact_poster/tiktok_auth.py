import os
import re
import urllib.parse

import requests
from dotenv import load_dotenv

from .constants import (
    PLACEHOLDER_TIKTOK_CLIENT_KEY,
    PLACEHOLDER_TIKTOK_CLIENT_SECRET,
    PLACEHOLDER_TIKTOK_REFRESH_TOKEN,
    is_unset_secret,
)
from .logger import get_logger
from .paths import REPO_ROOT

log = get_logger()


def update_env_file(key: str, value: str) -> None:
    """Update a specific key in the project's .env file safely."""
    env_file = os.path.join(REPO_ROOT, ".env")
    if not os.path.exists(env_file):
        with open(env_file, "w") as f:
            f.write("")

    with open(env_file) as f:
        lines = f.readlines()

    key_found = False
    with open(env_file, "w") as f:
        for line in lines:
            if line.startswith(f"{key}="):
                f.write(f"{key}={value}\n")
                key_found = True
            else:
                f.write(line)
        if not key_found:
            f.write(f"\n{key}={value}\n")

def refresh_access_token() -> str | None:
    """
    Exchange the stored refresh token for a fresh access token.

    TikTok user access tokens expire after roughly 24 hours; the refresh
    token is long-lived (and rotates on every use), so this keeps scheduled
    runs working without manual re-authorization. Updated values are
    persisted to .env and os.environ (used automatically by tiktok_poster).

    Returns:
        The new access token, or None when a refresh is not possible.
    """
    client_key = os.environ.get("TIKTOK_CLIENT_KEY", "").strip()
    client_secret = os.environ.get("TIKTOK_CLIENT_SECRET", "").strip()
    refresh_token = os.environ.get("TIKTOK_REFRESH_TOKEN", "").strip()

    if (
        is_unset_secret(client_key, PLACEHOLDER_TIKTOK_CLIENT_KEY)
        or is_unset_secret(client_secret, PLACEHOLDER_TIKTOK_CLIENT_SECRET)
        or is_unset_secret(refresh_token, PLACEHOLDER_TIKTOK_REFRESH_TOKEN)
    ):
        log.info("TikTok token refresh skipped: client credentials or refresh token missing.")
        return None

    try:
        response = requests.post(
            "https://open.tiktokapis.com/v2/oauth/token/",
            data={
                "client_key": client_key,
                "client_secret": client_secret,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
    except requests.RequestException as e:
        log.warning(f"TikTok token refresh request failed: {e}")
        return None

    if response.status_code != 200:
        log.warning(f"TikTok token refresh failed ({response.status_code}): {response.text[:200]}")
        return None

    data = response.json()
    access_token = data.get("access_token", "")
    if not access_token:
        log.warning("TikTok token refresh response contained no access_token.")
        return None

    new_refresh = data.get("refresh_token") or refresh_token
    os.environ["TIKTOK_ACCESS_TOKEN"] = access_token
    os.environ["TIKTOK_REFRESH_TOKEN"] = new_refresh
    try:
        update_env_file("TIKTOK_ACCESS_TOKEN", access_token)
        update_env_file("TIKTOK_REFRESH_TOKEN", new_refresh)
    except OSError as e:
        log.warning(f"Refreshed tokens could not be persisted to .env: {e}")

    log.info("TikTok access token refreshed successfully.")
    return access_token


def main():
    print("==================================================")
    print("      TikTok OAuth 2.0 Token Generator            ")
    print("==================================================")

    load_dotenv()

    client_key = os.environ.get("TIKTOK_CLIENT_KEY", "").strip()
    client_secret = os.environ.get("TIKTOK_CLIENT_SECRET", "").strip()

    if not client_key or not client_secret:
        print("❌ Error: TIKTOK_CLIENT_KEY or TIKTOK_CLIENT_SECRET not found in .env!")
        print("Please add them to your .env file first.")
        return

    # A registered redirect URI in your TikTok Developer Portal is required.
    # Often, developers use localhost or 127.0.0.1 for local testing.
    redirect_uri = input("\nWhat is your registered Redirect URI? (Press Enter for 'https://127.0.0.1/'): ").strip()
    if not redirect_uri:
        redirect_uri = "https://127.0.0.1/"

    # URL-encode the redirect URI
    encoded_redirect_uri = urllib.parse.quote(redirect_uri, safe='')

    # Construct the Authorization URL
    # Using video.publish which is the standard scope for Direct Post API v2
    auth_url = (
        f"https://www.tiktok.com/v2/auth/authorize/"
        f"?client_key={client_key}"
        f"&scope=video.publish,video.upload"
        f"&response_type=code"
        f"&redirect_uri={encoded_redirect_uri}"
    )

    print("\n[STEP 1] Open the following URL in your web browser:")
    print("-" * 60)
    print(auth_url)
    print("-" * 60)
    print("\nLog in to TikTok and click 'Authorize'.")
    print(f"You will be redirected to a page that starts with {redirect_uri}")
    print("It might look like it's broken or failed to load. That is normal!")

    print("\n[STEP 2] Copy the ENTIRE URL from your browser's address bar and paste it below:")
    redirected_url = input("> ").strip()

    if not redirected_url:
        print("❌ No URL provided. Aborting.")
        return

    # Extract the 'code' parameter from the URL
    try:
        parsed_url = urllib.parse.urlparse(redirected_url)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        code = query_params.get("code", [None])[0]

        if not code:
            # Fallback regex just in case
            match = re.search(r'code=([^&]+)', redirected_url)
            if match:
                code = match.group(1)

        if not code:
            print("❌ Could not find 'code' in the provided URL. Please try again.")
            return

    except Exception as e:
        print(f"❌ Error parsing URL: {e}")
        return

    # Decode the code because it is URL-encoded
    code = urllib.parse.unquote(code)
    print(f"\n✅ Extracted Authorization Code: {code[:5]}...{code[-5:]}")

    print("\n[STEP 3] Exchanging code for Access Token...")

    token_url = "https://open.tiktokapis.com/v2/oauth/token/"

    # TikTok OAuth v2 requires form-urlencoded data
    payload = {
        "client_key": client_key,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Cache-Control": "no-cache"
    }

    try:
        response = requests.post(token_url, data=payload, headers=headers)
        data = response.json()

        if response.status_code == 200 and "access_token" in data:
            access_token = data["access_token"]
            refresh_token = data.get("refresh_token", "")

            print("\n🎉 Success! Tokens received.")
            print(f"Access Token:  {access_token[:15]}...")
            print(f"Refresh Token: {refresh_token[:15]}...")

            print("\n[STEP 4] Automatically saving tokens to .env file...")
            update_env_file("TIKTOK_ACCESS_TOKEN", access_token)
            update_env_file("TIKTOK_REFRESH_TOKEN", refresh_token)
            print("✅ .env file updated successfully! You can now run main.py.")

        else:
            print(f"\n❌ Failed to get tokens (Status {response.status_code}).")
            print(f"Response: {data}")

    except Exception as e:
        print(f"\n❌ Request failed: {e}")

if __name__ == "__main__":
    main()
