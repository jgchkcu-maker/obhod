@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title Обход - установка

echo ============================================================
echo   Обход - установка всего, что нужно для запуска
echo   Запускать один раз. Потом открывать "Запустить Обход.cmd"
echo ============================================================
echo.

rem --- 1. Python 3.11-3.14 -------------------------------------------------
echo [1/4] Ищу Python...
set "PY="
call :try_python py -3.13
call :try_python py -3.12
call :try_python py -3.14
call :try_python py -3.11
call :try_python python
call :try_local_python
if defined PY goto have_python

echo       Python не найден, ставлю Python 3.13 через winget...
where winget >nul 2>&1 || goto no_winget
winget install -e --id Python.Python.3.13 --scope user --accept-package-agreements --accept-source-agreements
call :try_local_python
if defined PY goto have_python

:no_winget
echo.
echo [ОШИБКА] Не получилось поставить Python автоматически.
echo Скачайте Python 3.13 с python.org, при установке отметьте галочку
echo "Add python.exe to PATH", затем запустите этот файл ещё раз.
start "" "https://www.python.org/downloads/"
goto fail

:have_python
echo       Найден: %PY%
echo.

rem --- 2. Виртуальное окружение ------------------------------------------
echo [2/4] Готовлю окружение .venv...
if exist ".venv\Scripts\python.exe" (
    echo       Уже есть, пропускаю.
) else (
    %PY% -m venv .venv || goto venv_failed
)
echo.

rem --- 3. Библиотеки ------------------------------------------------------
echo [3/4] Ставлю библиотеки, это может занять несколько минут...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -e . || goto pip_failed
echo       Готово.
echo.

rem --- 4. winws и списки --------------------------------------------------
echo [4/4] Проверяю winws и списки...
if exist "bin\winws.exe" (
    echo       На месте.
) else (
    ".venv\Scripts\python.exe" scripts\fetch_vendor.py || goto vendor_failed
)
echo.

echo ============================================================
echo   Установка завершена.
echo ============================================================
echo.
set "ANSWER="
set /p "ANSWER=Создать ярлык на рабочем столе? [Y/N]: "
if /i "%ANSWER%"=="Y" ".venv\Scripts\python.exe" scripts\create_shortcut.py
set "ANSWER="
set /p "ANSWER=Запустить Обход сейчас? [Y/N]: "
if /i "%ANSWER%"=="Y" call "%~dp0Запустить Обход.cmd"
exit /b 0

rem --- помощники ------------------------------------------------------------
:try_python
if defined PY exit /b 0
%* -c "import sys; sys.exit(0 if (3, 11) <= sys.version_info[:2] <= (3, 14) else 1)" >nul 2>&1 && set "PY=%*"
exit /b 0

:try_local_python
if defined PY exit /b 0
for %%V in (313 312 314 311) do (
    if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" set PY="%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe"
)
exit /b 0

:venv_failed
echo [ОШИБКА] Не удалось создать .venv.
goto fail

:pip_failed
echo [ОШИБКА] Не удалось поставить библиотеки. Проверьте интернет;
echo если включён VPN или обход - попробуйте с ним и без него.
goto fail

:vendor_failed
echo [ОШИБКА] Не удалось скачать winws и списки Flowseal.
goto fail

:fail
echo.
pause
exit /b 1
