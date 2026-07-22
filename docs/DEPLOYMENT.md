# 🚀 Forest Intelligence System — Production Deployment Guide

This guide outlines the procedure for deploying the **Forest Intelligence System (FIS)** to a production Linux server (Ubuntu 22.04 LTS / Debian 12).

---

## 1. System Requirements & Prerequisites

- **Server Spec**: 2+ vCPU, 4GB+ RAM.
- **Operating System**: Ubuntu 22.04 LTS.
- **Database**: MySQL 8.0+ or PostgreSQL 14+.
- **In-Memory Store**: Redis 7.0+.
- **Reverse Proxy**: Nginx with SSL (Certbot / Let's Encrypt).
- **Python**: Python 3.10 or higher.
- **Service Account**: Google Earth Engine registered Service Account JSON key.

---

## 2. Directory & User Setup

Create a non-root system user for managing the application:

```bash
sudo useradd -m -s /bin/bash fisuser
sudo usermod -aG sudo fisuser
sudo su - fisuser

# Clone repository
git clone https://github.com/jaherunhasanrimon/Forest-Intelligence-System-FIS.git
cd Forest-Intelligence-System-FIS/backend

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 3. Production Environment Configuration

Create the production `.env` file at `/home/fisuser/Forest-Intelligence-System-FIS/backend/.env`:

```env
APP_NAME="Forest Intelligence System"
ENVIRONMENT=production
PORT=8000
SECRET_KEY="generate-a-secure-random-secret-key-here"

# Database Connection (MySQL)
DATABASE_URL="mysql+pymysql://fis_db_user:StrongPasswordHere@localhost:3306/forest_intelligence_db"

# Redis Queue
REDIS_URL="redis://localhost:6379/0"

# GEE Credentials
GEE_SERVICE_ACCOUNT_JSON="/home/fisuser/Forest-Intelligence-System-FIS/backend/secrets/gee-service-account.json"
GOOGLE_MAPS_API_KEY="AIzaSyYourProductionGoogleMapsAPIKey"

# Storage Settings
STORAGE_BACKEND=local
LOCAL_STORAGE_PATH="/home/fisuser/Forest-Intelligence-System-FIS/backend/storage"

# Optional Cloud Storage (if Google Cloud Storage billing is enabled)
# STORAGE_BACKEND=gcs
# GCS_BUCKET_NAME=your-production-gcs-bucket-name
```

---

## 4. GEE Service Account Key Management

Upload your `gee-service-account.json` to the secure directory:

```bash
mkdir -p /home/fisuser/Forest-Intelligence-System-FIS/backend/secrets
chmod 700 /home/fisuser/Forest-Intelligence-System-FIS/backend/secrets
# Copy json key file to /home/fisuser/Forest-Intelligence-System-FIS/backend/secrets/gee-service-account.json
chmod 600 /home/fisuser/Forest-Intelligence-System-FIS/backend/secrets/gee-service-account.json
```

---

## 5. Systemd Service Configurations

### A. FastAPI Web Server (`/etc/systemd/system/fis-web.service`)
```ini
[Unit]
Description=Forest Intelligence System Web Server (FastAPI)
After=network.target mysql.service redis-server.service

[Service]
User=fisuser
Group=fisuser
WorkingDirectory=/home/fisuser/Forest-Intelligence-System-FIS/backend
ExecStart=/home/fisuser/Forest-Intelligence-System-FIS/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 4
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### B. Celery Background Worker (`/etc/systemd/system/fis-worker.service`)
```ini
[Unit]
Description=Forest Intelligence System Celery Worker
After=network.target redis-server.service

[Service]
User=fisuser
Group=fisuser
WorkingDirectory=/home/fisuser/Forest-Intelligence-System-FIS/backend
ExecStart=/home/fisuser/Forest-Intelligence-System-FIS/backend/.venv/bin/celery -A celery_worker.celery_app worker --loglevel=info --concurrency=2
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start systemd services:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now fis-web fis-worker
```

---

## 6. Nginx Reverse Proxy Configuration

Create `/etc/nginx/sites-available/forest-intelligence.conf`:

```nginx
server {
    listen 80;
    server_name fis.yourdomain.com;

    client_max_body_size 50M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /home/fisuser/Forest-Intelligence-System-FIS/backend/app/static/;
    }
}
```

Enable Nginx site and obtain SSL Certificate:
```bash
sudo ln -s /etc/nginx/sites-available/forest-intelligence.conf /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
sudo certbot --nginx -d fis.yourdomain.com
```

---

## 7. Operational Verification

1. Check system service status:
   ```bash
   sudo systemctl status fis-web fis-worker
   ```
2. Monitor application logs:
   ```bash
   journalctl -u fis-web -f
   journalctl -u fis-worker -f
   ```
