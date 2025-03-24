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

# Dictionary keyed by slug, e.g. { "mydocument-2023": {...}, ... }
PUBLIC_FILES = {}

def slugify(title: str) -> str:
    """
    Convert to lowercase, keep letters, digits, underscores (_), dashes (-), and spaces.
    Then remove all spaces (with no replacement), preserving any dashes.
    e.g. "My Doc - 2023!" -> "mydoc-2023"
    """
    s = title.lower()
    # Remove all chars except letters, digits, underscores, dashes, and spaces
    s = re.sub(r'[^a-z0-9_\-\s]+', '', s)
    # Remove spaces entirely
    s = re.sub(r'\s+', '', s)
    # Strip leading/trailing dashes
    s = s.strip('-')
    return s

def maybe_add_embedded_param(url: str) -> str:
    """
    If the URL appears to be a published Google Doc, Slide, or other /pub link,
    and doesn't already have ?embedded=true, append it for iframe embedding.
    """
    if "docs.google.com" in url and "/pub" in url:
        if "embedded=true" not in url:
            separator = '&' if '?' in url else '?'
            return url + separator + "embedded=true"
    return url

def generate_qr_code(url: str) -> str:
    """
    Generate a QR code for the given URL and return it as a 'data:image/png;base64,...' string.
    """
    qr_img = qrcode.make(url)
    buffer = io.BytesIO()
    qr_img.save(buffer, format="PNG")
    b64_img = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{b64_img}"

def load_files_from_json():
    """
    Load JSON from DATA_JSON_PATH (an array of { "title": "...", "url": "..." }),
    building a dict keyed by slug.
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
    Home page: show a "hop menu" of buttons to each file's page.
    """
    files_data = [(slug, info["title"], info["url"])
                  for slug, info in PUBLIC_FILES.items()]
    # If you want them sorted by title:
    # files_data.sort(key=lambda x: x[1].lower())

    return render_template(
        "index.html",
        page_title=PAGE_TITLE,
        page_header=PAGE_HEADER,
        files_data=files_data
    )

@app.route("/<slug>")
def view_file(slug):
    """
    View page for a given slug: shows an iframe (if applicable) plus a QR code in bottom-right.
    """
    file_data = PUBLIC_FILES.get(slug)
    if not file_data:
        return f"File slug '{slug}' not found in JSON."

    # Build a full HTTPS URL for the current route
    # e.g. "https://mydomain.com/my-file"
    # If the request is not already https, replace http with https in the scheme:
    full_url = request.url.replace("http://", "https://")
    
    # Generate QR code
    qr_code_data_uri = generate_qr_code(full_url)

    return render_template(
        "view_file.html",
        page_title=PAGE_TITLE,
        page_header=PAGE_HEADER,
        file_title=file_data["title"],
        embed_url=file_data["iframeUrl"],
        qr_code_data_uri=qr_code_data_uri
    )

if __name__ == "__main__":
    # Load once at startup
    load_files_from_json()

    # Start background reloader
    refresh_thread = threading.Thread(target=background_refresh_loop, daemon=True)
    refresh_thread.start()

    # Run Flask
    app.run(host="0.0.0.0", port=8080, debug=True)
