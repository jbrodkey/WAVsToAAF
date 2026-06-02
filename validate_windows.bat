@echo off
REM Automated validation script for WAVsToAAF Windows build

SET EXE_PATH=dist\WAVsToAAF.exe

REM 1. Check if executable exists
IF NOT EXIST "%EXE_PATH%" (
    echo Error: Executable not found at %EXE_PATH%
    exit /b 1
)
echo Executable found: %EXE_PATH%

echo Checking executable launch...
"%EXE_PATH%" --version
IF ERRORLEVEL 1 (
    echo Error: Executable failed to run with --version
    IF EXIST "%TEMP%\wavtoaaf_startup.log" (
        echo Startup wrapper log:
        type "%TEMP%\wavtoaaf_startup.log"
    )
    exit /b 1
)
echo Executable launched successfully.

REM 2. Check file size (should be substantial for a bundled app)
FOR %%A IN ("%EXE_PATH%") DO (
    echo File size: %%~zA bytes
)

IF EXIST "%TEMP%\wavtoaaf_startup.log" (
    echo Warning: startup log exists at %TEMP%\wavtoaaf_startup.log
    type "%TEMP%\wavtoaaf_startup.log"
)

echo Validation complete.
