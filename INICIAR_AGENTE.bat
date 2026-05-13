@echo off
title Agente MOP - Manual de Carreteras
color 1F
echo.
echo  =====================================================
echo   AGENTE MOP - Manual de Carreteras de Chile
echo  =====================================================
echo.
echo  Iniciando interfaz web...
echo  Se abrira automaticamente en tu navegador.
echo.
echo  Para detener el agente: cierra esta ventana
echo  o presiona Ctrl+C
echo.

cd /d "%~dp0"
set PYTHONIOENCODING=utf-8

python -m streamlit run app_publica.py --server.port 8501 --server.headless false --browser.gatherUsageStats false

pause
