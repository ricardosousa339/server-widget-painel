# server-widget-painel

Backend em Python (FastAPI) para um painel de LED 64x32 controlado por ESP32.

## Arquitetura

A aplicacao usa widgets orientados a objetos:

- `BaseWidget`: classe abstrata com metodo `get_data()`.
- `SpotifyWidget`: prioridade maxima (100) quando `currently_playing == true`.
- `CustomGifWidget`: biblioteca de GIFs custom, com GIF separado para a campainha, e prioridade 80 quando existe GIF custom ativo.
- `ClockWidget`: fallback permanente (prioridade 0).

Fluxo de decisao (modo `priority`):

1. Tenta `SpotifyWidget`.
2. Se Spotify nao estiver ativo, tenta `CustomGifWidget`.
3. Se nenhum dos dois estiver ativo/disponivel, retorna `ClockWidget`.

Observacao: esse fluxo pode mudar conforme o `display_mode` salvo em `/widgets/config`.

## Requisitos

- Python 3.10+
- Dependencias em `requirements.txt`

## Instalacao (Linux/macOS/Windows PowerShell)

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows PowerShell
pip install -r requirements.txt
cp .env.example .env
```

## Variaveis de ambiente

Edite `.env`:

- `IMAGE_SIZE=32`
- `REQUEST_TIMEOUT_SECONDS=6`
- `SPOTIPY_CLIENT_ID`
- `SPOTIPY_CLIENT_SECRET`
- `SPOTIPY_REDIRECT_URI`
- `SPOTIFY_REFRESH_TOKEN`
- `SPOTIFY_ACCESS_TOKEN`
- `FRAME_SOURCE_REFRESH_MS=1500`
- `WIDGET_CONFIG_PATH=data/widget_config.json`
- `CUSTOM_GIF_STATE_PATH=data/custom_gifs_state.json`
- `CUSTOM_GIF_UPLOAD_DIR=data/uploads`
- `CUSTOM_GIF_MAX_UPLOAD_BYTES=8388608`
- `DOORBELL_ALERT_DEFAULT_SECONDS=8`
- `DOORBELL_ALERT_MAX_SECONDS=60`

## Gerar tokens do Spotify (access + refresh)

No Spotify Developer Dashboard voce encontra apenas `Client ID` e `Client Secret`.
Os tokens de usuario (`SPOTIFY_ACCESS_TOKEN` e `SPOTIFY_REFRESH_TOKEN`) precisam ser gerados via OAuth.

1. No app do Spotify, cadastre a Redirect URI usada no projeto:
  - `http://localhost:8888/callback`
2. Rode o script abaixo e siga o fluxo no navegador:

```bash
python scripts/get_spotify_tokens.py \
  --client-id "CLIENT_ID_REAL" \
  --client-secret "CLIENT_SECRET_REAL" \
  --redirect-uri "http://localhost:8888/callback" \
  --show-dialog
```

Em ambientes sem browser integrado (WSL/servidor), use:

```bash
python scripts/get_spotify_tokens.py \
  --client-id "CLIENT_ID_REAL" \
  --client-secret "CLIENT_SECRET_REAL" \
  --redirect-uri "http://localhost:8888/callback" \
  --show-dialog \
  --no-browser
```

Depois, copie a URL impressa no terminal e abra manualmente no navegador do seu sistema.

3. Ao final, cole os valores impressos no seu `.env`:
  - `SPOTIPY_CLIENT_ID`
  - `SPOTIPY_CLIENT_SECRET`
  - `SPOTIPY_REDIRECT_URI`
  - `SPOTIFY_ACCESS_TOKEN`
  - `SPOTIFY_REFRESH_TOKEN`

Se preferir fluxo manual, use `--print-auth-url` para apenas imprimir a URL de autorizacao,
e depois rode novamente com `--code "<code_da_callback>"`.

## Executar servidor

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Script `.bat` (Windows)

Arquivo: `run_server_windows.bat`

Ele:

1. Cria `.venv` se necessario.
2. Ativa o ambiente.
3. Instala dependencias.
4. Sobe o servidor em `0.0.0.0:8000`.

## Rodar como servico no Windows (24x7)

Para quem roda o projeto no WSL, o caminho mais estavel e usar o Agendador de Tarefas do Windows
com um script de vigilancia (`scripts/ensure_server.sh`) que sobe o backend apenas quando necessario.

### Modo rapido (recomendado)

No CMD do Windows como Administrador, execute na raiz do projeto:

```bat
setup_windows_wsl_service.bat
```

Esse script:

1. Ajusta energia para nao suspender em AC e nao pausar ao fechar tampa.
2. Cria tarefa no logon (`ServerWidgetPainel-OnLogon`).
3. Cria watchdog por minuto (`ServerWidgetPainel-Watchdog`).
4. Detecta o IP atual do WSL e configura `portproxy` (Windows:8000 -> WSL:8000).
5. Gera um runner oculto para evitar janela de terminal piscando.
6. Libera a porta 8000 no firewall.
7. Dispara a inicializacao imediatamente.

Importante: com backend rodando dentro do WSL, agendar em `SYSTEM` no boot pode falhar,
porque a distro WSL e por usuario. O modo `ONLOGON` do seu usuario e o mais confiavel.

Se sua distro/caminho no WSL forem diferentes:

```bat
setup_windows_wsl_service.bat "Ubuntu-22.04" "/home/usuario/projeto"
```

Para iniciar/reiniciar manualmente pelo Windows durante desenvolvimento:

```bat
run_server_wsl_windows.bat
```

Observacao: se executado como Administrador, esse script tambem atualiza o `portproxy`
para o IP atual do WSL (util quando o WSL troca de IP apos reboot).

Para remover toda configuracao criada (tarefas + firewall):

```bat
remove_windows_wsl_service.bat
```

Esse remove tambem o `portproxy` da porta 8000.

### Janela do terminal aparecendo e sumindo

Se voce viu uma janela abrindo a cada minuto, era a tarefa watchdog rodando comando direto.
Rode novamente o setup para trocar para execucao oculta:

```bat
remove_windows_wsl_service.bat
setup_windows_wsl_service.bat
```

### Se `http://IP_DO_WINDOWS:8000/health` falhar

1. Rode no CMD como Administrador:

```bat
setup_windows_wsl_service.bat
```

2. Teste local no Windows:

```bat
curl http://127.0.0.1:8000/health
curl http://SEU_IP_LAN:8000/health
```

3. Se o primeiro funcionar e o segundo nao, confira se o celular esta na mesma rede (nao Guest) e sem VPN.

### 1) Ajustar energia para nao pausar com tampa fechada

Execute no PowerShell (Administrador):

```powershell
# Nao suspender na tomada
powercfg /change standby-timeout-ac 0

# Acao da tampa na tomada: "Nao fazer nada"
powercfg /SETACVALUEINDEX SCHEME_CURRENT SUB_BUTTONS LIDACTION 0
powercfg /SETACTIVE SCHEME_CURRENT
```

### 2) Criar tarefa de inicializacao (logon)

No Prompt de Comando (Administrador), ajuste o nome da distro e caminho do projeto se necessario:

```bat
schtasks /Create /TN "ServerWidgetPainel-OnLogon" /SC ONLOGON /DELAY 0000:20 /RL HIGHEST /TR "wsl.exe -d Ubuntu --cd /home/ricardohsm/projetos/server-widget-painel /bin/bash -lc './scripts/ensure_server.sh'" /F
```

### 3) Criar tarefa de vigilancia (a cada 1 minuto)

```bat
schtasks /Create /TN "ServerWidgetPainel-Watchdog" /SC MINUTE /MO 1 /RL HIGHEST /TR "wsl.exe -d Ubuntu --cd /home/ricardohsm/projetos/server-widget-painel /bin/bash -lc './scripts/ensure_server.sh'" /F
```

### 4) Testar imediatamente

```bat
schtasks /Run /TN "ServerWidgetPainel-OnLogon"
```

### 5) Verificar status

```bat
schtasks /Query /TN "ServerWidgetPainel-OnLogon"
schtasks /Query /TN "ServerWidgetPainel-Watchdog"
```

Se quiser validar pela API:

```bash
curl http://127.0.0.1:8000/health
```

Observacoes:

- O script `scripts/ensure_server.sh` nao reinicia sem necessidade; ele apenas sobe quando o health nao responde.
- Em queda de processo, a tarefa por minuto religa automaticamente.
- Em notebooks, para manter 24x7, deixe ligado na tomada e com as configuracoes de energia acima.

## Home Assistant no Windows (WSL + Docker)

Para integrar sua campainha Smart Life com o painel, voce pode rodar o Home Assistant no mesmo host da API,
com o mesmo modelo de servico continuo no logon.

Arquivos de suporte adicionados:

- `scripts/ensure_home_assistant.sh`
- `run_home_assistant_wsl_windows.bat`
- `setup_windows_wsl_home_assistant_service.bat`
- `remove_windows_wsl_home_assistant_service.bat`
- `examples/home_assistant/README.md`
- `examples/home_assistant/doorbell_bridge_package.yaml`

Passo a passo rapido:

1. Instale e inicie o Docker Desktop no Windows (com integracao WSL habilitada).
2. No Windows, na raiz do projeto, rode:

```bat
run_home_assistant_wsl_windows.bat
```

3. Abra `http://127.0.0.1:8123` e conclua o onboarding do Home Assistant.
4. Para manter 24x7 e reiniciar no logon (igual a API), execute como Administrador:

```bat
setup_windows_wsl_home_assistant_service.bat
```

Isso cria:

1. `ServerWidgetHA-OnLogon`
2. `ServerWidgetHA-Watchdog` (a cada minuto)
3. `portproxy` da porta 8123 e regra de firewall

Remocao completa:

```bat
remove_windows_wsl_home_assistant_service.bat
```

Depois, siga o guia de automacao em `examples/home_assistant/README.md`.

## Abrir firewall no Windows

### CMD (Administrador)

```bat
netsh advfirewall firewall add rule name="LED Panel API 8000" dir=in action=allow protocol=TCP localport=8000
```

### PowerShell (Administrador)

```powershell
New-NetFirewallRule -DisplayName "LED Panel API 8000" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow
```

## Endpoint principal

### `GET /screen`

Query param opcional:

- `img_mode=rgb565_base64` (padrao, menor payload)
- `img_mode=rgb_base64`
- `img_mode=rgb_array`

Exemplo de resposta com Spotify ativo:

```json
{
  "widget": "spotify",
  "priority": 100,
  "ts": 1711886400,
  "data": {
    "currently_playing": true,
    "track": "Song Name",
    "artist": "Artist",
    "album": "Album",
    "progress_ms": 12345,
    "duration_ms": 210000,
    "cover": {
      "w": 32,
      "h": 32,
      "enc": "rgb565_base64",
      "data": "..."
    }
  }
}
```

## Configurar widgets ativos

Agora existe uma pagina amigavel para habilitar/desabilitar widgets:

- UI: `/config/widgets`
- API (ler): `GET /widgets/config`
- API (salvar): `POST /widgets/config`

### Modos de exibicao

Campos aceitos no `POST /widgets/config`:

- `display_mode`: `priority`, `custom_only` ou `hybrid`
- `hybrid_period_seconds`: periodo da janela hibrida (10 a 86400)
- `hybrid_show_seconds`: tempo do GIF dentro do periodo (1 a 3600, sempre menor que o periodo)

Comportamento de cada modo:

- `priority` (padrao): usa prioridade normal (`spotify` -> `custom_gif` -> `clock`).
- `custom_only`: tenta mostrar `custom_gif`; se indisponivel, cai para `spotify/clock` para nao deixar a tela vazia.
- `hybrid`: a cada `hybrid_period_seconds`, tenta mostrar `custom_gif` por `hybrid_show_seconds`; fora dessa janela, usa `spotify/clock`.

Valores padrao:

- `display_mode`: `priority`
- `hybrid_period_seconds`: `300`
- `hybrid_show_seconds`: `30`

Exemplo de update via API:

```bash
curl -X POST "http://127.0.0.1:8000/widgets/config" \
  -H "Content-Type: application/json" \
  -d '{"enabled_widgets": ["spotify", "custom_gif", "clock"]}'
```

Exemplo de update no modo hibrido:

```bash
curl -X POST "http://127.0.0.1:8000/widgets/config" \
  -H "Content-Type: application/json" \
  -d '{
    "enabled_widgets": ["spotify", "custom_gif", "clock"],
    "display_mode": "hybrid",
    "hybrid_period_seconds": 300,
    "hybrid_show_seconds": 30
  }'
```

Exemplo de leitura de configuracao:

```json
{
  "widgets": [
    {"name": "spotify", "priority": 100, "role": "primary", "enabled": true},
    {"name": "custom_gif", "priority": 80, "role": "primary", "enabled": true},
    {"name": "clock", "priority": 0, "role": "fallback", "enabled": true}
  ],
  "enabled_widgets": ["clock", "custom_gif", "spotify"],
  "display_mode": "hybrid",
  "hybrid_period_seconds": 300,
  "hybrid_show_seconds": 30,
  "updated_at": 1711886400
}
```

Persistencia:

- O estado e salvo em `data/widget_config.json`.
- Caminho configuravel pela variavel `WIDGET_CONFIG_PATH`.

## Widget custom_gif (biblioteca de GIFs)

Endpoints principais:

- Estado atual da biblioteca: `GET /widgets/custom-gif`
- Download do asset selecionado: `GET /widgets/custom-gif/raw?kind=custom&asset_id=...`
- Pacote de playback para o ESP32: `GET /widgets/custom-gif/playback?kind=custom&asset_id=...`
- Upload de GIF: `POST /widgets/custom-gif/upload` (multipart form com `file`, `kind` e `active`)
- Ativar ou desativar um asset: `PATCH /widgets/custom-gif/{asset_id}`
- Remocao de um asset: `DELETE /widgets/custom-gif/{asset_id}`
- Limpar a biblioteca de um kind: `DELETE /widgets/custom-gif?kind=custom` ou `kind=doorbell`

Exemplo de upload:

```bash
curl -X POST "http://127.0.0.1:8000/widgets/custom-gif/upload" \
  -F "file=@/caminho/animacao.gif" \
  -F "kind=custom" \
  -F "active=true"
```

Exemplo de playback:

```bash
curl "http://127.0.0.1:8000/widgets/custom-gif/playback?kind=custom"
```

Exemplo de limpeza:

```bash
curl -X DELETE "http://127.0.0.1:8000/widgets/custom-gif?kind=custom"
```

Persistencia do custom_gif:

- Metadados da biblioteca: `CUSTOM_GIF_STATE_PATH`.
- GIFs custom salvos em: `CUSTOM_GIF_UPLOAD_DIR/custom_gifs/`.
- GIF da campainha salvo em: `CUSTOM_GIF_UPLOAD_DIR/doorbell_gif/`.
- Limite de upload em bytes: `CUSTOM_GIF_MAX_UPLOAD_BYTES`.

## Integracao Home Assistant (campainha Smart Life)

Foi adicionada uma ponte REST para automacao de campainha via Home Assistant:

- Estado: `GET /integrations/doorbell/state`
- Acionar alerta: `POST /integrations/doorbell/trigger`
- Limpar alerta: `DELETE /integrations/doorbell/state`

Comportamento do trigger:

- Ativa uma janela temporaria de alerta (`TTL`) em memoria.
- Durante essa janela, o backend tenta priorizar o GIF da campainha (`kind=doorbell`) no `/screen`.
- Nao altera `display_mode` nem sobrescreve `enabled_widgets` em `widget_config.json`.

Observacao importante:

- O ideal e configurar um GIF separado para a campainha, mas o backend ainda pode usar um GIF custom ativo como fallback se o asset `doorbell` nao existir.

Exemplo de trigger (8 segundos por padrao):

```bash
curl -X POST "http://127.0.0.1:8000/integrations/doorbell/trigger" \
  -H "Content-Type: application/json" \
  -d '{"source":"home_assistant"}'
```

Exemplo de trigger customizado:

```bash
curl -X POST "http://127.0.0.1:8000/integrations/doorbell/trigger" \
  -H "Content-Type: application/json" \
  -d '{"duration_seconds":12,"source":"smart_life"}'
```

Exemplo de leitura de estado:

```bash
curl "http://127.0.0.1:8000/integrations/doorbell/state"
```

## Observacoes para ESP32

- Recomenda-se usar `img_mode=rgb565_base64` para reduzir bytes na rede.
- `rgb_array` existe para debug, mas gera payload bem maior.
- O ESP32 pode decodificar base64 e escrever direto no buffer RGB565.

## Exemplo de cliente ESP32 (Arduino)

Foi adicionado um exemplo pronto para consumir o endpoint `/screen` e renderizar no painel HUB75 64x32:

- Sketch: `examples/esp32/esp32_led_panel_client/esp32_led_panel_client.ino`
- Guia rapido: `examples/esp32/README.md`

Resumo de uso:

1. Instale bibliotecas `ArduinoJson` e `ESP32-HUB75-MatrixPanel-I2S-DMA` no Arduino IDE.
2. No sketch, configure `WIFI_SSID`, `WIFI_PASSWORD`, `API_HOST` e `API_PORT`.
3. Garanta que o FastAPI esteja acessivel na rede local (porta 8000 liberada no firewall).
4. Grave no ESP32 e verifique logs seriais a 115200 baud.
