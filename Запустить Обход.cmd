@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist "%~dp0dist\Obhod\Obhod.exe" (
    start "" "%~dp0dist\Obhod\Obhod.exe"
    exit /b
)
if exist "%~dp0.venv\Scripts\pythonw.exe" (
    start "" "%~dp0.venv\Scripts\pythonw.exe" -m obhod
    exit /b
)
echo Не найдено приложение. Откройте README.md: раздел «Сборка из исходников».
pause

