@echo off
rem Запуск приложения Windows (без окна консоли)
cd /d "%~dp0"
start "" pythonw.exe launcher.py
