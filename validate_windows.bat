@echo off
REM Automated validation script for WAVsToAAF Windows build

SET EXE_PATH=dist\WAVsToAAF.exe

REM 1. Check if executable exists
IF NOT EXIST "%EXE_PATH%" (
    echo Error: Executable not found at %EXE_PATH%
    exit /b 1
)
echo Executable found: %EXE_PATH%

REM 2. Check file size (should be substantial for a bundled app)
FOR %%A IN ("%EXE_PATH%") DO (
    echo File size: %%~zA bytes
)

echo Validation complete.
