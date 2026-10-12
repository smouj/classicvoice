@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-ClassicVoice.ps1"
if errorlevel 1 (
  echo.
  echo No se pudo instalar ClassicVoice. Comprueba el mensaje anterior y vuelve a intentarlo.
  pause
)
