# AI Surveillance System

> **GirlScript Summer of Code (GSSoC) Edition** :star2:

A production-minded missing-person surveillance workflow built with a Next.js operator console and a FastAPI + computer vision backend. This platform is designed for fast operator decisions using video analysis, real-time bounding boxes, and PDF evidence generation.

---

## 📑 Table of Contents
1. [Overview & Architecture](#overview--architecture)
2. [Prerequisites](#prerequisites)
3. [Local Setup & Run](#local-setup--run)
4. [GSSoC Contribution Pipeline](#gssoc-contribution-pipeline)
5. [The "Local Sanity Check"](#the-local-sanity-check)
6. [Vercel Preview Deployment Guide](#vercel-preview-deployment-guide)
7. [Project Structure](#project-structure)

---

## 🏗️ Overview & Architecture

1. **Upload Phase**: Operator uploads a reference image + CAM-1/CAM-2 video clips.
2. **Analysis Job**: Frontend sends files to the backend `/api/analyze` with a selected performance profile (Fast, Balanced, Accurate).
3. **Async Workers**: Backend creates a session and starts Celery-based analysis workers.
4. **Live Polling**: Frontend polls real-time progress and detection alerts.
5. **Review & Export**: Operator reviews the timeline and exports a formal, branded PDF report.

**Tech Stack**: 
- **Frontend**: Next.js 16, React 19, Tailwind CSS 4
- **Backend**: FastAPI, OpenCV, DeepFace, Ultralytics YOLO

---

## ⚙️ Prerequisites

Before you begin contributing, ensure your environment meets the following specifications:

| Requirement | Version | Notes |
| --- | --- | --- |
| **Node.js** | `v20.x` | Required for Next.js frontend development. |
| **npm** | `v10.x` | Standard package manager (comes with Node 20). |
| **Python** | `3.11+` | Required for the FastAPI + OpenCV backend. |
| **Git** | `Latest` | Required for version control and Husky hooks. |

---

## 💻 Local Setup & Run

### 1. Automated Setup (Recommended for Windows)
If you're on Windows, simply run the PowerShell script to bootstrap the entire project:
```powershell
powershell -ExecutionPolicy Bypass -File .\setup_system.ps1
```
After setup is complete, you can launch the app daily using:
```powershell
powershell -ExecutionPolicy Bypass -File .\run_full_project.ps1
```

### 2. Manual Startup

**Frontend (Next.js)**
```bash
cd frontend
npm install
npm run dev
```

**Backend (FastAPI)**
```bash
cd backend
python -m venv .venv
# Activate venv:
# Windows: .venv\Scripts\activate
# Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload --port 8001
```

---

## 🚀 GSSoC Contribution Pipeline

We welcome hundreds of contributors during GSSoC! To manage this scale cleanly, we have a fully automated CI/CD pipeline. Here is exactly what happens when you open a Pull Request targeting the `main` or `dev` branches:

1. **Dependency Caching**: Our GitHub Actions pipeline caches `npm` and `pip` dependencies for blazing fast test runs.
2. **Code Linting & Formatting**: We run `ESLint` and `Prettier` (frontend) and `Ruff` and `Black` (backend) to ensure structural and stylistic perfection.
3. **Type Checking**: We compile TypeScript using `tsc --noEmit` to catch any breaking type shifts.
4. **Build Verification**: We build the Next.js app to guarantee it won't crash in production.
5. **Vercel Preview Deployments**: Vercel will automatically spin up an ephemeral deployment of your exact PR code so maintainers can test the UI live. 

> [!IMPORTANT]
> All automated checks (Lint, Build, Types) **must pass** before a Project Admin will review or merge your Pull Request. 

---

## ✅ The "Local Sanity Check"

To prevent your Pull Request from failing the CI pipeline and causing delays, you must run our "Local Sanity Check" before pushing your code. We have integrated **Husky** and **lint-staged** to automatically check your code when you commit, but you can also manually verify everything.

Run these explicit commands in your terminal (inside the `frontend` directory):

```bash
cd frontend

# 1. Check for any ESLint warnings or errors
npm run lint

# 2. Format all your code perfectly
npm run format

# 3. Verify the app builds without crashing
npm run build
```

If these three commands pass locally, your Pull Request is mathematically almost guaranteed to pass the GitHub Actions CI workflow! 🎉

---

## 🌐 Vercel Preview Deployment Guide

Because this project is deployed via Vercel, every Pull Request gets its own **live preview URL**. 

1. **Find the Link**: After opening your PR, scroll down to the "Checks" section. The **vercel** bot will leave a comment and a check-mark with a link saying `Deploy Preview`.
2. **Test Live**: Click the link to view your code running on a live `.vercel.app` domain. 
3. **Collaboration Toolbar**: On the preview site, you will see a Vercel Toolbar at the bottom of the screen. You can use this to leave comments directly on UI elements for the maintainers!

*(Note: The backend API requires long-running background workers and is hosted separately from Vercel. The preview deployment specifically handles the Next.js frontend.)*

---

## 📁 Project Structure

```text
├── backend/                  # FastAPI API, Celery async jobs, CV engine
├── frontend/                 # Next.js operator UI
├── .github/                  # CI/CD Workflows & Issue/PR Templates
├── vercel.json               # Root routing config for Vercel deployment
├── setup_system.ps1          # One-time bootstrap script (Windows)
└── run_full_project.ps1      # Standard start script
```

---

## ❓ Troubleshooting

- **Backend offline in UI**: Verify backend is running on port 8001 and check `NEXT_PUBLIC_BACKEND_URL`.
- **No alerts appearing**: Try `Fast` profile for earliest detection signal. Check `/api/progress/{session_id}` for `failed` state.
- **Git Commit fails (Husky)**: If your commit is rejected by Husky, read the terminal output! It usually means you have unformatted code. Run `npm run format` inside the `frontend` folder and try committing again.

---

### Developed By
- **Name**: Ayush Kathil
- **LinkedIn**: [Ayush Kathil](https://www.linkedin.com/in/ayushkathil/)
- **GitHub**: [@Ayush-kathil](https://github.com/Ayush-kathil)
