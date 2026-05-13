@echo off
title Agente MOP - INDEPENDIENTE (Sin tokens, sin internet)
color 2F
echo.
echo  =====================================================
echo   AGENTE MOP - MODO INDEPENDIENTE
echo  =====================================================
echo.
echo  - 100%% local (en tu PC)
echo  - Sin tokens, sin costos, sin limites
echo  - Sin necesidad de internet (despues de instalar)
echo.
echo  Iniciando interfaz web...
echo  Se abrira automaticamente en tu navegador.
echo.
echo  Para detener: cierra esta ventana o Ctrl+C
echo.

cd /d "%~dp0"
set PYTHONIOENCODING=utf-8

python -m streamlit run app_independiente.py --server.port 8502 --server.headless false --browser.gatherUsageStats false

pause
