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

# Dictionary keyed by slug, e.g. { "mydocument-2023": {"title": "...", "url": "...", "iframeUrl": "..."}, ...}
PUBLIC_FILES = {}

def slugify(title: str) -> str:
    """
    Convert 'title' to lowercase, then remove all characters except letters, digits,
    underscores (_), dashes (-), and spaces. Finally, remove all spaces (with no replacement),
    keeping the dash if it was originally there.
      e.g.: "My Document - 2023!" -> "mydocument-2023"
    """
    s = title.lower()
    # Keep letters, digits, underscores, dashes, and spaces. Remove all else.
    s = re.sub(r'[^a-z0-9_\-\s]+', '', s)
    # Remove spaces entirely.
    s = re.sub(r'\s+', '', s)
    # Strip leading/trailing dashes if any remain.
    s = s.strip('-')
    return s

def maybe_add_embedded_param(url: str) -> str:
    """
    If the URL appears to be a published Google Doc, Slide, or /pub link,
    and it doesn't have '?embedded=true', append it to embed the doc in an iframe.
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
        {"title": "My Doc", "url": "https://docs.google.com/.../pub"},
        ...
      ]
    Then store them in PUBLIC_FILES keyed by the slug of each title.
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

        # Possibly append ?embedded=true if it's a Google Docs/Slides pub link
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
    Periodically re-load the JSON file in a background thread.
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
    The home page: a 'hop menu' of buttons pointing to each file's embed page.
    """
    files_data = [(slug, info["title"], info["url"])
                  for slug, info in PUBLIC_FILES.items()]
    # If desired, you could sort by title:
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
    The embed page for a given file slug.
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
    # Initial load
    load_files_from_json()

    # Start the background reloader
    refresh_thread = threading.Thread(target=background_refresh_loop, daemon=True)
    refresh_thread.start()

    # Run the Flask server
    app.run(host="0.0.0.0", port=8080, debug=True)
