@echo off
setlocal
cd /d "%~dp0.."
rem Projektwurzel = Ordnername von START.bat + ".." (config, .venv, dist liegen dort).
set "BAKI="
if exist "%~dp0..\BakiAIO\baki.py" if exist "%~dp0..\.venv\Scripts\python.exe" set BAKI="%~dp0..\.venv\Scripts\python.exe" "%~dp0..\BakiAIO\baki.py"
if not defined BAKI if exist "%~dp0..\dist\BakiAIO.exe" set BAKI="%~dp0..\dist\BakiAIO.exe"
if not defined BAKI if exist "%~dp0..\BakiAIO.exe" set BAKI="%~dp0..\BakiAIO.exe"
if not defined BAKI echo Weder baki.py mit .venv noch BakiAIO.exe gefunden.
if not defined BAKI pause
if not defined BAKI exit /b 1
if not exist "%~dp0..\config\profiles.yaml" echo Hinweis: config\profiles.yaml fehlt. Setup: Menue 1 (Topps EU), dann 7.
%BAKI%
exit /b %errorlevel%
