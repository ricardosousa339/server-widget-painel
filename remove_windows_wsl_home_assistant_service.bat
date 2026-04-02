@echo off
setlocal

set "TASK_ONLOGON=ServerWidgetHA-OnLogon"
set "TASK_WATCHDOG=ServerWidgetHA-Watchdog"
set "FIREWALL_RULE=Home Assistant 8123"
set "RUNNER_DIR=%ProgramData%\ServerWidgetHA"
set "RUNNER_VBS=%RUNNER_DIR%\run_ensure_home_assistant_hidden.vbs"

net session >nul 2>&1
if not "%errorlevel%"=="0" (
    echo [ERRO] Execute este script como Administrador.
    exit /b 1
)

echo [INFO] Removendo tarefas do Agendador...
schtasks /Delete /TN "%TASK_ONLOGON%" /F >nul 2>&1
schtasks /Delete /TN "%TASK_WATCHDOG%" /F >nul 2>&1

echo [INFO] Removendo regra de firewall...
netsh advfirewall firewall delete rule name="%FIREWALL_RULE%" >nul

echo [INFO] Removendo portproxy da porta 8123...
netsh interface portproxy delete v4tov4 listenaddress=0.0.0.0 listenport=8123 >nul 2>&1

echo [INFO] Removendo runner oculto...
if exist "%RUNNER_VBS%" del /f /q "%RUNNER_VBS%" >nul 2>&1
rmdir "%RUNNER_DIR%" >nul 2>&1

echo [OK] Remocao concluida.

endlocal
