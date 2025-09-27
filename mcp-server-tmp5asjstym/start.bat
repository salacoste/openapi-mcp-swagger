@echo off
rem Startup script for test MCP Server

cd /d "%~dp0"

rem Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is required but not found
    exit /b 1
)

rem Check if virtual environment exists
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

rem Activate virtual environment
call venv\Scripts\activate.bat

rem Install dependencies
if exist "requirements.txt" (
    echo Installing dependencies...
    pip install -r requirements.txt
)

rem Start server
echo Starting Test MCP Server...
python server.py %*
