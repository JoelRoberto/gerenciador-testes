@echo off
title Gerenciador de Casos de Teste - Iniciando...
echo ============================================
echo  Gerenciador de Casos de Teste - Stone/Ton
echo ============================================
echo.

set REPO_ZIP=https://github.com/JoelRoberto/gerenciador-testes/archive/refs/heads/main.zip
set DEST=%USERPROFILE%\gerenciador-testes
set TEMP_ZIP=%TEMP%\gerenciador-testes_update.zip
set TEMP_EXTRACT=%TEMP%\gerenciador-testes_extract

:: Baixa sempre a versao mais recente do GitHub (sem precisar de Git instalado)
echo Verificando atualizacoes...
if exist "%TEMP_EXTRACT%" rmdir /s /q "%TEMP_EXTRACT%"
powershell -NoProfile -Command "try { Invoke-WebRequest -Uri '%REPO_ZIP%' -OutFile '%TEMP_ZIP%' -UseBasicParsing; exit 0 } catch { exit 1 }"
if errorlevel 1 (
    echo [AVISO] Nao foi possivel baixar a atualizacao. Verifique sua internet.
    if not exist "%DEST%\app.py" (
        echo [ERRO] Nenhuma copia local encontrada. Nao e possivel continuar sem internet na primeira instalacao.
        pause
        exit /b 1
    )
    echo Continuando com a versao local ja instalada em "%DEST%"...
    goto RUN
)

powershell -NoProfile -Command "Expand-Archive -Path '%TEMP_ZIP%' -DestinationPath '%TEMP_EXTRACT%' -Force"
if not exist "%DEST%" mkdir "%DEST%"

:: Copia por cima da instalacao existente, preservando saves\ e logs\ (nao apaga nada, so atualiza)
robocopy "%TEMP_EXTRACT%\gerenciador-testes-main" "%DEST%" /E /XD .git .devcontainer __pycache__ saves logs >nul

del /q "%TEMP_ZIP%" >nul 2>&1
rmdir /s /q "%TEMP_EXTRACT%" >nul 2>&1
echo Atualizado!

:RUN
cd /d "%DEST%"
if not exist "saves" mkdir "saves"
if not exist "logs" mkdir "logs"

:: Verifica Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python nao encontrado. Baixando instalador...
    curl -L -o python_installer.exe https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe
    echo Instalando Python, aguarde...
    python_installer.exe /quiet InstallAllUsers=0 PrependPath=1 Include_pip=1
    del python_installer.exe
    echo Python instalado!
)

:: Instala dependencias
echo Verificando dependencias...
pip install streamlit fpdf2 pandas --quiet

:: Inicia o app
echo.
echo Iniciando o Gerenciador de Testes...
echo Acesse: http://localhost:8501
echo Para fechar, pressione Ctrl+C nesta janela
echo.
streamlit run app.py --server.headless true
pause
