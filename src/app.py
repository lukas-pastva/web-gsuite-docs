import os
import time
import json
import threading

from flask import Flask, render_template

app = Flask(__name__)

# Environment Variables
DATA_JSON_PATH = os.environ.get("DATA_JSON_PATH", "/tmp/files.json")
REFRESH_INTERVAL = int(os.environ.get("REFRESH_INTERVAL", "300"))  # default 5 minutes

PAGE_TITLE = os.environ.get("PAGE_TITLE", "web-gsuite-docs")
PAGE_HEADER = os.environ.get("PAGE_HEADER", "My G Suite Folder")

# In-memory store: { file_id: { name, mimeType, iframeUrl } }
PUBLIC_FILES = {}

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
        return None

def load_files_from_json():
    """
    Load JSON from DATA_JSON_PATH and build the in-memory PUBLIC_FILES dict.
    JSON structure: [
      { "id": "<file_id>", "name": "<file_name>", "mimeType": "<mime_type>" },
      ...
    ]
    """
    global PUBLIC_FILES

    if not os.path.exists(DATA_JSON_PATH):
        print(f"[WARNING] JSON file not found at {DATA_JSON_PATH}. Using empty list.")
        PUBLIC_FILES = {}
        return

    try:
        with open(DATA_JSON_PATH, "r") as f:
            files_list = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"[ERROR] Could not load/parse JSON file: {e}")
        PUBLIC_FILES = {}
        return

    file_map = {}
    for entry in files_list:
        fid = entry.get("id")
        fname = entry.get("name", "Untitled")
        mime_type = entry.get("mimeType", "")
        if fid:
            file_map[fid] = {
                "name": fname,
                "mimeType": mime_type,
                "iframeUrl": generate_iframe_url(fid, mime_type)
            }

    PUBLIC_FILES = file_map

def background_refresh_loop():
    """
    Runs in a background thread, periodically re-loading the JSON file.
    """
    while True:
        print("[refresh] Reloading JSON file...")
        load_files_from_json()
        print("[refresh] Reloaded successfully.")
        time.sleep(REFRESH_INTERVAL)

# --- Flask Routes ---

@app.route("/")
def index():
    """
    Lists all files from the in-memory dict.
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
    If the file is Google Docs/Sheets/Slides, embed in an iframe. Otherwise, show a note.
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

if __name__ == "__main__":
    # Load once at startup:
    load_files_from_json()

    # Start background thread to refresh every REFRESH_INTERVAL:
    refresh_thread = threading.Thread(target=background_refresh_loop, daemon=True)
    refresh_thread.start()

    # Run dev server
    app.run(host="0.0.0.0", port=8080, debug=True)
