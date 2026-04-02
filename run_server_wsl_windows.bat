@echo off
setlocal

set "DISTRO=%~1"
if "%DISTRO%"=="" set "DISTRO=Ubuntu"

set "WSL_PROJECT_DIR=%~2"
if "%WSL_PROJECT_DIR%"=="" set "WSL_PROJECT_DIR=/home/ricardohsm/projetos/server-widget-painel"

set "WSL_IP="
set "IS_ADMIN=0"
net session >nul 2>&1
if "%errorlevel%"=="0" set "IS_ADMIN=1"

echo [INFO] Distro WSL: %DISTRO%
echo [INFO] Projeto WSL: %WSL_PROJECT_DIR%

if "%IS_ADMIN%"=="1" (
    echo [INFO] Atualizando portproxy para IP atual do WSL...
    for /f "tokens=1" %%i in ('wsl.exe -d %DISTRO% -- hostname -I 2^>nul') do (
        if not defined WSL_IP set "WSL_IP=%%i"
    )

    if not "%WSL_IP%"=="" (
        netsh interface portproxy delete v4tov4 listenaddress=0.0.0.0 listenport=8000 >nul 2>&1
        netsh interface portproxy add v4tov4 listenaddress=0.0.0.0 listenport=8000 connectaddress=%WSL_IP% connectport=8000 >nul
        if errorlevel 1 (
            echo [WARN] Nao foi possivel atualizar portproxy automaticamente.
        ) else (
            echo [INFO] Portproxy atualizado para %WSL_IP%.
        )
    ) else (
        echo [WARN] Nao foi possivel detectar IP do WSL; mantendo portproxy atual.
    )
) else (
    echo [WARN] Execute como Administrador para atualizar portproxy automaticamente.
)

echo [INFO] Reiniciando servidor no WSL...

wsl.exe -d %DISTRO% --cd %WSL_PROJECT_DIR% /bin/bash -lc "./scripts/restart_server.sh"
if errorlevel 1 (
    echo [ERRO] Falha ao reiniciar servidor no WSL.
    exit /b 1
)

echo [OK] Servidor reiniciado.
echo [OK] Preview: http://127.0.0.1:8000/preview/painel

endlocal