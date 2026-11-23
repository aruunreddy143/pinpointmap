# Deploy to free tiers (demo/pilot)

Frontend: Cloudflare Pages. Backend: Render (free web service). Database: Neon (free Postgres with PostGIS).

## 1. Database (Neon)
1. Create a project, then in the SQL editor run `CREATE EXTENSION IF NOT EXISTS postgis;`
2. Copy the connection string and change the scheme to `postgresql+psycopg://` (keep `?sslmode=require`).

## 2. Backend (Render)
1. New > Blueprint > pick this GitHub repo (uses `render.yaml`).
2. Set `PINPOINT_DATABASE_URL`, `PINPOINT_PUBLIC_BASE_URL` (the Pages URL) and
   `PINPOINT_CORS_ORIGINS` as a JSON list, e.g. `["https://pinpoint.pages.dev"]`.
3. Deploy. The container runs `alembic upgrade head` on every start. First request after idle takes ~30-60 s.
4. Seed the first admin once from the Render shell: `python scripts/seed_dev.py` (dev data; create a real admin instead for anything beyond a demo).

## 3. Frontend (Cloudflare Pages)
- Root directory `frontend`, build command `npm ci && npm run build`, output `dist`.
- Build variables: `VITE_API_BASE_URL` (the Render URL), `VITE_PUBLIC_BASE_URL` (the Pages URL), `VITE_MAP_STYLE_URL` (a MapTiler/Stadia style; OSM tiles are dev-only).
- `public/_redirects` makes React Router deep links work.

## Known gaps before real use
- `app/providers/notify.py` raises in production until an email/SMS provider is added, so one-time codes and invites will not send. Add an email provider (e.g. Resend) first.
- If the browser and API are on different domains, check the refresh-token cookie (SameSite=None; Secure) and CORS.
- Free tiers: Render sleeps when idle; Neon is ~0.5 GB. Not for production load.
