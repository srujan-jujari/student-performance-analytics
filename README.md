# Student Performance Analytics

A starter project for a cloud-based student performance analytics and risk
detection application built with Flask, Pandas, NumPy, Bootstrap, Chart.js,
Amazon S3, and Render.

This project provides a working CSV analytics flow and a demonstration risk
classification model. Use synthetic student records for development and demos.

## Run locally

From the project folder in PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
py app.py
```

Open <http://127.0.0.1:5000/> in a browser. No cloud credentials are needed to
view the application or analyze a CSV. To enable S3 uploads locally, copy
`.env.example` to `.env` and configure your AWS credentials. Keep `.env` out of
source control.

Run the starter tests with:

```powershell
py -m pytest -q
```

## Project files

- `app.py` — Flask upload, analysis, and CSRF-protected storage routes.
- `analytics.py` — small starting point for reusable analysis functions.
- `cloud_storage.py` — server-side private Amazon S3 uploads.
- `requirements.txt` — Python package dependencies.
- `.env.example` — local Flask and AWS environment settings; contains no real secrets.
- `.gitignore` — excludes credentials, virtual environments, and generated files.
- `templates/` — shared page layout and starter pages.
- `static/css/style.css` — project-specific styles.
- `static/js/dashboard.js` — dashboard charts, filters, downloads, and storage form submission.
- `tests/test_analytics.py` — starter tests for analytics helpers.
- `tests/` — analytics, upload-route, and mocked S3 tests.

## Data and deployment notes

- Use synthetic student records during development and demos.
- Configure `AWS_REGION` and `AWS_S3_BUCKET` for S3 uploads. For local
  development, set both `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` in
  `.env`, or use the standard AWS credential chain. Never expose AWS
  credentials through HTML or JavaScript.
- Set a strong, stable `FLASK_SECRET_KEY` in `.env` for local development and
  in the Render environment. Set `SESSION_COOKIE_SECURE=true` when serving over
  HTTPS. POST forms use session-bound CSRF tokens, but this starter project
  does not implement authenticated user accounts or multi-user authorization.
- The storage buttons revalidate the submitted CSV before upload. Source CSVs
  and generated reports are uploaded to the configured S3 bucket under
  `student-performance-analytics/source/` and
  `student-performance-analytics/report/` with unique object keys. Uploads use
  server-side encryption, do not set public ACLs, and do not return public
  URLs. The dashboard keeps its current data in the page only and does not
  persist it on Render's local filesystem or in the session.
- Storage forms use asynchronous requests so saving either asset preserves the
  current dashboard and the separate status for each action.
- Do not rely on Render's local filesystem for permanent uploads. Configure
  `AWS_REGION`, `AWS_S3_BUCKET`, `AWS_ACCESS_KEY_ID`, and
  `AWS_SECRET_ACCESS_KEY` as Render environment variables for the deployed
  service. Keep credentials out of the repository and never expose them to the
  browser.
- Validate locally before deploying to Render. This documentation does not
  change the existing Render service or its deployment settings.
