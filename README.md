# server-widget-painel

Backend em Python (FastAPI) para um painel de LED 64x32 controlado por ESP32.

## Arquitetura

A aplicacao usa widgets orientados a objetos:

- `BaseWidget`: classe abstrata com metodo `get_data()`.
- `SpotifyWidget`: prioridade maxima (100) quando `currently_playing == true`.
- `BookWidget`: prioridade intermediaria (50) para capa de livro, com estado manual via API.
- `ClockWidget`: fallback permanente (prioridade 0).

Fluxo de decisao:

1. Tenta `SpotifyWidget`.
2. Se nao estiver ativo, tenta `BookWidget`.
3. Se nenhum ativo, retorna `ClockWidget`.

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
- `BOOK_STATE_PATH=data/current_book.json`

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

## Endpoints auxiliares do livro

### `GET /book/current`
Retorna o estado atual do widget de livro.

### `POST /book/current`
Atualiza estado atual do widget de livro.

Exemplo:

```json
{
  "is_reading": true,
  "title": "Clean Code",
  "author": "Robert C. Martin",
  "cover_url": "https://..."
}
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
