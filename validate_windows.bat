@echo off
REM Automated validation script for WAVsToAAF Windows build

SET EXE_PATH=dist\WAVsToAAF\WAVsToAAF.exe

REM 1. Check if executable exists
IF NOT EXIST "%EXE_PATH%" (
    echo Error: Executable not found at %EXE_PATH%
    exit /b 1
)
echo Executable found: %EXE_PATH%

REM 2. Check if data folder exists
IF NOT EXIST "dist\WAVsToAAF\data" (
    echo Warning: Data folder not found in distribution folder.
) ELSE (
    echo Data folder found in distribution folder.
)

REM 3. Attempt to launch the app (headless)
echo Skipping app launch test - requires GUI environment
echo Validation complete.
