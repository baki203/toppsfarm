@echo off
setlocal
cd /d "%~dp0"
if not exist "dist\toppsfarm.exe" ( echo EXE fehlt. & pause & exit /b 1 )
if not exist "config\profiles.yaml" ( dist\toppsfarm.exe setup & pause )
:menu
cls
echo ============================================
echo   TOPPSFARM
echo ============================================
echo  1  Selftest
echo  2  Watch  - Cart-Links (wenig Daten)
echo  3  Watch  - mit Browser
echo  4  Drop auf Variante
echo  5  Profile pruefen
echo  6  Statistik
echo  7  Setup erneut ausfuehren
echo  8  Browser-Engine installieren
echo  0  Ende
echo ============================================
set /p wahl= Auswahl: 
if "%wahl%"=="1" dist\toppsfarm.exe selftest & pause & goto menu
if "%wahl%"=="2" dist\toppsfarm.exe watch --mode cart & pause & goto menu
if "%wahl%"=="3" dist\toppsfarm.exe watch --mode browser & pause & goto menu
if "%wahl%"=="4" ( set /p host= Host: & set /p vid= Variant-ID: & set /p n= Tasks: & dist\toppsfarm.exe drop --host %host% --variant %vid% --tasks %n% --mode cart & pause & goto menu )
if "%wahl%"=="5" dist\toppsfarm.exe profiles-check & pause & goto menu
if "%wahl%"=="6" dist\toppsfarm.exe stats & pause & goto menu
if "%wahl%"=="7" dist\toppsfarm.exe setup & pause & goto menu
if "%wahl%"=="8" dist\toppsfarm.exe install-browser & pause & goto menu
if "%wahl%"=="0" exit /b 0
goto menu
