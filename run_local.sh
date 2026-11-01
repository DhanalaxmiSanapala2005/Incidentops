#!/usr/bin/env bash
# Starts mock services (8001), API (8000, SQLite) and Streamlit UI (8501) without Docker.
set -e; cd "$(dirname "$0")"; export PYTHONPATH="$PWD"
pip install -q -r requirements.txt
uvicorn integrations.mock_app:app --port 8001 & uvicorn backend.main:app --port 8000 &
trap 'kill 0' EXIT; sleep 3
streamlit run frontend/app.py --server.port 8501
