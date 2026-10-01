"""Google OAuth 2.0。

預設：沿用 google_tokens.json，過期自動 refresh，沒有才開瀏覽器。
force=True（--reauth）：忽略既有 token，重新開瀏覽器授權（demo 用）。
"""
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow


def get_access_token(client_secret_file: Path, token_file: Path, scopes: list[str], force: bool = False) -> str:
    creds = None
    if not force and token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), scopes)
        if creds.valid:
            return creds.token
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            token_file.write_text(creds.to_json())
            return creds.token

    if not client_secret_file.exists():
        raise FileNotFoundError(
            f"找不到 {client_secret_file}。請在 Google Cloud Console 建立 OAuth client（Desktop app），"
            "下載 JSON 後放到專案根目錄。")
    flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_file), scopes)
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
    token_file.write_text(creds.to_json())
    return creds.token
