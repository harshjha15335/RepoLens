#!/usr/bin/env bash
echo "===================================================="
echo "Starting CodeMentor-RAG (Backend + Frontend)"
echo "===================================================="

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Start backend
(cd "$DIR/../backend" && uvicorn app.main:app --reload --port 8000) &
BACKEND_PID=$!

# Wait for backend
sleep 3

# Start frontend
(cd "$DIR/../frontend" && npm run dev) &
FRONTEND_PID=$!

echo ""
echo "Services launched:"
echo " - Backend API:  http://localhost:8000 (Docs: http://localhost:8000/docs)"
echo " - Frontend App: http://localhost:3000"
echo ""

trap "kill $BACKEND_PID $FRONTEND_PID" EXIT
wait
