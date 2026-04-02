@echo off
setlocal

set "DISTRO=%~1"
if "%DISTRO%"=="" set "DISTRO=Ubuntu"

set "WSL_PROJECT_DIR=%~2"
if "%WSL_PROJECT_DIR%"=="" set "WSL_PROJECT_DIR=/home/ricardohsm/projetos/server-widget-painel"

set "TASK_ONLOGON=ServerWidgetHA-OnLogon"
set "TASK_WATCHDOG=ServerWidgetHA-Watchdog"
set "FIREWALL_RULE=Home Assistant 8123"
set "RUNNER_DIR=%ProgramData%\ServerWidgetHA"
set "RUNNER_VBS=%RUNNER_DIR%\run_ensure_home_assistant_hidden.vbs"
set "SERVICE_CMD="
set "WSL_IP="

net session >nul 2>&1
if not "%errorlevel%"=="0" (
    echo [ERRO] Execute este script como Administrador.
    exit /b 1
)

echo [INFO] Distro WSL: %DISTRO%
echo [INFO] Projeto WSL: %WSL_PROJECT_DIR%

echo [INFO] Detectando IP atual do WSL...
for /f "tokens=1" %%i in ('wsl.exe -d %DISTRO% -- hostname -I 2^>nul') do (
    if not defined WSL_IP set "WSL_IP=%%i"
)

if "%WSL_IP%"=="" (
    echo [ERRO] Nao foi possivel detectar IP do WSL para a distro %DISTRO%.
    echo [ERRO] Valide a distro com: wsl -l -v
    exit /b 1
)

echo [INFO] IP WSL detectado: %WSL_IP%

echo [INFO] Gerando runner oculto para evitar janela piscando...
if not exist "%RUNNER_DIR%" mkdir "%RUNNER_DIR%"
(
    echo Option Explicit
    echo Dim shell, cmd
    echo Set shell = CreateObject("WScript.Shell")
    echo cmd = "wsl.exe -d ""%DISTRO%"" --cd ""%WSL_PROJECT_DIR%"" /bin/bash -lc ""./scripts/ensure_home_assistant.sh"""
    echo shell.Run cmd, 0, True
) > "%RUNNER_VBS%"
if errorlevel 1 (
    echo [ERRO] Falha ao gerar runner oculto em %RUNNER_VBS%.
    exit /b 1
)

set "SERVICE_CMD=wscript.exe //B //Nologo %RUNNER_VBS%"

echo [INFO] Configurando portproxy (Windows:8123 -> WSL:8123)...
netsh interface portproxy delete v4tov4 listenaddress=0.0.0.0 listenport=8123 >nul 2>&1
netsh interface portproxy add v4tov4 listenaddress=0.0.0.0 listenport=8123 connectaddress=%WSL_IP% connectport=8123 >nul
if errorlevel 1 (
    echo [ERRO] Falha ao configurar portproxy na porta 8123.
    echo [ERRO] Verifique se o servico "IP Helper" esta ativo no Windows.
    exit /b 1
)

echo [INFO] Removendo tarefas antigas (se existirem)...
schtasks /Delete /TN "%TASK_ONLOGON%" /F >nul 2>&1
schtasks /Delete /TN "%TASK_WATCHDOG%" /F >nul 2>&1

echo [INFO] Criando tarefa para iniciar no logon do usuario atual...
schtasks /Create /TN "%TASK_ONLOGON%" /SC ONLOGON /DELAY 0000:30 /RL HIGHEST /TR "%SERVICE_CMD%" /F >nul
if errorlevel 1 (
    echo [ERRO] Falha ao criar tarefa %TASK_ONLOGON%.
    exit /b 1
)

echo [INFO] Criando tarefa de vigilancia (1 minuto)...
schtasks /Create /TN "%TASK_WATCHDOG%" /SC MINUTE /MO 1 /RL HIGHEST /TR "%SERVICE_CMD%" /F >nul
if errorlevel 1 (
    echo [ERRO] Falha ao criar tarefa %TASK_WATCHDOG%.
    exit /b 1
)

echo [INFO] Liberando porta 8123 no firewall do Windows...
netsh advfirewall firewall add rule name="%FIREWALL_RULE%" dir=in action=allow protocol=TCP localport=8123 >nul

echo [INFO] Disparando a tarefa de logon agora...
schtasks /Run /TN "%TASK_ONLOGON%" >nul

echo [OK] Home Assistant configurado como servico no logon.
echo [OK] URL local: http://127.0.0.1:8123
echo [OK] Tarefas criadas:
echo      - %TASK_ONLOGON%
echo      - %TASK_WATCHDOG%
echo.
echo [DICA] Se sua distro/caminho forem diferentes:
echo        setup_windows_wsl_home_assistant_service.bat "Ubuntu-22.04" "/home/usuario/projeto"

endlocal
