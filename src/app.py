import os
import time
import json
import threading
import re

from flask import Flask, render_template

app = Flask(__name__)

# Environment Variables
DATA_JSON_PATH = os.environ.get("DATA_JSON_PATH", "/tmp/files.json")
REFRESH_INTERVAL = int(os.environ.get("REFRESH_INTERVAL", "300"))  # default 5 minutes

PAGE_TITLE = os.environ.get("PAGE_TITLE", "web-gsuite-docs")
PAGE_HEADER = os.environ.get("PAGE_HEADER", "My G Suite Folder")

# We'll store files in this dict, keyed by slug: { "mydoc": { "title": ..., "url": ..., "iframeUrl": ... },
#                                                 "anotherdoc": { "title": ..., "url": ..., "iframeUrl": ... }, ... }
PUBLIC_FILES = {}

def slugify(title: str) -> str:
    """
    Convert title to lowercase, remove spaces, punctuation, etc. 
    For example: "My Document 2023!" -> "mydocument2023"
    """
    # Convert to lowercase, remove all non-word characters, then remove spaces if any remain, etc.
    return re.sub(r"\W+", "", title.lower())

def maybe_add_embedded_param(url: str) -> str:
    """
    If the URL appears to be a published Google Doc, Slide, or other /pub link,
    and it doesn't already have ?embedded=true, append it.
    """
    if "docs.google.com" in url and "/pub" in url:
        if "embedded=true" not in url:
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
    Then build the PUBLIC_FILES dict keyed by a slug of the title.
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

        # Potentially modify the URL to ensure ?embedded=true for published docs:
        iframe_url = maybe_add_embedded_param(url)

        # Create a slug from the title
        page_slug = slugify(title)

        file_map[page_slug] = {
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
    # We'll produce a list of tuples: (slug, title, url)
    files_data = [(slug, info["title"], info["url"]) for slug, info in PUBLIC_FILES.items()]

    # If you want them sorted alphabetically by title or slug, you can do:
    # files_data.sort(key=lambda x: x[1].lower())  # sort by title

    return render_template(
        "index.html",
        page_title=PAGE_TITLE,
        page_header=PAGE_HEADER,
        files_data=files_data
    )

@app.route("/<slug>")
def view_file(slug):
    """
    Renders the link in an iframe if possible, otherwise shows a note.
    """
    file_data = PUBLIC_FILES.get(slug)
    if not file_data:
        return f"File slug '{slug}' not found in JSON."

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
