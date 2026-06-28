# Help Desk Portal

A lightweight internal help desk ticketing system built with Python/Flask, containerised with Docker, and deployed to GCP using Cloud Build and Cloud Deploy.

---

## Features

- Submit support tickets with title, description, category, priority, and assignee
- View all open tickets on a dashboard with colour-coded priority and status badges
- Edit tickets and update their status (Open → In Progress → Closed)
- Delete tickets with a confirmation prompt
- Automatic status assignment (`Open`) on ticket creation

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.8 |
| Web framework | Flask |
| ORM | Flask-SQLAlchemy |
| Database (local) | SQLite |
| Templating | Jinja2 |
| Containerisation | Docker |
| Image registry | GCP Artifact Registry |
| CI pipeline | GCP Cloud Build |
| CD pipeline | GCP Cloud Deploy |
| Runtime | GCP Cloud Run |

---

## Architecture

```
┌──────────────┐     git push      ┌──────────────────────────────────────┐
│  Developer   │ ────────────────► │           Cloud Build                │
│  Workstation │                   │                                      │
└──────────────┘                   │  1. Lint      (flake8)               │
                                   │  2. Unit test (pytest)               │
                                   │  3. Docker build                     │
                                   │  4. Push image → Artifact Registry   │
                                   └─────────────┬──────────────┬─────────┘
                                                 │              │
                                    feature-*    │              │  main branch
                                    branch       │              │
                                                 ▼              ▼
                                   ┌─────────────────┐  ┌──────────────────────────┐
                                   │  Cloud Run      │  │     Cloud Deploy          │
                                   │  (feature env)  │  │                          │
                                   │                 │  │  ┌──────────────────┐    │
                                   │  Smoke test:    │  │  │  staging-env     │    │
                                   │  curl / grep    │  │  │  Cloud Run svc   │    │
                                   │  "Support       │  │  └────────┬─────────┘    │
                                   │   Tickets"      │  │           │ auto-promote │
                                   └─────────────────┘  │           │ after 1 min  │
                                                        │  ┌────────▼─────────┐    │
                                                        │  │  production-env  │    │
                                                        │  │  Cloud Run svc   │    │
                                                        │  └──────────────────┘    │
                                                        └──────────────────────────┘

  Artifact storage (GCS bucket: help-desk)
  └── Lint HTML reports  (uploaded only on lint failure)
  └── Pytest HTML reports (uploaded only on test failure)
```

---

## Local Development Setup

### Prerequisites

- Python 3.8+
- pip

### Steps

```bash
# 1. Clone the repository
git clone <repo-url>
cd helpdesk-portal

# 2. Create a virtual environment 
uv venv --python 3.8

# 3. Install dependencies
uv pip install -r requirements.txt

# 4. Activate Virtual Environment

source .venv/bin/activate

# 5. Create the database
python create_db.py

# 6. Run the application
python app.py
```

The app will start at `http://localhost:8080`.

### Running Tests Locally

```bash
# Install test dependencies
uv pip install pytest pytest-html flake8 flake8-html

# Lint check
flake8 --format=html --htmldir=flake_reports/

# Unit tests
pytest --html=pytest_reports/pytest-report.html --self-contained-html
```

### Running with Docker Locally

```bash
# Build the image
docker build -t helpdesk-portal .

# Run the container
docker run -p 8080:8080 helpdesk-portal
```

App will be available at `http://localhost:8080`.

---

## GCP Deployment

### Prerequisites

- A GCP project with billing enabled
- `gcloud` CLI installed and authenticated
- The following APIs enabled:
  - Cloud Build
  - Cloud Deploy
  - Cloud Run
  - Artifact Registry
  - Cloud Storage

### 1. Create the Artifact Registry repository

```bash
gcloud artifacts repositories create help-desk-repo \
  --repository-format=docker \
  --location=asia-south1 \
  --project=<PROJECT_ID>
```

### 2. Create the GCS bucket for test artifacts

```bash
gsutil mb -l us-central1 gs://help-desk
```

### 3. Configure Cloud Build trigger

In the GCP console → Cloud Build → Triggers, create a trigger pointing to your repository with the following substitution variables:

| Variable | Value |
|---|---|
| `_LOCATION` | `asia-south1-docker.pkg.dev` |
| `_IMAGE` | `help-desk-repo/help-desk-image` |
| `_DEPLOY_REGION` | `us-central1` |

`_IMAGE_PATH` is derived automatically as `${_LOCATION}/${PROJECT_ID}/${_IMAGE}:${BRANCH_NAME}`.

### 4. Grant Cloud Build permissions

The Cloud Build service account needs the following IAM roles:

```bash
PROJECT_NUMBER=$(gcloud projects describe <PROJECT_ID> --format='value(projectNumber)')
CB_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"

gcloud projects add-iam-policy-binding <PROJECT_ID> --member="serviceAccount:${CB_SA}" --role="roles/run.admin"
gcloud projects add-iam-policy-binding <PROJECT_ID> --member="serviceAccount:${CB_SA}" --role="roles/clouddeploy.operator"
gcloud projects add-iam-policy-binding <PROJECT_ID> --member="serviceAccount:${CB_SA}" --role="roles/iam.serviceAccountUser"
gcloud projects add-iam-policy-binding <PROJECT_ID> --member="serviceAccount:${CB_SA}" --role="roles/storage.objectAdmin"
```

### 5. Push to trigger the pipeline

```bash
# Feature branch — deploys a preview Cloud Run service and runs a smoke test
git checkout -b feature-my-change
git push origin feature-my-change

# Main branch — triggers Cloud Deploy staging → production promotion
git checkout main
git push origin main
```

### Branch Behaviour Summary

| Branch pattern | What happens |
|---|---|
| `feature-*` | Lint → Test → Build → Push → Deploy preview Cloud Run → Smoke test |
| `main` | Lint → Test → Build → Push → Register Cloud Deploy pipeline → Create release → Auto-promote staging → production |

---

## Project Structure

```
.
├── app.py                        # Flask application and route handlers
├── create_db.py                  # One-time database initialisation script
├── requirements.txt              # Python dependencies
├── Dockerfile                    # Container image definition
├── cloudbuild.yaml               # Cloud Build CI/CD pipeline definition
├── skaffold.yaml                 # Skaffold render profiles for Cloud Deploy
├── models/
│   ├── __init__.py
│   └── models.py                 # SQLAlchemy Ticket model
├── templates/
│   ├── template.html             # Base HTML template
│   ├── index.html                # Ticket list page
│   ├── add.html                  # New ticket form
│   └── edit.html                 # Edit ticket form
├── static/
│   └── template.css              # Global stylesheet
├── deploy/
│   ├── clouddeploy.yaml          # Cloud Deploy pipeline and targets
│   ├── deploy-staging.yaml       # Knative service spec for staging
│   └── deploy-production.yaml    # Knative service spec for production
├── test_app.py                   # pytest test suite
└── documentation/
    ├── frontend.md               # Frontend implementation details
    ├── backend.md                # Backend implementation details
    └── cicd.md                   # CI/CD pipeline implementation details
```

---

## Documentation

| Document | Description |
|---|---|
| [Frontend](documentation/frontend.md) | How the UI was built with Jinja2 templates and CSS |
| [Backend](documentation/backend.md) | Flask app structure, data model, and route logic |
| [CI/CD Pipeline](documentation/cicd.md) | End-to-end Cloud Build and Cloud Deploy walkthrough |
