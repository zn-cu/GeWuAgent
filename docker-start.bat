@echo off
setlocal
cd /d "%~dp0"

echo ==========================================================
echo   Gewu - start local docker services
echo   Milvus + etcd + MinIO + Attu + MongoDB
echo   (Chinese doc: docker\README.md)
echo ==========================================================
echo.

docker info >nul 2>&1
if errorlevel 1 goto nodocker

echo [1/2] starting containers, first Milvus start takes 1-2 min ...
echo.
docker compose up -d
if errorlevel 1 goto failed
goto status

:nodocker
echo [ERROR] Docker is not running. Start Docker Desktop first.
goto end

:failed
echo.
echo [FAILED] docker compose up did not succeed. Common causes:
echo   1. old containers still own these names - run docker-stop.bat first
echo   2. ports 19530 / 27017 / 3000 / 9002 / 9003 already in use
echo   3. images not pulled yet, or network problem
goto end

:status
echo.
echo [2/2] current status:
docker compose ps --format "table {{.Name}}\t{{.Service}}\t{{.Status}}\t{{.Ports}}"
echo.
echo ----------------------------------------------------------
echo   Milvus   127.0.0.1:19530   health http://127.0.0.1:9091/healthz
echo   Attu     http://127.0.0.1:3000
echo   MinIO    http://127.0.0.1:9003   data port 9002
echo   MongoDB  127.0.0.1:27017
echo ----------------------------------------------------------
echo   Python services are NOT in docker, start them separately:
echo     uvicorn app.import_process.api.file_import_service:app --host 0.0.0.0 --port 8000 --reload
echo     uvicorn app.query_process.api.query_server:app --host 0.0.0.0 --port 8001 --reload
echo ----------------------------------------------------------

:end
echo.
pause
