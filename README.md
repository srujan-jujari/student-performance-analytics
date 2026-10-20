# Student Performance Analytics

A starter project for a cloud-based student performance analytics and risk
detection application built with Flask, Pandas, NumPy, Bootstrap, Chart.js,
Cloudinary, and Render.

This repository is an initial scaffold, not a complete analytics or risk
detection system. The included CSV contains synthetic example data only.

## Run locally

From the project folder in PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
py app.py
```

Open <http://127.0.0.1:5000/> in a browser. No cloud credentials are needed to
view the starter pages. To prepare local environment configuration later, copy
`.env.example` to `.env` and add your own credentials. Keep `.env` out of source
control.

Run the starter tests with:

```powershell
py -m pytest
```

## Project files

- `app.py` — Flask upload, analysis, CSRF-protected Cloudinary storage routes.
- `analytics.py` — small starting point for reusable analysis functions.
- `cloud_storage.py` — server-side authenticated Cloudinary uploads.
- `requirements.txt` — Python package dependencies.
- `.env.example` — names of local environment settings; contains no real secrets.
- `.gitignore` — excludes credentials, virtual environments, and generated files.
- `templates/` — shared page layout and starter pages.
- `static/css/style.css` — project-specific styles.
- `static/js/dashboard.js` — dashboard charts, filters, downloads, and storage form submission.
- `tests/test_analytics.py` — starter tests for analytics helpers.
- `sample_data/student_performance.csv` — synthetic sample data.

## Data and deployment notes

- Use synthetic student records during development and demos.
- Keep Cloudinary API secrets on the server in environment variables. Never
  expose them through HTML or JavaScript.
- Set a strong, stable `FLASK_SECRET_KEY` in `.env` for local development and
  in the deployment environment. Set `SESSION_COOKIE_SECURE=true` when serving
  over HTTPS. POST forms use session-bound CSRF tokens, but this starter
  project does not implement authenticated user accounts or multi-user
  authorization.
- Cloudinary storage buttons revalidate the submitted CSV before storage. Source
  CSVs and analyzed reports are uploaded as authenticated raw assets; the app
  does not return public URLs. The dashboard keeps its current data in the page
  only and does not persist it on Render's local filesystem or in the session.
- Do not rely on Render's local filesystem for permanent uploads. The planned
  upload flow sends files to Cloudinary and avoids retaining them on the
  application disk.
- Validate locally before configuring cloud storage or deploying to Render.
