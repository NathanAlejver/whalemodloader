@echo off
REM Go to this script's directory
cd /d "%~dp0"

set OUTPUT_NAME=WhaleModLoader

echo.
echo Building %OUTPUT_NAME%.exe ...
echo.

python -m PyInstaller --clean --onefile --noconsole --name "%OUTPUT_NAME%" --add-data "assets\icons;assets\icons" --icon "assets\icons\icon.ico" gui_run.py

IF ERRORLEVEL 1 (
    echo.
    echo Build FAILED. Check the error messages above.
    pause
    exit /b 1
)

echo.
echo Build finished. Moving exe...

REM Move exe from dist\ to current folder (overwrite silently)
IF EXIST "dist\%OUTPUT_NAME%.exe" (
    move /Y "dist\%OUTPUT_NAME%.exe" "%~dp0" >NUL
)

REM Remove dist folder
IF EXIST "dist" (
    rmdir /S /Q "dist"
)

REM Delete the build and .spec file
IF EXIST "build" (
    rmdir /S /Q "build"
)
IF EXIST "%OUTPUT_NAME%.spec" (
    del /Q "%OUTPUT_NAME%.spec"
)

echo.
echo Done! New %OUTPUT_NAME%.exe is in:
echo %~dp0
echo.
pause
