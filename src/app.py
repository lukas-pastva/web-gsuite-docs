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

# We'll store files in this dict: { "0": { "title": ..., "url": ..., "iframeUrl": ... },
#                                  "1": { "title": ..., "url": ..., "iframeUrl": ... }, ... }
PUBLIC_FILES = {}

def maybe_add_embedded_param(url: str) -> str:
    """
    If the URL appears to be a published Google Doc, Slide, or other /pub link,
    and it doesn't already have ?embedded=true, append it.
    This is optional convenience, so you don't have to type ?embedded=true each time.
    """
    # If it's not docs.google.com or doesn't have '/pub' in it, we just return as-is.
    if "docs.google.com" in url and "/pub" in url:
        # If it already has ? or & we can append differently, but simplest is:
        if "embedded=true" not in url:
            # If there's already a '?', append '&'; otherwise, append '?'
            separator = '&' if '?' in url else '?'
            return url + separator + "embedded=true"
    return url

def load_files_from_json():
    """
    Load JSON from DATA_JSON_PATH:
      [
        { "title": "My Doc", "url": "https://docs.google.com/.../pub" },
        ...
      ]
    Build the PUBLIC_FILES dict keyed by index (string).
    """
    global PUBLIC_FILES

    if not os.path.exists(DATA_JSON_PATH):
        print(f"[WARNING] JSON file not found at {DATA_JSON_PATH}. Using empty list.")
        PUBLIC_FILES = {}
        return

    try:
        with open(DATA_JSON_PATH, "r") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"[ERROR] Could not load/parse JSON file: {e}")
        PUBLIC_FILES = {}
        return

    file_map = {}
    for i, entry in enumerate(data):
        title = entry.get("title", f"Untitled {i}")
        url = entry.get("url", "").strip()
        if not url:
            continue

        # Potentially modify the URL to ensure ?embedded=true for published docs:
        iframe_url = maybe_add_embedded_param(url)

        # We'll store them with a string index (e.g. "0", "1", "2", ...)
        key = str(i)
        file_map[key] = {
            "title": title,
            "url": url,
            "iframeUrl": iframe_url
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
    Lists all links from the in-memory dict.
    """
    # We'll produce a list of tuples: (index_str, title, original_url)
    files_data = [(idx, info["title"], info["url"]) for idx, info in PUBLIC_FILES.items()]
    # Sort by index to keep them in the same order as the JSON
    files_data.sort(key=lambda x: int(x[0]))
    return render_template(
        "index.html",
        page_title=PAGE_TITLE,
        page_header=PAGE_HEADER,
        files_data=files_data
    )

@app.route("/view/<file_idx>")
def view_file(file_idx):
    """
    Renders the link in an iframe if possible, otherwise shows a note.
    """
    file_data = PUBLIC_FILES.get(file_idx)
    if not file_data:
        return f"File index {file_idx} not found in JSON."

    # If the user wants to see the raw link, we have file_data["url"]
    # The embed link is file_data["iframeUrl"]
    return render_template(
        "view_file.html",
        page_title=PAGE_TITLE,
        page_header=PAGE_HEADER,
        file_title=file_data["title"],
        embed_url=file_data["iframeUrl"]
    )

if __name__ == "__main__":
    # Load once at startup:
    load_files_from_json()

    # Start background thread to refresh every REFRESH_INTERVAL:
    refresh_thread = threading.Thread(target=background_refresh_loop, daemon=True)
    refresh_thread.start()

    # Run dev server
    app.run(host="0.0.0.0", port=8080, debug=True)
