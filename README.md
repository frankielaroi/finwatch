# FinWatch Backend Deployment

This repository now includes a production-oriented split between the API process and the background workers.

## Runtime Layout

- `uvicorn app.main:app` runs the API only.
- `python scripts/run_profile_worker.py` runs the profile ingestion/matching worker.
- `python scripts/run_dlq_worker.py` runs the DLQ retry worker.

## Local Docker Compose

1. Copy `.env.example` to `.env` and fill in secrets.
2. Build and start the stack.

```bash
docker compose up --build
```

Services included:
- `postgres`
- `redis`
- `migrate`
- `api`
- `profile-worker`
- `dlq-worker`

## Systemd

Copy the unit files from `deploy/systemd/` into `/etc/systemd/system/`, update paths if needed, then enable them.

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now finwatch-api
sudo systemctl enable --now finwatch-profile-worker
sudo systemctl enable --now finwatch-dlq-worker
```

## Notes

- Run migrations before starting workers if you deploy manually.
- Keep API, profile worker, and DLQ worker as separate processes so scaling and restarts are independent.
- Keep Redis and Postgres on managed services if possible.
- Set `AUTH_API_KEY` in production and send it as `X-API-Key` on requests to `/api/v1/*`.
- Audit records are written to `audit_logs` for authenticated API traffic.
