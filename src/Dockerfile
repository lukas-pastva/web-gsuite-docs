FROM python:3.9-slim

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Default environment variables (overridable in K8s or docker run)
ENV FLASK_APP=app.py
ENV FLASK_ENV=production
ENV GSUITE_FOLDER_URL=""
ENV REFRESH_INTERVAL=300
ENV SERVICE_ACCOUNT_FILE="/var/secrets/google/service_account.json"
ENV PAGE_TITLE="web-gsuite-docs"
ENV PAGE_HEADER="My G Suite Folder"

EXPOSE 8080

CMD ["python", "app.py"]
