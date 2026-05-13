@echo off
title Crear Instalador Escritorio - Agente MOP
color 1F
echo.
echo  ============================================
echo   CREANDO PAQUETE DE ESCRITORIO - AGENTE MOP
echo  ============================================
echo.

set "PROYECTO=C:\Users\mathias.yanez\agente_mop"
set "DESTINO=C:\Users\mathias.yanez\Desktop\AgenteMOP_Instalador"

echo [1/5] Creando estructura del instalador...
mkdir "%DESTINO%" 2>nul
mkdir "%DESTINO%\app" 2>nul
mkdir "%DESTINO%\app\chroma_db" 2>nul
mkdir "%DESTINO%\app\reportes" 2>nul
mkdir "%DESTINO%\app\manuales" 2>nul

echo [2/5] Copiando archivos de la app...
copy "%PROYECTO%\app_publica.py"   "%DESTINO%\app\" /Y
copy "%PROYECTO%\app.py"           "%DESTINO%\app\" /Y
copy "%PROYECTO%\agent.py"         "%DESTINO%\app\" /Y
copy "%PROYECTO%\local_agent.py"   "%DESTINO%\app\" /Y
copy "%PROYECTO%\cloud_agent.py"   "%DESTINO%\app\" /Y
copy "%PROYECTO%\config.py"        "%DESTINO%\app\" /Y
copy "%PROYECTO%\status.py"        "%DESTINO%\app\" /Y
copy "%PROYECTO%\requirements.txt" "%DESTINO%\app\" /Y
if exist "%PROYECTO%\.streamlit" xcopy "%PROYECTO%\.streamlit" "%DESTINO%\app\.streamlit\" /E /I /Y

echo [3/5] Copiando base de datos ChromaDB (puede tardar)...
xcopy "%PROYECTO%\chroma_db" "%DESTINO%\app\chroma_db\" /E /I /Y /Q

echo [4/5] Creando scripts de instalacion...

rem --- SETUP.bat ---
(
echo @echo off
echo title Configuracion Agente MOP
echo color 1F
echo echo.
echo echo  ================================================
echo echo   CONFIGURACION INICIAL - AGENTE MOP
echo echo  ================================================
echo echo.
echo echo  Este proceso instala todas las dependencias.
echo echo  Solo se ejecuta UNA VEZ. Puede tardar 5-10 min.
echo echo.
echo set "DIR=%%~dp0app"
echo cd /d "%%DIR%%"
echo echo [1/3] Creando entorno virtual...
echo python -m venv venv
echo echo [2/3] Instalando dependencias...
echo call venv\Scripts\activate
echo pip install -r requirements.txt --quiet
echo echo [3/3] Configuracion completada.
echo echo.
echo echo  Ahora puedes usar INICIAR_AGENTE.bat para abrir el agente.
echo echo.
echo pause
) > "%DESTINO%\SETUP.bat"

rem --- INICIAR_AGENTE.bat ---
(
echo @echo off
echo title Agente MOP - Manual de Carreteras
echo set "DIR=%%~dp0app"
echo cd /d "%%DIR%%"
echo if not exist "venv\Scripts\python.exe" ^(
echo     echo ERROR: Ejecuta primero SETUP.bat
echo     pause
echo     exit /b 1
echo ^)
echo set PYTHONIOENCODING=utf-8
echo call venv\Scripts\activate
echo python -m streamlit run app_publica.py --server.port 8501 --server.headless false --browser.gatherUsageStats false
echo pause
) > "%DESTINO%\INICIAR_AGENTE.bat"

rem --- CONFIGURAR_CLAVE.bat ---
(
echo @echo off
echo title Configurar Clave API - Agente MOP
echo echo.
echo echo  Para usar el Agente MOP necesitas una clave GRATUITA de Groq.
echo echo.
echo echo  1. Ve a: https://console.groq.com/keys
echo echo  2. Crea una cuenta gratuita ^(puedes usar Gmail^)
echo echo  3. Crea una nueva API Key
echo echo  4. Pegala a continuacion:
echo echo.
echo set /p GROQ_KEY="Pega tu clave Groq aqui: "
echo echo GROQ_API_KEY=%%GROQ_KEY%% > "%%~dp0app\.env"
echo echo.
echo echo  Clave guardada correctamente.
echo echo  Ya puedes usar INICIAR_AGENTE.bat
echo echo.
echo pause
) > "%DESTINO%\CONFIGURAR_CLAVE_GROQ.bat"

rem --- README.txt ---
(
echo AGENTE MOP - Manual de Carreteras de Chile
echo ==========================================
echo.
echo PRIMERA VEZ:
echo 1. Ejecuta SETUP.bat ^(instala dependencias, solo una vez^)
echo 2. Ejecuta CONFIGURAR_CLAVE_GROQ.bat ^(obtener clave gratis en groq.com^)
echo 3. Ejecuta INICIAR_AGENTE.bat
echo.
echo USO NORMAL:
echo - Solo ejecuta INICIAR_AGENTE.bat
echo - Se abre el navegador automaticamente
echo - Escribe tus consultas sobre el Manual MOP
echo.
echo REQUISITOS:
echo - Windows 10/11
echo - Python 3.10 o superior ^(python.org^)
echo - Conexion a internet ^(solo para las respuestas de IA^)
echo.
echo SOPORTE: El agente tiene acceso a los 9 volumenes del Manual MOP
echo indexados en la base de datos local incluida en este paquete.
) > "%DESTINO%\LEEME.txt"

echo [5/5] Paquete creado en:
echo     %DESTINO%
echo.
echo Archivos del instalador:
echo   - SETUP.bat               ^(ejecutar primera vez^)
echo   - INICIAR_AGENTE.bat      ^(ejecutar cada vez^)
echo   - CONFIGURAR_CLAVE_GROQ.bat ^(configurar API key gratis^)
echo   - LEEME.txt               ^(instrucciones^)
echo   - app\                    ^(archivos de la aplicacion + ChromaDB^)
echo.
echo Para distribuir: comprime la carpeta AgenteMOP_Instalador en un ZIP.
echo.
pause
