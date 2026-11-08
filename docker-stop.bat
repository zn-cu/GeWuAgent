@echo off
setlocal
cd /d "%~dp0"

echo ==========================================================
echo   Gewu - stop local docker services
echo   (Chinese doc: docker\README.md)
echo ==========================================================
echo.
echo Containers are removed, data is kept (no -v used).
echo.

docker compose down
if errorlevel 1 goto failed
goto stopped

:failed
echo.
echo [WARN] docker compose down failed.
echo        Stop the "gewu" group in Docker Desktop manually.
goto end

:stopped
echo.
echo Stopped. To delete the data as well (DANGEROUS):
echo   docker compose down -v

:end
echo.
pause
