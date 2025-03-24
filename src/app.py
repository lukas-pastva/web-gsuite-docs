import os
import time
import json
import threading
import re
import io
import base64

import qrcode
from flask import Flask, render_template, request

app = Flask(__name__)

# Environment Variables
DATA_JSON_PATH = os.environ.get("DATA_JSON_PATH", "/tmp/files.json")
REFRESH_INTERVAL = int(os.environ.get("REFRESH_INTERVAL", "300"))  # default 5 minutes

PAGE_TITLE = os.environ.get("PAGE_TITLE", "web-gsuite-docs")
PAGE_HEADER = os.environ.get("PAGE_HEADER", "My G Suite Folder")

# The "Home" button will link to this URL (e.g. your intranet or any external site).
HOME_URL = os.environ.get("HOME_URL", "https://example.com")

# We'll store file data in a dict keyed by slug, e.g.:
#   PUBLIC_FILES = {
#       "mydoc-2023": { "title": "My Doc - 2023", "url": "...", "iframeUrl": "..." },
#       ...
#   }
PUBLIC_FILES = {}

def slugify(title: str) -> str:
    """
    Lowercase the title, keep letters, digits, underscores, dashes, and spaces.
    Then remove spaces entirely, preserving dashes.
    E.g. "My Doc - 2023!" -> "mydoc-2023"
    """
    s = title.lower()
    s = re.sub(r'[^a-z0-9_\-\s]+', '', s)  # remove non-allowed chars
    s = re.sub(r'\s+', '', s)             # remove spaces
    s = s.strip('-')                      # strip leading/trailing dashes
    return s

def maybe_add_embedded_param(url: str) -> str:
    """
    If it's a published Google Doc (with /pub) and doesn't have ?embedded=true, append it.
    """
    if "docs.google.com" in url and "/pub" in url:
        if "embedded=true" not in url:
            sep = '&' if '?' in url else '?'
            return url + sep + "embedded=true"
    return url

def generate_qr_code(url: str) -> str:
    """
    Generate a QR code for the given URL, return as data:image/png;base64,...
    """
    qr_img = qrcode.make(url)
    buffer = io.BytesIO()
    qr_img.save(buffer, "PNG")
    b64_img = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{b64_img}"

def load_files_from_json():
    """
    Load the JSON from DATA_JSON_PATH, building a dict keyed by slug.
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
    for entry in data:
        title = entry.get("title", "Untitled")
        url = entry.get("url", "").strip()
        if not url:
            continue

        iframe_url = maybe_add_embedded_param(url)
        slug = slugify(title)

        file_map[slug] = {
            "title": title,
            "url": url,
            "iframeUrl": iframe_url
        }

    PUBLIC_FILES = file_map

def background_refresh_loop():
    """
    Periodically refresh the JSON file in a background thread.
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
    The home page: shows the full hop menu (buttons) for all files,
    plus a "Home" button that links to HOME_URL.
    """
    files_data = [(slug, info["title"], info["url"])
                  for slug, info in PUBLIC_FILES.items()]
    # Sort if desired:
    # files_data.sort(key=lambda x: x[1].lower())

    return render_template(
        "index.html",
        page_title=PAGE_TITLE,
        page_header=PAGE_HEADER,
        files_data=files_data,
        home_url=HOME_URL
    )

@app.route("/<slug>")
def view_file(slug):
    """
    The sub-page for a given slug, also includes the same hop menu plus "Home" button.
    QR code in the bottom-right corner for the full https URL of this page.
    """
    file_data = PUBLIC_FILES.get(slug)
    if not file_data:
        return f"File slug '{slug}' not found in JSON."

    # Build full https URL
    full_url = request.url.replace("http://", "https://")
    qr_code_data_uri = generate_qr_code(full_url)

    # We'll also pass the same hop menu
    files_data = [(s, info["title"], info["url"])
                  for s, info in PUBLIC_FILES.items()]

    return render_template(
        "view_file.html",
        page_title=PAGE_TITLE,
        page_header=PAGE_HEADER,
        file_title=file_data["title"],
        embed_url=file_data["iframeUrl"],
        qr_code_data_uri=qr_code_data_uri,
        files_data=files_data,
        home_url=HOME_URL
    )

if __name__ == "__main__":
    load_files_from_json()
    refresh_thread = threading.Thread(target=background_refresh_loop, daemon=True)
    refresh_thread.start()

    app.run(host="0.0.0.0", port=8080, debug=True)
