"""
Google Drive API v3.
Auth priority: OAuth user credentials (oauth-token.json) → service account.
OAuth avoids the "Service Accounts do not have storage quota" error on
personal Drive; SA is used as fallback when no OAuth token is present.
All API calls auto-retry on transient errors (HTTP 429/5xx, network blips).
"""
import io
import json
import logging
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

from src.utils.retry import with_retries

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive"]
GOOGLE_DOC_MIME = "application/vnd.google-apps.document"
FOLDER_MIME = "application/vnd.google-apps.folder"


class DriveAPI:
    def __init__(self, settings):
        self.settings = settings
        self.service = self._init()
        self._folder_cache: dict = {}

    def _init(self):
        oauth_file = getattr(self.settings, "GOOGLE_OAUTH_TOKEN_FILE", "oauth-token.json")
        if Path(oauth_file).exists():
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            with open(oauth_file) as f:
                token_data = json.load(f)
            creds = Credentials(
                token=token_data.get("token"),
                refresh_token=token_data["refresh_token"],
                token_uri=token_data["token_uri"],
                client_id=token_data["client_id"],
                client_secret=token_data["client_secret"],
                scopes=token_data.get("scopes", SCOPES),
            )
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
            logger.info("✅ Google Drive API initialized (OAuth)")
            return build("drive", "v3", credentials=creds, cache_discovery=False)

        creds = service_account.Credentials.from_service_account_file(
            self.settings.GOOGLE_SERVICE_ACCOUNT_FILE, scopes=SCOPES
        )
        logger.info("✅ Google Drive API initialized (service account)")
        return build("drive", "v3", credentials=creds, cache_discovery=False)

    @with_retries
    def _get_meta(self, file_id: str) -> dict:
        return self.service.files().get(
            fileId=file_id, fields="mimeType,name"
        ).execute()

    @with_retries
    def _export(self, file_id: str, mime: str = "text/plain") -> bytes:
        return self.service.files().export(
            fileId=file_id, mimeType=mime
        ).execute()

    @with_retries
    def _get_media(self, file_id: str) -> bytes:
        return self.service.files().get_media(fileId=file_id).execute()

    @with_retries
    def _list(self, q: str, fields: str = "files(id, name)", page_size: int = 20):
        return self.service.files().list(
            q=q, fields=fields, pageSize=page_size
        ).execute()

    @with_retries
    def _create(self, body: dict, media=None, fields: str = "id"):
        kwargs = {"body": body, "fields": fields}
        if media is not None:
            kwargs["media_body"] = media
        return self.service.files().create(**kwargs).execute()

    @with_retries
    def _update(self, file_id: str, media, fields: str = "id"):
        return self.service.files().update(
            fileId=file_id, media_body=media, fields=fields
        ).execute()

    def download_file(self, file_id: str) -> str:
        try:
            meta = self._get_meta(file_id)
            if meta.get("mimeType") == GOOGLE_DOC_MIME:
                content = self._export(file_id, "text/plain")
            else:
                content = self._get_media(file_id)
            return content.decode("utf-8")
        except Exception as e:
            logger.error(f"Download failed ({file_id}): {e}")
            return ""

    def file_exists(self, name: str, folder_id: str) -> bool:
        name_esc = name.replace("\\", "\\\\").replace("'", "\\'")
        q = (f"name='{name_esc}' and '{folder_id}' in parents "
             f"and trashed=false")
        try:
            res = self._list(q, fields="files(id)", page_size=1)
            return len(res.get("files", [])) > 0
        except Exception as e:
            logger.error(f"file_exists check failed: {e}")
            return False

    def upload(self, filename: str, content: str | bytes,
               folder_id: str, mime_type: str = "text/html",
               skip_if_exists: bool = True) -> str | None:
        if skip_if_exists and self.file_exists(filename, folder_id):
            logger.info(f"⏭️  Skipped (already exists): {filename}")
            return None
        try:
            data = content.encode("utf-8") if isinstance(content, str) else content
            meta = {"name": filename, "parents": [folder_id]}
            media = MediaIoBaseUpload(
                io.BytesIO(data), mimetype=mime_type, resumable=True
            )
            file = self._create(meta, media=media)
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
        res = self._list(q, fields="files(id)", page_size=1)
        if res["files"]:
            return res["files"][0]["id"]
        meta = {"name": name, "mimeType": FOLDER_MIME, "parents": [parent_id]}
        folder = self._create(meta)
        logger.debug(f"📁 Created folder: {name}")
        return folder.get("id")

    def update_file_content(self, file_id: str, content: str | bytes,
                            mime_type: str = "text/markdown") -> str | None:
        """Replace contents of an existing file by its Drive ID. Used by
        the calendar planner to extend the calendar in place."""
        try:
            meta = self._get_meta(file_id)
            if meta.get("mimeType") == GOOGLE_DOC_MIME:
                mime_type = "text/plain"
            data = content.encode("utf-8") if isinstance(content, str) else content
            media = MediaIoBaseUpload(
                io.BytesIO(data), mimetype=mime_type, resumable=True
            )
            result = self._update(file_id, media)
            logger.info(f"♻️  Updated file content: {file_id}")
            return result.get("id")
        except Exception as e:
            logger.error(f"update_file_content failed ({file_id}): {e}")
            return None

    def update_or_create(self, filename: str, content: str | bytes,
                         folder_id: str, mime_type: str = "text/markdown") -> str | None:
        """Upload a file, replacing any existing one with the same name in the
        same folder. Used for auto-generated artifacts (indexes) that should
        always reflect the latest state."""
        try:
            data = content.encode("utf-8") if isinstance(content, str) else content
            media = MediaIoBaseUpload(
                io.BytesIO(data), mimetype=mime_type, resumable=True
            )
            name_esc = filename.replace("\\", "\\\\").replace("'", "\\'")
            q = (f"name='{name_esc}' and '{folder_id}' in parents "
                 f"and trashed=false")
            res = self._list(q, fields="files(id)", page_size=1)
            if res.get("files"):
                file_id = res["files"][0]["id"]
                self._update(file_id, media)
                logger.info(f"♻️  Updated: {filename}")
                return file_id
            file = self._create({"name": filename, "parents": [folder_id]}, media=media)
            logger.info(f"✅ Created: {filename}")
            return file.get("id")
        except Exception as e:
            logger.error(f"update_or_create failed ({filename}): {e}")
            return None

    def walk(self, folder_id: str, _path: str = "") -> list[dict]:
        """Recursively list all files under folder_id. Returns a flat list of
        {path, name, id, mimeType, parent_path}."""
        try:
            res = self._list(
                f"'{folder_id}' in parents and trashed=false",
                fields="files(id, name, mimeType)", page_size=200,
            )
        except Exception as e:
            logger.error(f"walk failed at {folder_id}: {e}")
            return []
        items = []
        for f in res.get("files", []):
            here = f"{_path}/{f['name']}" if _path else f["name"]
            if f["mimeType"] == FOLDER_MIME:
                items.extend(self.walk(f["id"], here))
            else:
                items.append({
                    "path": here, "name": f["name"], "id": f["id"],
                    "mime": f["mimeType"], "parent_path": _path,
                })
        return items

    def list_files_by_prefix(self, name_prefix: str) -> list:
        prefix_esc = name_prefix.replace("\\", "\\\\").replace("'", "\\'")
        q = f"name contains '{prefix_esc}' and trashed=false"
        try:
            res = self._list(q, fields="files(id, name)", page_size=20)
            return res.get("files", [])
        except Exception as e:
            logger.error(f"List files error: {e}")
            return []

    def check_access(self, file_or_folder_id: str) -> tuple[bool, str]:
        """Returns (ok, name_or_error_msg). Used for startup pre-flight checks."""
        if not file_or_folder_id:
            return False, "id is empty"
        try:
            meta = self._get_meta(file_or_folder_id)
            return True, meta.get("name", "?")
        except Exception as e:
            return False, str(e)
