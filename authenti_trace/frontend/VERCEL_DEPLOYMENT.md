# AuthentiTrace Vercel Deployment Guide

This guide deploys the Next.js frontend to Vercel and connects it to your FastAPI backend.

## 1. What Is Deployed to Vercel

- Deployed on Vercel: `authenti_trace/frontend` (Next.js app)
- Not deployed on Vercel in this guide: `authenti_trace/backend` (FastAPI)

You should host the backend on a Python-friendly platform (for example Render, Railway, Fly.io, or Azure/App Service).

## 2. Changes Already Applied for Deployment Safety

Two code changes were made so deployment is cleaner:

1. Frontend API URL fallback logic:
- File: `frontend/src/lib/api.ts`
- Behavior:
  - Development defaults to `http://localhost:8000`
  - Production no longer hardcodes localhost
  - If `NEXT_PUBLIC_API_URL` is missing in production, requests use relative paths

2. Backend CORS is now environment-driven:
- File: `backend/app/main.py`
- New env var: `CORS_ALLOW_ORIGINS`
- Format: comma-separated origins
- Default still supports local dev origins

## 3. Prerequisites

- GitHub repository pushed
- Vercel account connected to GitHub
- Backend deployed and publicly reachable over HTTPS
- Backend API working (test `/docs` and `/api/v1/dashboard/metrics`)

## 4. Deploy Frontend to Vercel (Step by Step)

1. Open Vercel Dashboard.
2. Click Add New Project.
3. Import your GitHub repository.
4. In Project Settings, set Root Directory to:
   - `authenti_trace/frontend`
5. Framework should auto-detect as Next.js.
6. Build command should be auto-detected (`next build`).
7. Add Environment Variable:
   - Name: `NEXT_PUBLIC_API_URL`
   - Value: your backend URL, for example `https://your-backend-domain.com`
8. Click Deploy.

## 5. Configure Backend CORS for Vercel Domain

After first Vercel deployment, you will get a URL like:
- `https://your-project-name.vercel.app`

Set backend env var:

- Name: `CORS_ALLOW_ORIGINS`
- Value example:
  - `https://your-project-name.vercel.app,https://www.yourcustomdomain.com`

If you do not have a custom domain yet, use only the Vercel domain first.

## 6. Redeploy Backend and Frontend

1. Restart or redeploy backend so CORS env vars are active.
2. Redeploy frontend from Vercel dashboard (or push a commit).

## 7. Post-Deploy Verification Checklist

1. Open deployed frontend URL.
2. Verify navigation works:
   - `/`
   - `/upload`
   - `/dashboard`
3. Upload a file on `/upload`.
4. Confirm redirect to dynamic route `/report/{id}`.
5. Open `/dashboard` and verify metrics/audit are loading.
6. Open browser devtools and ensure no CORS errors.

## 8. Common Issues and Fixes

### Issue: Requests still hit localhost in production

- Cause: old frontend build or missing env var
- Fix:
  1. Set `NEXT_PUBLIC_API_URL` in Vercel project env vars
  2. Redeploy frontend

### Issue: CORS blocked by backend

- Cause: `CORS_ALLOW_ORIGINS` not set correctly
- Fix:
  1. Include exact Vercel origin in backend env var
  2. Redeploy backend

### Issue: Upload works locally but fails in production

- Check backend file upload limits and storage path permissions
- Confirm backend platform allows multipart uploads and sufficient disk or object storage

## 9. Recommended Production Hardening

1. Use PostgreSQL instead of SQLite for backend production workloads.
2. Add authentication and rate limiting.
3. Use object storage for media files.
4. Add HTTPS custom domain for frontend and backend.
5. Add monitoring and error alerts.

## 10. Quick Reference

Frontend env (Vercel):
- `NEXT_PUBLIC_API_URL=https://your-backend-domain.com`

Backend env:
- `CORS_ALLOW_ORIGINS=https://your-project-name.vercel.app,https://www.yourcustomdomain.com`
