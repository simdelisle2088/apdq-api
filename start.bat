@echo off
:: start.bat
setlocal

IF "%1"=="" (
    SET APP_ENV=local
) ELSE (
    SET APP_ENV=%1
)

echo Starting application in %APP_ENV% environment...

IF NOT EXIST ".env.%APP_ENV%" (
    echo Error: Environment file .env.%APP_ENV% not found!
    exit /b 1
)

:: You would have to parse the .env file to set HOST=..., PORT=...
:: This is non-trivial in a .bat file.

:: But if you manually know host/port from the file, you can do:
uvicorn server.main:app --reload --host 0.0.0.0 --port 8000

endlocal
