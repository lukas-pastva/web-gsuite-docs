import os
import time
import json
import threading
import re
import io
import base64

import qrcode
from flask import Flask, render_template, request, url_for

app = Flask(__name__)

# Environment Variables
DATA_JSON_PATH = os.environ.get("DATA_JSON_PATH", "/tmp/files.json")
REFRESH_INTERVAL = int(os.environ.get("REFRESH_INTERVAL", "300"))  # default 5 minutes

PAGE_TITLE = os.environ.get("PAGE_TITLE", "web-gsuite-docs")
PAGE_HEADER = os.environ.get("PAGE_HEADER", "My G Suite Folder")

HOME_URL = os.environ.get("HOME_URL", "https://example.com")

PUBLIC_FILES = {}

def slugify(title: str) -> str:
    s = title.lower()
    s = re.sub(r'[^a-z0-9_\-\s]+', '', s)  # remove non-allowed chars
    s = re.sub(r'\s+', '', s)             # remove spaces
    s = s.strip('-')                      # strip leading/trailing dashes
    return s

def maybe_add_embedded_param(url: str) -> str:
    if "docs.google.com" in url and "/pub" in url:
        if "embedded=true" not in url:
            sep = '&' if '?' in url else '?'
            return url + sep + "embedded=true"
    return url

def generate_qr_code(url: str) -> str:
    """
    Generate a QR code (PNG) for the given URL, return it as a data URI (base64).
    """
    qr_img = qrcode.make(url)
    buffer = io.BytesIO()
    qr_img.save(buffer, "PNG")
    b64_img = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{b64_img}"

def load_files_from_json():
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
    while True:
        print("[refresh] Reloading JSON file...")
        load_files_from_json()
        print("[refresh] Reloaded successfully.")
        time.sleep(REFRESH_INTERVAL)

@app.route("/")
def index():
    """
    Home page: shows a button for 'Home' plus links for each file,
    plus a link for "All QR Codes."
    """
    files_data = [(slug, info["title"], info["url"])
                  for slug, info in PUBLIC_FILES.items()]
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
    The sub-page for a given file, showing its embedded doc and a clickable QR code.
    """
    file_data = PUBLIC_FILES.get(slug)
    if not file_data:
        return f"File slug '{slug}' not found in JSON."

    # Build full https URL for this page (for the QR code to encode)
    full_url = request.url.replace("http://", "https://")
    qr_code_data_uri = generate_qr_code(full_url)

    # We'll pass the same hop menu
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

@app.route("/<slug>/qr_only")
def view_file_qr_only(slug):
    """
    Minimal page that ONLY shows the QR code (no headers/nav).
    """
    file_data = PUBLIC_FILES.get(slug)
    if not file_data:
        return f"File slug '{slug}' not found."

    # The QR should encode the same 'view_file' route:
    full_url = url_for('view_file', slug=slug, _external=True)
    # If you'd rather keep 'https://' always, you could do:
    # full_url = request.url_root.replace("http://", "https://") + slug

    qr_code_data_uri = generate_qr_code(full_url)
    return render_template(
        "qr_only.html",
        qr_code_data_uri=qr_code_data_uri
    )

@app.route("/all_qr_codes")
def all_qr_codes():
    """
    Page that shows all files' titles and their QR codes on one page.
    """
    # We'll build a list of (slug, title, qr_data_uri).
    # The QR code for each file points to the main route for that file.
    files_data = [(s, info["title"], info["url"]) for s, info in PUBLIC_FILES.items()]

    qr_list = []
    for slug, title, _ in files_data:
        full_url = url_for('view_file', slug=slug, _external=True)
        qr_data_uri = generate_qr_code(full_url)
        qr_list.append((slug, title, qr_data_uri))

    return render_template(
        "all_qr_codes.html",
        page_title=PAGE_TITLE,
        page_header=PAGE_HEADER,
        files_data=files_data,  # for the nav
        qr_codes=qr_list,       # for the displayed QRs
        home_url=HOME_URL
    )

if __name__ == "__main__":
    load_files_from_json()
    refresh_thread = threading.Thread(target=background_refresh_loop, daemon=True)
    refresh_thread.start()

    app.run(host="0.0.0.0", port=8080, debug=True)
