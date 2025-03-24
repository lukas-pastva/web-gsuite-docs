import os
import re
import time
import threading

from flask import Flask, render_template
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

app = Flask(__name__)

# --- Environment Variables ---
GSUITE_FOLDER_URL = os.environ.get("GSUITE_FOLDER_URL", "")
REFRESH_INTERVAL = int(os.environ.get("REFRESH_INTERVAL", "300"))  # default 5 minutes
SERVICE_ACCOUNT_FILE = os.environ.get("SERVICE_ACCOUNT_FILE", "/var/secrets/google/service_account.json")

PAGE_TITLE = os.environ.get("PAGE_TITLE", "web-gsuite-docs")
PAGE_HEADER = os.environ.get("PAGE_HEADER", "My G Suite Folder")

# In-memory store: file_id => { name, mimeType, iframeUrl }
PUBLIC_FILES = {}

# --- Helper Functions ---

def get_folder_id_from_url(folder_url: str) -> str:
    """
    Extracts the folder ID from a typical Google Drive folder URL:
      https://drive.google.com/drive/folders/<FOLDER_ID>
    """
    match = re.search(r'/folders/([^/]+)', folder_url)
    if match:
        return match.group(1)
    return folder_url

def build_drive_service():
    """
    Build Google Drive API service using service account credentials.
    """
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=['https://www.googleapis.com/auth/drive.readonly']
    )
    return build('drive', 'v3', credentials=credentials)

def generate_iframe_url(file_id, mime_type):
    """
    Return a Google Docs/Sheets/Slides 'preview' link for embedding in an iframe.
    """
    if mime_type == 'application/vnd.google-apps.document':
        # Google Docs
        return f"https://docs.google.com/document/d/{file_id}/preview"
    elif mime_type == 'application/vnd.google-apps.spreadsheet':
        # Google Sheets
        return f"https://docs.google.com/spreadsheets/d/{file_id}/preview"
    elif mime_type == 'application/vnd.google-apps.presentation':
        # Google Slides
        return f"https://docs.google.com/presentation/d/{file_id}/preview"
    else:
        # For non-Google file types (PDF, images, etc.), no direct iframe preview
        return None

def fetch_public_files_from_folder(folder_url):
    """
    Use the Drive API to list files in the folder, build 'iframeUrl' if applicable.
    """
    folder_id = get_folder_id_from_url(folder_url)
    drive_service = build_drive_service()

    file_map = {}
    try:
        query = f"'{folder_id}' in parents and trashed=false"
        response = drive_service.files().list(
            q=query,
            fields="files(id, name, mimeType)"
        ).execute()

        for file_info in response.get('files', []):
            fid = file_info['id']
            fname = file_info['name']
            mime_type = file_info['mimeType']

            iframe_url = generate_iframe_url(fid, mime_type)

            file_map[fid] = {
                "name": fname,
                "mimeType": mime_type,
                "iframeUrl": iframe_url
            }
    except HttpError as err:
        print(f"[ERROR] Failed to list files from folder {folder_id}: {err}")

    return file_map

def refresh_file_list():
    """
    Background thread to periodically refresh the file list from Google Drive.
    """
    global PUBLIC_FILES
    while True:
        try:
            print(f"[refresh_file_list] Refreshing files from: {GSUITE_FOLDER_URL}")
            PUBLIC_FILES = fetch_public_files_from_folder(GSUITE_FOLDER_URL)
            print("[refresh_file_list] Refreshed successfully.")
        except Exception as e:
            print(f"[refresh_file_list] Error: {e}")

        time.sleep(REFRESH_INTERVAL)

# --- Flask Routes ---

@app.route("/")
def index():
    """
    Lists all files found in the folder. 
    """
    files_data = [(fid, info["name"], info["mimeType"]) for fid, info in PUBLIC_FILES.items()]
    return render_template(
        "index.html",
        page_title=PAGE_TITLE,
        page_header=PAGE_HEADER,
        files_data=files_data
    )

@app.route("/view/<file_id>")
def view_file(file_id):
    """
    If the file is a GDoc/Sheet/Slide, embed in an iframe. Otherwise, show a note.
    """
    file_data = PUBLIC_FILES.get(file_id)
    if not file_data:
        return f"File {file_id} not found or not accessible."

    return render_template(
        "view_file.html",
        page_title=PAGE_TITLE,
        page_header=PAGE_HEADER,
        file_name=file_data["name"],
        mime_type=file_data["mimeType"],
        iframe_url=file_data["iframeUrl"]
    )

# --- Main Entrypoint ---
if __name__ == "__main__":
    # Start background refresh thread
    refresh_thread = threading.Thread(target=refresh_file_list, daemon=True)
    refresh_thread.start()

    # Run the dev server (for production, use Gunicorn or similar)
    app.run(host="0.0.0.0", port=8080, debug=True)
