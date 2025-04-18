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

# ────────────────────────────────
#  Environment Variables
# ────────────────────────────────
DATA_JSON_PATH  = os.environ.get("DATA_JSON_PATH", "/tmp/files.json")
REFRESH_INTERVAL = int(os.environ.get("REFRESH_INTERVAL", "300"))  # default 5 min
PAGE_TITLE      = os.environ.get("PAGE_TITLE", "web-gsuite-docs")
PAGE_HEADER     = os.environ.get("PAGE_HEADER", "My G Suite Folder")
HOME_URL        = os.environ.get("HOME_URL", "https://example.com")

PUBLIC_FILES: dict[str, dict] = {}


# ────────────────────────────────
#  Helpers
# ────────────────────────────────
def slugify(title: str) -> str:
    s = title.lower()
    s = re.sub(r'[^a-z0-9_\-\s]+', '', s)   # remove non‑allowed chars
    s = re.sub(r'\s+', '', s)               # collapse whitespace
    return s.strip('-')


def build_iframe_url(url: str) -> str:
    """
    Convert any Google‑Docs link (shared or 'publish to web') to
    the zero‑padding preview variant.
    """
    if "docs.google.com/document" not in url:
        return url  # untouched for non‑Docs links

    # 1. Normal share links  …/edit → …/preview
    url = re.sub(r'/edit(\?.*)?$', '/preview', url)

    # 2. Published links …/pub*  → …/preview
    url = re.sub(r'/pub.*$',  '/preview', url)

    # Ensure ?rm=minimal is present exactly once
    if '?rm=minimal' not in url:
        sep = '&' if '?' in url else '?'
        url = f'{url}{sep}rm=minimal'

    return url


def generate_qr_code(url: str) -> str:
    qr_img = qrcode.make(url)
    buffer = io.BytesIO()
    qr_img.save(buffer, "PNG")
    b64_img = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/png;base64,{b64_img}"


# ────────────────────────────────
#  Data loading & background refresh
# ────────────────────────────────
def load_files_from_json() -> None:
    global PUBLIC_FILES

    if not os.path.exists(DATA_JSON_PATH):
        print(f"[WARNING] JSON file not found at {DATA_JSON_PATH}; using empty list.")
        PUBLIC_FILES = {}
        return

    try:
        with open(DATA_JSON_PATH, "r") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[ERROR] Could not load/parse JSON: {exc}")
        PUBLIC_FILES = {}
        return

    file_map: dict[str, dict] = {}
    for entry in data:
        title = entry.get("title", "Untitled")
        url   = entry.get("url", "").strip()
        if not url:
            continue

        slug = slugify(title)
        file_map[slug] = {
            "title": title,
            "url":   url,
            "iframeUrl": build_iframe_url(url)
        }

    PUBLIC_FILES = file_map


def background_refresh_loop() -> None:
    while True:
        print("[refresh] Reloading JSON file…")
        load_files_from_json()
        print("[refresh] Reloaded successfully.")
        time.sleep(REFRESH_INTERVAL)


# ────────────────────────────────
#  Routes
# ────────────────────────────────
@app.route("/")
def index():
    files_data = sorted(
        [(slug, info["title"], info["url"]) for slug, info in PUBLIC_FILES.items()],
        key=lambda item: item[1].lower()
    )
    return render_template(
        "index.html",
        page_title=PAGE_TITLE,
        page_header=PAGE_HEADER,
        files_data=files_data,
        home_url=HOME_URL
    )


@app.route("/<slug>")
def view_file(slug):
    file_data = PUBLIC_FILES.get(slug)
    if not file_data:
        return f"File slug ‘{slug}’ not found in JSON."

    full_url = request.url.replace("http://", "https://")
    qr_code_data_uri = generate_qr_code(full_url)

    files_data = sorted(
        [(s, info["title"], info["url"]) for s, info in PUBLIC_FILES.items()],
        key=lambda item: item[1].lower()
    )

    return render_template(
        "view_file.html",
        page_title=PAGE_TITLE,
        page_header=PAGE_HEADER,
        file_title=file_data["title"],
        embed_url=file_data["iframeUrl"],
        qr_code_data_uri=qr_code_data_uri,
        files_data=files_data,
        home_url=HOME_URL,
        slug=slug
    )


@app.route("/<slug>/qr_only")
def view_file_qr_only(slug):
    if slug not in PUBLIC_FILES:
        return f"File slug ‘{slug}’ not found."

    full_url = url_for('view_file', slug=slug, _external=True)
    qr_code_data_uri = generate_qr_code(full_url)
    return render_template("qr_only.html", qr_code_data_uri=qr_code_data_uri)


@app.route("/all_qr_codes")
def all_qr_codes():
    files_data = sorted(
        [(s, info["title"], info["url"]) for s, info in PUBLIC_FILES.items()],
        key=lambda item: item[1].lower()
    )

    qr_list = []
    for slug, title, _ in files_data:
        full_url = url_for('view_file', slug=slug, _external=True)
        qr_list.append((slug, title, generate_qr_code(full_url)))

    return render_template(
        "all_qr_codes.html",
        page_title=PAGE_TITLE,
        page_header=PAGE_HEADER,
        files_data=files_data,
        qr_codes=qr_list,
        home_url=HOME_URL
    )


# ────────────────────────────────
#  Main
# ────────────────────────────────
if __name__ == "__main__":
    load_files_from_json()
    threading.Thread(target=background_refresh_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=8080, debug=True)
