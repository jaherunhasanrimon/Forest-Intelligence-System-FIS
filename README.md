# Forest Intelligence System (FIS)

An automated satellite image processing and forest intelligence analysis platform built with FastAPI, Celery, Redis, MySQL, and Google Earth Engine.

This platform automates the pipeline from drawing an Area of Interest (AOI) on Google Maps to fetching Sentinel-1/Sentinel-2 satellite data, creating 10-band composite GeoTIFFs, executing AI analysis, and generating downloadable PDF reports.

---

## 🛠️ Technology Stack

- **Backend API**: FastAPI (Python 3.11)
- **Database**: MySQL 8.0
- **Task Queue**: Celery + Redis
- **Geospatial & Satellite API**: Google Earth Engine Python API (`earthengine-api`)
- **Local / Cloud Storage**: Strategy-pattern abstraction supporting local filesystem and Google Cloud Storage (GCS)
- **Containerization**: Docker & Docker Compose

---

## 🚀 Setup & Installation (For Evaluators)

In professional software development, API keys, credentials, and service account files are kept secure and are **never** committed to version control. 

To run and evaluate this project, follow the configuration steps below:

### 1. Prerequisite Configuration

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/jaherunhasanrimon/Forest-Intelligence-System-FIS.git
   cd Forest-Intelligence-System-FIS
   ```

2. **Set up Environment Variables**:
   Copy the example environment file to create your active `.env`:
   ```bash
   cp backend/.env.example backend/.env
   ```
   Open `backend/.env` in your editor and configure the parameters:
   - `GEE_SERVICE_ACCOUNT_EMAIL`: Your Earth Engine Service Account email.
   - `GOOGLE_MAPS_API_KEY`: Your Google Maps API key (needed for the frontend map selector in Phase 1+).
   - *Note*: Keep `STORAGE_BACKEND=local` and `GCS_BUCKET_NAME=not-configured` to use local storage. This avoids the need for Google Cloud Storage billing/bucket setup during evaluation.

3. **Add Google Earth Engine Key**:
   Place your GEE service account JSON credentials key file inside `backend/secrets/`.
   In your `backend/.env` file, ensure `GEE_SERVICE_ACCOUNT_KEY_PATH` points to the exact path of your JSON key file. For example:
   ```env
   GEE_SERVICE_ACCOUNT_KEY_PATH=backend/secrets/your-service-account-key.json
   ```

---

### 2. Local Environment Execution

You can run the application directly on your machine or inside containers.

#### Option A: Running Locally (Recommended for verification)

1. Create a Python virtual environment and activate it:
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run GEE connection verification to confirm configuration:
   ```bash
   python scripts/verify_gee.py
   ```
   If configured correctly, you will see a success message verifying authentication and a round-trip server calculation.

4. Run the FastAPI development server:
   ```bash
   uvicorn app.main:app --reload
   ```
   Visit the Swagger API documentation at: `http://localhost:8000/docs`

#### Option B: Running with Docker Compose

1. Build and start all services (API, Celery worker, MySQL database, Redis):
   ```bash
   docker-compose up --build
   ```

2. The services will start:
   - API Server: `http://localhost:8000`
   - Interactive Docs: `http://localhost:8000/docs`

---

## 📁 Repository Structure

```
Forest-Intelligence-System-FIS/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI main instance
│   │   ├── config.py          # Settings manager (pydantic-settings)
│   │   ├── db.py              # SQLAlchemy engine & session factory
│   │   ├── models/            # SQLAlchemy schemas (User, AOI, Job, Dataset, etc.)
│   │   ├── services/          # GEE connection & storage abstraction
│   │   └── tasks/             # Celery async tasks configuration
│   ├── scripts/
│   │   └── verify_gee.py      # GEE API connection smoketest
│   ├── secrets/               # Ignored directory for GEE credentials
│   ├── storage/               # Local directory for generated GeoTIFFs & outputs
│   └── tests/                 # Pytest test suite
├── docker-compose.yml         # Container configuration
└── README.md                  # This file
```

---

## 🔒 Security Practices

This project implements professional security standards:
- Credentials and private keys are placed in local, gitignored files (`backend/secrets/`, `.env`).
- Database credentials and API keys are read strictly from environment configurations.
- Storage targets are abstractly managed so the app operates locally if GCS cloud billing is unavailable.
