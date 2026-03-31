# server-widget-painel

Backend em Python (FastAPI) para um painel de LED 64x32 controlado por ESP32.

## Arquitetura

A aplicacao usa widgets orientados a objetos:

- `BaseWidget`: classe abstrata com metodo `get_data()`.
- `SpotifyWidget`: prioridade maxima (100) quando `currently_playing == true`.
- `BookWidget`: prioridade intermediaria (50) para capa de livro, com sync manual/automatico via Skoob.
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
- `SKOOB_SYNC_ENABLED=false`
- `SKOOB_SYNC_INTERVAL_SECONDS=300`
- `SKOOB_PROFILE_URL=`
- `SKOOB_USER_ID=`
- `SKOOB_AUTH_COOKIE=`
- `SKOOB_READING_TYPES=2`

## Sync do Skoob (scraping)

O backend suporta dois modos inspirados no fluxo do projeto `skoob-api`:

1. **Scraping publico do perfil**: usa `SKOOB_PROFILE_URL` para buscar o livro em leitura no HTML do seu perfil.
2. **API interna com cookie**: usa `SKOOB_USER_ID` + `SKOOB_AUTH_COOKIE` para consultar `/v1/bookcase/books/...` e identificar o item da estante marcado como leitura.

Prioridade da sincronizacao:

1. Tenta scraping de perfil (se `SKOOB_PROFILE_URL` estiver preenchido).
2. Se nao encontrar leitura ativa e houver `SKOOB_USER_ID` + `SKOOB_AUTH_COOKIE`, usa a API interna.

Sincronizacao automatica:

- Se `SKOOB_SYNC_ENABLED=true`, o `BookWidget` tenta sincronizar em background durante chamadas de `/screen` respeitando `SKOOB_SYNC_INTERVAL_SECONDS`.
- Mesmo com sync automatico desligado, voce pode sincronizar sob demanda via endpoint.

## Como obter SKOOB_USER_ID e SKOOB_AUTH_COOKIE

Se o modo publico (`SKOOB_PROFILE_URL`) funcionar para voce, nao precisa de `SKOOB_USER_ID` nem `SKOOB_AUTH_COOKIE`.
Use os dois apenas para o fallback da API interna.

Observacao:

- Alguns perfis (incluindo rotas em `/pt/profile/...`) podem retornar HTTP 403 sem sessao ativa.
- Nesses casos, configure ao menos `SKOOB_AUTH_COOKIE` e, idealmente, `SKOOB_USER_ID` para habilitar o fallback pela API interna.

### Descobrir SKOOB_USER_ID

Opcao A (quando a chamada aparece no Network):

1. Entre no Skoob no navegador (logado).
2. Abra DevTools (F12) e va em **Network**.
3. Recarregue a pagina e filtre por `bookcase/books`.
4. Abra a request parecida com:
  `https://www.skoob.com.br/v1/bookcase/books/123456/shelf_id:0/limit:1000000`
5. O numero apos `books/` e seu `SKOOB_USER_ID`.

Opcao B (quando nao aparece no Network):

1. Com o perfil aberto e logado, abra DevTools -> **Console**.
2. Execute:

```js
const m = document.documentElement.outerHTML.match(/\/v1\/bookcase\/books\/(\d+)\//);
m ? m[1] : "nao encontrado";
```

3. Se retornar um numero, ele e o `SKOOB_USER_ID`.

Opcao C (sem descobrir manualmente):

1. Configure `SKOOB_PROFILE_URL` + `SKOOB_AUTH_COOKIE`.
2. Deixe `SKOOB_USER_ID` vazio.
3. O backend tentara inferir o `user_id` automaticamente antes de chamar a API interna.

### Descobrir SKOOB_AUTH_COOKIE

Opcao recomendada (mais confiavel):

1. No **Network**, abra qualquer request para `www.skoob.com.br` (nao precisa ser `bookcase/books`).
2. Copie o header `Cookie` completo em **Request Headers**.
3. Cole o valor inteiro em `SKOOB_AUTH_COOKIE`.

Alternativa:

1. DevTools -> **Application/Storage** -> **Cookies** -> `https://www.skoob.com.br`.
2. Copie os cookies de sessao e monte uma string no formato `chave1=valor1; chave2=valor2`.

Importante:

- Nao versionar `.env` com cookie real.
- Cookie de sessao expira; quando vencer, atualize `SKOOB_AUTH_COOKIE`.

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

### `POST /book/sync/skoob`
Sincroniza o estado do livro com seu perfil Skoob.

Corpo opcional (sobrescreve variaveis de ambiente apenas nesta chamada):

```json
{
  "profile_url": "https://www.skoob.com.br/pt/profile/SEU_USUARIO",
  "user_id": "12345",
  "auth_cookie": "SEU_COOKIE_COMPLETO"
}
```

Exemplo de resposta do `POST /book/sync/skoob`:

```json
{
  "is_reading": true,
  "title": "Nome do Livro",
  "author": "Nome do Autor",
  "cover_url": "https://...",
  "sync_source": "skoob_profile",
  "profile_url": "https://www.skoob.com.br/pt/profile/SEU_USUARIO",
  "last_sync_ts": 1711886400
}
```

### `GET /book/sync/skoob/status`
Retorna status da sincronizacao e configuracao atual (sem expor valor do cookie).

Exemplo de resposta:

```json
{
  "sync": {
    "configured": true,
    "auto_sync_enabled": true,
    "sync_interval_seconds": 300,
    "last_attempt_ts": 1711886400,
    "last_success_ts": 1711886400,
    "last_error": "",
    "last_source": "skoob_profile",
    "last_is_reading": true,
    "next_sync_ts": 1711886700,
    "seconds_until_next_sync": 120,
    "current_state": {
      "is_reading": true,
      "title": "Nome do Livro",
      "author": "Nome do Autor",
      "cover_url": "https://...",
      "sync_source": "skoob_profile",
      "profile_url": "https://www.skoob.com.br/pt/profile/usuario",
      "last_sync_ts": 1711886400
    }
  },
  "config": {
    "profile_url": "https://www.skoob.com.br/pt/profile/usuario",
    "user_id": "123456",
    "auth_cookie_configured": true,
    "reading_types": ["2"],
    "sync_enabled": true,
    "sync_interval_seconds": 300
  }
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
