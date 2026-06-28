# CI/CD Pipeline Implementation

## Overview

The pipeline uses two GCP-native services:

- **Cloud Build** — CI: lint, test, build Docker image, push to Artifact Registry, and optionally deploy and smoke-test a feature branch preview.
- **Cloud Deploy** — CD: promote a validated container image through staging → production Cloud Run services, with automatic promotion.

The pipeline is fully defined in three files:

| File | Role |
|---|---|
| `cloudbuild.yaml` | Cloud Build step definitions |
| `deploy/clouddeploy.yaml` | Cloud Deploy pipeline, targets, and automation |
| `skaffold.yaml` | Render profiles mapping Skaffold to Knative service manifests |

---

## End-to-End Flow

```
git push
    │
    ▼
Cloud Build trigger fires
    │
    ├─ Step 1: lint_test       — flake8 lints Python source
    ├─ Step 2: upload-lint-artifacts  — uploads HTML report to GCS if lint failed, then exits
    ├─ Step 3: pytest          — runs the pytest suite (parallel with Step 1)
    ├─ Step 4: upload-pytest-artifacts — uploads HTML report to GCS if tests failed, then exits
    ├─ Step 5: build           — docker build
    ├─ Step 6: push            — docker push to Artifact Registry
    │
    ├─ [feature-* branch only]
    │   ├─ Step 7: deploy_feature  — gcloud run deploy ${BRANCH_NAME}
    │   └─ Step 8: test_feature    — curl the deployed URL, grep "Support Tickets"
    │
    └─ [main branch only]
        ├─ Step 9: register_pipeline  — gcloud deploy apply (upserts pipeline/targets)
        └─ Step 10: create_release    — gcloud deploy releases create → triggers Cloud Deploy
                                                │
                                                ▼
                                        Cloud Deploy pipeline
                                                │
                                        ┌───────┴────────┐
                                        │  staging-env   │  (Cloud Run, 1 CPU / 512Mi)
                                        └───────┬────────┘
                                                │ Automation: promoteReleaseRule
                                                │ wait: 1 minute
                                                ▼
                                        ┌───────────────────┐
                                        │  production-env   │  (Cloud Run, 2 CPU / 1024Mi)
                                        └───────────────────┘
```

---

## Cloud Build — `cloudbuild.yaml`

### Substitution Variables

```yaml
substitutions:
  _LOCATION:    asia-south1-docker.pkg.dev
  _IMAGE:       emp-portal-repo/emp-portal-image
  _IMAGE_PATH:  ${_LOCATION}/${PROJECT_ID}/${_IMAGE}:${BRANCH_NAME}
  _DEPLOY_REGION: us-central1
```

`_IMAGE_PATH` resolves to a fully-qualified image reference that is unique per branch — e.g., `asia-south1-docker.pkg.dev/my-project/emp-portal-repo/emp-portal-image:main`. `dynamicSubstitutions: true` enables the nested `${}` references.

`$PROJECT_ID`, `$BRANCH_NAME`, and `$SHORT_SHA` are built-in Cloud Build variables injected at runtime.

---

### Step 1 — `lint_test`

```yaml
- name: "python"
  id: "lint_test"
  entrypoint: "bash"
  args:
    - "-c"
    - |
      pip install flake8-html \
      && flake8 --format=html --htmldir=flake_reports/ || lint_status=$?
      echo "$${lint_status:-0}" > lint_exit_code.txt
  allowFailure: true
```

- Uses the official `python` Cloud Build image.
- `allowFailure: true` — the step is allowed to exit non-zero without immediately failing the build. This is necessary because the next step needs to upload the report before terminating.
- The exit code is written to `lint_exit_code.txt` so the next step can read it. The `$${lint_status:-0}` syntax uses `:-0` as a default — if linting succeeded, `$lint_status` is unset, so the file contains `0`.

### Step 2 — `upload-lint-artifacts`

```yaml
- name: 'gcr.io/cloud-builders/gsutil'
  id: "upload-lint-artifacts"
  waitFor: ["lint_test"]
  args:
    - "-c"
    - |
      lint_status=$(cat lint_exit_code.txt)
      if [ "$lint_status" -ne 0 ]; then
        gsutil cp -r flake_reports/* gs://emp-portal-artifact/
        exit 1
      fi
```

- `waitFor: ["lint_test"]` — runs immediately after Step 1, regardless of Step 1's exit code.
- If lint failed: uploads the HTML report to GCS so developers can inspect it, then exits with code 1 to fail the build.
- If lint passed: does nothing and exits cleanly.

### Step 3 — `pytest`

```yaml
- name: "python"
  id: "pytest"
  waitFor: ["-"]
  args:
    - "-c"
    - |
      pip install pytest-html && pip install -r requirements.txt --user \
      && pytest --html=pytest_reports/pytest-report.html --self-contained-html \
      || pytest_status=$?
      echo "$${pytest_status:-0}" > pytest_exit_code.txt
  allowFailure: true
```

- `waitFor: ["-"]` — the `-` sentinel means "start immediately, do not wait for any prior step." This makes Step 3 run in **parallel** with Step 1 and Step 2, reducing total build time.
- `--self-contained-html` bundles CSS/JS into the HTML report so it is viewable without the surrounding directory.

### Step 4 — `upload-pytest-artifacts`

Same pattern as Step 2: waits for `pytest`, uploads to GCS on failure, exits 1 to fail the build.

### Step 5 — `build`

```yaml
- name: "gcr.io/cloud-builders/docker"
  id: "build"
  args: ['build', '-t', '${_IMAGE_PATH}', '.']
```

Builds the Docker image using the `Dockerfile` in the repo root. Tags it with the fully-qualified Artifact Registry path including the branch name.

### Step 6 — `push`

```yaml
- name: "gcr.io/cloud-builders/docker"
  id: "push"
  args: ['push', '${_IMAGE_PATH}']
  waitFor: ["build"]
```

Pushes the image to Artifact Registry. `waitFor: ["build"]` is explicit here to make the dependency clear (though it would be implied by ordering).

### Steps 7–8 — Feature branch deploy and smoke test

```yaml
- name: "gcr.io/google.com/cloudsdktool/cloud-sdk"
  id: "deploy_feature"
  args:
    - "-c"
    - |
      if [[ "$BRANCH_NAME" =~ ^feature-.*$ ]]; then
        gcloud run deploy "${BRANCH_NAME}" \
          --image "${_IMAGE_PATH}" \
          --region "${_DEPLOY_REGION}" \
          --allow-unauthenticated
      fi
```

- The `if` guard means the step is a no-op on non-feature branches. Cloud Build does not support conditional step execution natively, so this pattern wraps the logic in a bash conditional.
- Deploys a Cloud Run service named after the branch (e.g., `feature-my-change`). Each feature branch gets its own isolated preview URL.

```yaml
- name: "gcr.io/google.com/cloudsdktool/cloud-sdk"
  id: "test_feature"
  args:
    - "-c"
    - |
      if [[ "$BRANCH_NAME" =~ ^feature-.*$ ]]; then
        gcloud run services describe "${BRANCH_NAME}" \
          --region "${_DEPLOY_REGION}" \
          --format='value(status.url)' \
        | xargs -I {} curl -s "{}" \
        | grep "Support Tickets" && echo "Test passed" || (echo "Test failed" && exit 1)
      fi
```

- Retrieves the deployed Cloud Run URL with `gcloud run services describe ... --format='value(status.url)'`.
- Pipes it to `xargs curl` to fetch the home page.
- `grep "Support Tickets"` checks that the application is responding correctly. The string `"Support Tickets"` appears in the `<h1>` and `<title>` of `index.html`.

### Steps 9–10 — Main branch Cloud Deploy release

```yaml
- name: "gcr.io/google.com/cloudsdktool/cloud-sdk"
  id: "register_pipeline"
  args:
    - "-c"
    - |
      if [[ "$BRANCH_NAME" == "main" ]]; then
        gcloud deploy apply --file=./deploy/clouddeploy.yaml \
          --region=$_DEPLOY_REGION --project=$PROJECT_ID
      fi
```

`gcloud deploy apply` is idempotent — it creates or updates the Cloud Deploy pipeline, targets, and automation defined in `clouddeploy.yaml`. Running it on every main push ensures the pipeline definition stays in sync with the repository.

```yaml
- name: "gcr.io/google.com/cloudsdktool/cloud-sdk"
  id: "create_release"
  args:
    - "-c"
    - |
      if [[ "$BRANCH_NAME" == "main" ]]; then
        gcloud deploy releases create emp-portal-$SHORT_SHA \
          --delivery-pipeline emp-portal-pipeline \
          --region $_DEPLOY_REGION \
          --images app-image="${_IMAGE_PATH}"
      fi
```

- `emp-portal-$SHORT_SHA` creates a uniquely-named release per commit, making it easy to identify which commit is deployed.
- `--images app-image=...` substitutes the placeholder image name `app-image` in the Knative service manifests with the actual Artifact Registry image digest.

---

## Cloud Deploy — `deploy/clouddeploy.yaml`

### Delivery Pipeline

```yaml
apiVersion: deploy.cloud.google.com/v1
kind: DeliveryPipeline
metadata:
  name: emp-portal-pipeline
serialPipeline:
  stages:
  - targetId: staging-env
    profiles: [staging-profile]
  - targetId: production-env
    profiles: [production-profile]
```

Defines a two-stage serial pipeline. A release must pass through `staging-env` before it can reach `production-env`.

### Targets

```yaml
kind: Target
metadata:
  name: staging-env
run:
  location: projects/gcp-cicd-demo-123456/locations/us-central1
```

Each target is a Cloud Run location. Cloud Deploy renders the Knative service manifest using Skaffold and applies it to the Cloud Run endpoint for that project/region.

### Automation — Auto-promote

```yaml
kind: Automation
metadata:
  name: emp-portal-pipeline/promote
rules:
  - promoteReleaseRule:
      name: "promote-release"
      wait: 1m
      destinationTargetId: production-env
selector:
  targets:
    - id: staging-env
```

After a release is successfully deployed to `staging-env`, the automation waits **1 minute** then automatically promotes it to `production-env` without manual approval. The `selector` ensures this automation only fires for releases that land on `staging-env`.

---

## Skaffold — `skaffold.yaml`

```yaml
apiVersion: skaffold/v4beta11
kind: Config
profiles:
- name: staging-profile
  manifests:
    rawYaml:
    - ./deploy/deploy-staging.yaml
- name: production-profile
  manifests:
    rawYaml:
    - ./deploy/deploy-production.yaml
deploy:
  cloudrun: {}
```

Skaffold is the render/deploy engine used by Cloud Deploy. It applies the correct Knative service manifest based on the profile:

- `staging-profile` → `deploy-staging.yaml` (1 CPU / 512Mi memory)
- `production-profile` → `deploy-production.yaml` (2 CPU / 1024Mi memory)

Cloud Deploy passes the profile name from the delivery pipeline stage definition. Skaffold substitutes the `app-image` placeholder with the actual image path provided in the release.

---

## Knative Service Manifests

### Staging — `deploy/deploy-staging.yaml`

```yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: staging-app
spec:
  template:
    spec:
      containers:
      - image: app-image
        ports:
        - containerPort: 80
      resources:
        limits:
          cpu: 1000m
          memory: 512Mi
```

### Production — `deploy/deploy-production.yaml`

Same structure, but with doubled resources:

```yaml
resources:
  limits:
    cpu: 2000m
    memory: 1024Mi
```

Cloud Run uses Knative's serving API. The `image: app-image` placeholder is replaced by Skaffold with the real image digest at deploy time.

---

## Artifact Storage

Test and lint reports are uploaded to the GCS bucket `gs://emp-portal-artifact/` only on failure, keeping storage usage low. Reports can be downloaded and opened in a browser:

```bash
# Download lint report
gsutil cp -r gs://emp-portal-artifact/ ./reports/

# Open in browser
open reports/flake_reports/index.html
open reports/pytest_reports/pytest-report.html
```

---

## Branch Strategy Summary

| Branch | Lint | Test | Build & Push | Feature Deploy | Cloud Deploy |
|---|---|---|---|---|---|
| `feature-*` | Yes | Yes | Yes | Yes (preview URL) | No |
| `main` | Yes | Yes | Yes | No | Yes (staging → prod) |
| Any other | Yes | Yes | Yes | No | No |
