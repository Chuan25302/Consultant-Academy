"""
Google Drive API v3 — service account auth (headless-friendly).
Folders must be shared with the service account email (write access).
"""
import io
import logging
from typing import Optional, Union

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive"]
GOOGLE_DOC_MIME = "application/vnd.google-apps.document"
FOLDER_MIME = "application/vnd.google-apps.folder"


class DriveAPI:
    def __init__(self, settings):
        self.settings = settings
        self.service = self._init()
        self._folder_cache: dict = {}
        logger.info("✅ Google Drive API initialized (service account)")

    def _init(self):
        creds = service_account.Credentials.from_service_account_file(
            self.settings.GOOGLE_SERVICE_ACCOUNT_FILE, scopes=SCOPES
        )
        return build("drive", "v3", credentials=creds, cache_discovery=False)

    def download_file(self, file_id: str) -> str:
        try:
            meta = self.service.files().get(
                fileId=file_id, fields="mimeType,name"
            ).execute()
            if meta.get("mimeType") == GOOGLE_DOC_MIME:
                content = self.service.files().export(
                    fileId=file_id, mimeType="text/plain"
                ).execute()
            else:
                content = self.service.files().get_media(fileId=file_id).execute()
            return content.decode("utf-8")
        except Exception as e:
            logger.error(f"Download failed ({file_id}): {e}")
            return ""

    def file_exists(self, name: str, folder_id: str) -> bool:
        name_esc = name.replace("\\", "\\\\").replace("'", "\\'")
        q = (f"name='{name_esc}' and '{folder_id}' in parents "
             f"and trashed=false")
        try:
            res = self.service.files().list(
                q=q, fields="files(id)", pageSize=1
            ).execute()
            return len(res.get("files", [])) > 0
        except Exception as e:
            logger.error(f"file_exists check failed: {e}")
            return False

    def upload(self, filename: str, content: Union[str, bytes],
               folder_id: str, mime_type: str = "text/html",
               skip_if_exists: bool = True) -> Optional[str]:
        if skip_if_exists and self.file_exists(filename, folder_id):
            logger.info(f"⏭️  Skipped (already exists): {filename}")
            return None
        try:
            data = content.encode("utf-8") if isinstance(content, str) else content
            meta = {"name": filename, "parents": [folder_id]}
            media = MediaIoBaseUpload(
                io.BytesIO(data), mimetype=mime_type, resumable=True
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
        name_esc = name.replace("\\", "\\\\").replace("'", "\\'")
        q = (f"name='{name_esc}' and '{parent_id}' in parents "
             f"and mimeType='{FOLDER_MIME}' and trashed=false")
        res = self.service.files().list(q=q, fields="files(id)", pageSize=1).execute()
        if res["files"]:
            return res["files"][0]["id"]
        meta = {"name": name, "mimeType": FOLDER_MIME, "parents": [parent_id]}
        folder = self.service.files().create(body=meta, fields="id").execute()
        logger.debug(f"📁 Created folder: {name}")
        return folder.get("id")

    def list_files_by_prefix(self, name_prefix: str) -> list:
        prefix_esc = name_prefix.replace("\\", "\\\\").replace("'", "\\'")
        q = f"name contains '{prefix_esc}' and trashed=false"
        try:
            res = self.service.files().list(
                q=q, fields="files(id, name)", pageSize=20
            ).execute()
            return res.get("files", [])
        except Exception as e:
            logger.error(f"List files error: {e}")
            return []
