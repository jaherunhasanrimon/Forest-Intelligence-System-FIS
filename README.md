# 🌲 Forest Intelligence System (FIS)

> **Automated Geospatial Satellite Processing, AI Raster Inference & Forest Health Intelligence Engine**

---

## 📌 Executive Overview

The **Forest Intelligence System (FIS)** is an enterprise-grade geospatial web application that automates the acquisition, fusion, and AI analysis of satellite imagery for forest canopy monitoring, biomass estimation, carbon stock accounting, and health diagnostics.

By replacing manual Earth Engine script runs with an automated background job orchestration pipeline, FIS enables environmental scientists, land managers, and carbon project developers to draw an Area of Interest (AOI) on an interactive map and instantly generate a standardized 10-band composite GeoTIFF raster, AI environmental metrics, and an executive PDF/HTML report.

---

## 🏛️ System Architecture

```mermaid
flowchart TD
    subgraph Frontend["Frontend Layer (FastAPI Templates & JS)"]
        UI["Google Maps Interactive Drawing UI"]
        JobsUI["Jobs Dashboard & Real-Time Polling"]
    end

    subgraph API["Backend API Layer (FastAPI)"]
        AOIRoutes["AOI Routes (/api/aoi)"]
        JobRoutes["Job Routes (/api/jobs)"]
        DB[(MySQL / SQLite DB)]
    end

    subgraph Queue["Async Task Queue (Celery + Redis)"]
        Redis[("Redis Broker")]
        Worker["Celery Worker Node"]
    end

    subgraph Processing Engine
        GEE["Google Earth Engine API"]
        Composite["10-Band Composite Engine (S1 SAR + S2 Optical)"]
        AI["AI Inference Engine (Raster Analytics)"]
        ReportEngine["ReportLab PDF & HTML Engine"]
    end

    subgraph Storage
        LocalStorage["Local GeoTIFF & Report Storage"]
        GCSStorage["Google Cloud Storage (Optional)"]
    end

    UI -->|1. Submit AOI Polygon| AOIRoutes
    AOIRoutes -->|2. Create Job Record| DB
    AOIRoutes -->|3. Dispatch Task| Redis
    Redis --> Worker
    Worker -->|4. Authenticate & Query| GEE
    GEE -->|5. Build Composite Image| Composite
    Composite -->|6. Stream 10-Band GeoTIFF| LocalStorage
    LocalStorage --> AI
    AI -->|7. Calculate Biomass, Carbon & Health| DB
    AI --> ReportEngine
    ReportEngine -->|8. Generate Executive PDF/HTML| LocalStorage
    JobsUI -->|9. Poll Status (3s Interval)| JobRoutes
    JobRoutes -->|10. Download PDF Report| JobsUI
```

---

## 🌟 Key Features

1. **Interactive Full-Screen Map Drawer**:
   - Google Maps Drawing Manager allowing users to define polygon boundaries.
   - Client-side vertex bounds checking (3 to 100 vertices), max area enforcement (**5,000 ha**), coordinate rounding (6 decimal places), and Shoelace planar area calculation.
   - Server-side **Shapely polygon topology validation** preventing self-intersecting geometries.

2. **Stateful Asynchronous Job Queue (Celery + Redis)**:
   - Non-blocking job submission.
   - Stateful pipeline transitions (`PENDING` → `EXPORTING` → `EXPORTED` → `DOWNLOADED` → `ANALYZING` → `COMPLETED` | `FAILED`).
   - Dynamic real-time **NDVI Job Status Bars** updating via polling (`GET /api/jobs/{id}/status`).

3. **Automated 10-Band Sentinel Composite Engine**:
   - **Sentinel-2 Surface Reflectance (Optical)**: QA60 cloud and cirrus bitmasking, median compositing.
   - **Sentinel-1 SAR C-Band (Radar)**: $VV$ and $VH$ polarizations, 3x3 focal mean speckle filtering.
   - **Spectral Vegetation Indices**: NDVI (Normalized Difference Vegetation Index) and EVI (Enhanced Vegetation Index).
   - Standardized 10-Band Stack: `['B2', 'B3', 'B4', 'B8', 'B11', 'B12', 'NDVI', 'EVI', 'VV', 'VH']`.

4. **Dual Storage Provider Abstraction**:
   - **Local Storage Mode**: Direct GEE HTTP stream extraction into `storage/geotiffs/`. Requires **zero Google Cloud Storage billing**.
   - **Google Cloud Storage (GCS) Mode**: Automated GEE batch exports (`Export.image.toCloudStorage`).

5. **Local AI Raster Analytics Engine**:
   - Computes forest canopy cover %, tree count estimation, dry biomass tonnage, IPCC Tier 1 carbon stock ($\text{Carbon} = \text{Biomass} \times 0.47$) and $\text{CO}_2\text{e}$ offsets ($\text{CO}_2\text{e} = \text{Carbon} \times 3.67$).
   - Categorizes forest health into **Healthy**, **Stressed**, or **Degraded** using multi-spectral SWIR moisture ratios and EVI vigor.
   - **Zero external AI API keys required** (runs 100% locally).

6. **Automated Executive PDF & HTML Report Generator**:
   - Generates executive reports using Jinja2 HTML templates and ReportLab PDF compilation.
   - Includes download action buttons (`GET /api/jobs/{id}/report/download`) directly on the Jobs Dashboard.

---

## 🛠️ Technology Stack Matrix

| Layer | Technologies Used |
| :--- | :--- |
| **Backend Framework** | Python 3.13, FastAPI, Uvicorn, Pydantic V2, SQLAlchemy |
| **Database** | MySQL (Production) / SQLite (Testing) |
| **Async Task Queue** | Celery, Redis |
| **Remote Sensing & GIS** | Google Earth Engine Python API (`ee`), Shapely, NumPy, SciPy, Rasterio |
| **Report Compiler** | ReportLab, Jinja2 |
| **Frontend UI** | HTML5, Vanilla CSS (Technical Dark Forest & Light Report Themes), JavaScript, Google Maps API |

---

## 🚀 Local Quickstart Guide

### Prerequisites
- Python 3.10+ installed.
- Redis server running locally.
- Google Earth Engine Service Account JSON key stored in `backend/secrets/gee-service-account.json`.

### 1. Clone & Set Up Virtual Environment
```bash
git clone https://github.com/jaherunhasanrimon/Forest-Intelligence-System-FIS.git
cd Forest-Intelligence-System-FIS/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env`:
```env
APP_NAME="Forest Intelligence System"
ENVIRONMENT=development
PORT=8000
DATABASE_URL=sqlite:///./test.db
REDIS_URL=redis://localhost:6379/0
GEE_SERVICE_ACCOUNT_JSON=backend/secrets/gee-service-account.json
GOOGLE_MAPS_API_KEY=YOUR_GOOGLE_MAPS_API_KEY
STORAGE_BACKEND=local
GCS_BUCKET_NAME=not-configured
```

### 3. Start Redis Server
```bash
redis-server
```

### 4. Start Celery Background Worker
In a new terminal window:
```bash
cd backend
source .venv/bin/activate
celery -A celery_worker.celery_app worker --loglevel=info
```

### 5. Launch FastAPI Web Application
In a third terminal window:
```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

Open your browser and navigate to: **`http://localhost:8000`**

---

## 📡 REST API Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/aoi` | Submit a GeoJSON AOI polygon and date window to create a job |
| `GET` | `/api/jobs` | Retrieve all submitted monitoring jobs |
| `GET` | `/api/jobs/{id}/status` | Query current pipeline state and elapsed runtime |
| `GET` | `/api/jobs/{id}/results` | Retrieve AI analysis metrics (biomass, carbon, health, tree count) |
| `GET` | `/api/jobs/{id}/report/download` | Download generated PDF or HTML report deliverable |
| `DELETE`| `/api/jobs/{id}` | Cancel/delete a job and its associated logs |

---

## 🧪 Running Automated Tests

Run the complete test suite containing unit and integration tests:
```bash
cd backend
.venv/bin/pytest -v
```

All 13 tests execute using an isolated SQLite in-memory database and eager task execution:
```
tests/test_ai_analysis.py ..                                             [ 15%]
tests/test_aoi_api.py ....                                               [ 46%]
tests/test_gee_connection.py .                                           [ 53%]
tests/test_gee_script.py ...                                             [ 76%]
tests/test_jobs_api.py ..                                                [ 92%]
tests/test_report_generation.py .                                        [100%]
======================= 13 passed in 47s =======================
```

---

## 🔒 Security & Credentials Protection

- All secret keys, Google Maps API tokens, and Earth Engine service account credentials are stored in `.env` or `backend/secrets/`.
- `backend/secrets/`, `.env`, and generated GeoTIFF files (`backend/storage/*`) are strictly ignored in `.gitignore` to prevent accidental public disclosure.

---

## 📜 License
This project is developed under the Forest Intelligence System Specification for environmental conservation and remote sensing AI analytics.
