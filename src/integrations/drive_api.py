"""
Google Drive API v3 — upload files, create folders, download content.
Uses OAuth 2.0 (credentials.json → token.json).
"""
import io
import logging
from pathlib import Path
from typing import Optional

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request as AuthRequest
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

logger = logging.getLogger(__name__)
SCOPES = ["https://www.googleapis.com/auth/drive"]


class DriveAPI:
    def __init__(self, settings):
        self.settings = settings
        self.service = self._init()
        self._folder_cache: dict = {}
        logger.info("✅ Google Drive API initialized")

    def _init(self):
        creds = None
        token_path = Path(self.settings.GOOGLE_TOKEN_FILE)
        creds_path = Path(self.settings.GOOGLE_CREDENTIALS_FILE)

        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(AuthRequest())
        elif not creds or not creds.valid:
            flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
            creds = flow.run_local_server(port=0)
            token_path.write_text(creds.to_json())
        return build("drive", "v3", credentials=creds)

    def download_file(self, file_id: str) -> str:
        try:
            return self.service.files().get_media(fileId=file_id).execute().decode("utf-8")
        except Exception as e:
            logger.error(f"Download failed ({file_id}): {e}")
            return ""

    def upload(self, filename: str, content: str, folder_id: str,
               mime_type: str = "text/html") -> Optional[str]:
        try:
            meta = {"name": filename, "parents": [folder_id]}
            media = MediaIoBaseUpload(
                io.BytesIO(content.encode("utf-8")),
                mimetype=mime_type, resumable=True
            )
            file = self.service.files().create(
                body=meta, media_body=media, fields="id"
            ).execute()
            logger.info(f"✅ Uploaded: {filename}")
            return file.get("id")
        except Exception as e:
            logger.error(f"Upload failed ({filename}): {e}")
            return None

    def get_or_create_folder(self, path: str, root_id: str) -> str:
        cache_key = f"{root_id}:{path}"
        if cache_key in self._folder_cache:
            return self._folder_cache[cache_key]
        current_id = root_id
        for part in path.strip("/").split("/"):
            current_id = self._get_or_create_single(part, current_id)
        self._folder_cache[cache_key] = current_id
        return current_id

    def _get_or_create_single(self, name: str, parent_id: str) -> str:
        q = (f"name='{name}' and '{parent_id}' in parents "
             f"and mimeType='application/vnd.google-apps.folder' and trashed=false")
        res = self.service.files().list(q=q, fields="files(id)", pageSize=1).execute()
        if res["files"]:
            return res["files"][0]["id"]
        meta = {"name": name,
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [parent_id]}
        folder = self.service.files().create(body=meta, fields="id").execute()
        logger.debug(f"📁 Created folder: {name}")
        return folder.get("id")

    def list_files_by_prefix(self, name_prefix: str) -> list:
        q = f"name contains '{name_prefix}' and trashed=false"
        try:
            res = self.service.files().list(
                q=q, fields="files(id, name)", pageSize=20
            ).execute()
            return res.get("files", [])
        except Exception as e:
            logger.error(f"List files error: {e}")
            return []
