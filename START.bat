@echo off
setlocal
cd /d "%~dp0"
rem Aus dem Quelltext (baki.py), wenn eine venv da ist, sonst die gebaute Exe.
set "BAKI="
if exist "%~dp0baki.py" if exist "%~dp0.venv\Scripts\python.exe" set BAKI="%~dp0.venv\Scripts\python.exe" "%~dp0baki.py"
if not defined BAKI if exist "%~dp0dist\BakiAIO.exe" set BAKI="%~dp0dist\BakiAIO.exe"
if not defined BAKI if exist "%~dp0BakiAIO.exe" set BAKI="%~dp0BakiAIO.exe"
if not defined BAKI echo Weder baki.py mit .venv noch BakiAIO.exe gefunden.
if not defined BAKI pause
if not defined BAKI exit /b 1
if not exist "%~dp0config\profiles.yaml" %BAKI% topps setup
if not exist "%~dp0config\profiles.yaml" pause
%BAKI%
exit /b %errorlevel%
