FROM python:3.9-slim

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV FLASK_APP=app.py
ENV FLASK_ENV=production
ENV DATA_JSON_PATH=/tmp/files.json
ENV REFRESH_INTERVAL=300
ENV PAGE_TITLE="web-gsuite-docs"
ENV PAGE_HEADER="My G Suite Folder"

EXPOSE 8080

CMD ["python", "app.py"]
