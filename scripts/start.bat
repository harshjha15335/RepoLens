@echo off
echo ====================================================
echo Starting CodeMentor-RAG (Backend + Frontend)
echo ====================================================

start "CodeMentor-RAG Backend" cmd /k "cd /d %~dp0..\backend && uvicorn app.main:app --reload --port 8000"
timeout /t 3 >nul

start "CodeMentor-RAG Frontend" cmd /k "cd /d %~dp0..\frontend && npm run dev"
timeout /t 3 >nul

echo.
echo Services launched:
echo  - Backend API:  http://localhost:8000 (Docs: http://localhost:8000/docs)
echo  - Frontend App: http://localhost:3000
echo.
pause
