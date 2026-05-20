Deployment checklist

This document lists steps and files you should verify before pushing or deploying to production.

Environment
- Ensure `.env` (local) is NOT committed (it's in .gitignore).
- Provide production environment variables in your deployment platform or secret store: `DATABASE_URL`, `ASYNC_DATABASE_URL`, `REDIS_URL`, `AUTH_API_KEY`, `SECRET_KEY`.

Database
- Apply migrations:
  ```bash
  alembic upgrade head
  ```
- Verify the `model_versions`, `worker_runs`, and `scoring_failures` tables exist.

Services
- Start the API server (example):
  ```bash
  uvicorn app.main:app --host 0.0.0.0 --port 8000
  ```
- Start background workers (if running separately):
  ```bash
  python -m app.tasks.worker_entrypoint profile
  python -m app.tasks.worker_entrypoint dlq
  ```

Metrics & Monitoring
- Configure Prometheus to scrape `http://<host>:8000/metrics/prometheus` (see `deploy/prometheus/prometheus.yml`).
- Load `deploy/alertmanager/rules.yml` into your Alertmanager instance.

Model governance
- Retrain runs in-app daily (03:00 UTC) and registers candidate versions in DB.
- Promotion is manual: use the GitHub Actions `promote_manual` workflow or `tools/promote_model.py` with your `ASYNC_DATABASE_URL`.

CI & Pre-commit
- Install pre-commit hooks locally:
  ```bash
  pip install pre-commit
  pre-commit install
  pre-commit run --all-files
  ```

Security
- Rotate `AUTH_API_KEY` and other secrets via your secrets manager; do not commit them.
- Restrict access to `/api/v1/model_registry/admin` behind VPN or stronger auth.

Backups & Rollback
- Ensure DB backups are configured and you have a rollback plan before promoting models or applying migrations.

If you want, I can add a small `docker-compose.yml` that starts the app + Postgres + Redis + Prometheus + Alertmanager for local testing.
