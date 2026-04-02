@echo off
setlocal

set "TASK_ONLOGON=ServerWidgetPainel-OnLogon"
set "TASK_WATCHDOG=ServerWidgetPainel-Watchdog"
set "TASK_LEGACY_ONSTART=ServerWidgetPainel-OnStart"
set "FIREWALL_RULE=LED Panel API 8000"
set "RUNNER_DIR=%ProgramData%\ServerWidgetPainel"
set "RUNNER_VBS=%RUNNER_DIR%\run_ensure_hidden.vbs"

net session >nul 2>&1
if not "%errorlevel%"=="0" (
    echo [ERRO] Execute este script como Administrador.
    exit /b 1
)

echo [INFO] Removendo tarefas do Agendador...
schtasks /Delete /TN "%TASK_ONLOGON%" /F >nul 2>&1
schtasks /Delete /TN "%TASK_WATCHDOG%" /F >nul 2>&1
schtasks /Delete /TN "%TASK_LEGACY_ONSTART%" /F >nul 2>&1

echo [INFO] Removendo regra de firewall...
netsh advfirewall firewall delete rule name="%FIREWALL_RULE%" >nul

echo [INFO] Removendo portproxy da porta 8000...
netsh interface portproxy delete v4tov4 listenaddress=0.0.0.0 listenport=8000 >nul 2>&1

echo [INFO] Removendo runner oculto...
if exist "%RUNNER_VBS%" del /f /q "%RUNNER_VBS%" >nul 2>&1
rmdir "%RUNNER_DIR%" >nul 2>&1

echo [OK] Remocao concluida.
echo [DICA] Se quiser reverter energia manualmente, rode no PowerShell Admin:
echo        powercfg /SETACVALUEINDEX SCHEME_CURRENT SUB_BUTTONS LIDACTION 1
echo        powercfg /change standby-timeout-ac 30
echo        powercfg /SETACTIVE SCHEME_CURRENT

endlocal