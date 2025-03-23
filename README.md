# web-gsuite-docs

A Kubernetes-ready application that periodically **fetches** metadata from a **Google Drive** folder and **displays** it in a **Flask** web interface. The app uses a **Kubernetes CronJob** to retrieve file info (e.g., from Docs, Sheets, Slides) and writes it to a shared volume. The Flask app then **reads** that data, lists the files, and (for Google Docs/Sheets/Slides) embeds them via iframes for a “real look.”

## How It Works
1. **CronJob** runs `fetch.py` on a schedule, authenticating via a **service account** to list files in the specified Drive folder.  
2. The script writes file metadata to a **JSON file** stored in a **Persistent Volume**.  
3. **Flask app** (`app.py`) mounts the same volume, loads the JSON file, and displays the files in a simple web interface. If a file is a Google Doc, Sheet, or Slide, the app embeds it in an iframe.

## Basic Usage
1. **Build & push** two Docker images: one for the CronJob (`fetch.py`) and one for the Flask app.  
2. **Create** a **Kubernetes Secret** for the service account JSON.  
3. **Provision** a **Persistent Volume** (and PVC) for storing the file metadata.  
4. **Deploy**:
   - A **CronJob** (mounting the secret and PVC) that runs `fetch.py` every few minutes.  
   - A **Deployment** for the Flask app (also mounting the PVC).  
   - A **Service** to expose the Flask app.

## Environment Variables
- **CronJob** (`fetch.py`):
  - `GSUITE_FOLDER_URL`: Google Drive folder link.  
  - `SERVICE_ACCOUNT_FILE`: Path to service account JSON.  
  - `OUTPUT_JSON_PATH`: Where to write the JSON file (e.g., `/data/files.json`).  
- **Flask App** (`app.py`):
  - `DATA_JSON_PATH`: Path to the JSON file (e.g., `/data/files.json`).  
  - `PAGE_TITLE`: Text for the HTML `<title>`.  
  - `PAGE_HEADER`: Main header text in the UI.

That’s it! Once deployed, the CronJob updates the file list on the configured schedule, and the Flask app displays the latest data in a simple, iframe-based interface.
