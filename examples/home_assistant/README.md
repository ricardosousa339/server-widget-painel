# Home Assistant + Smart Life (Tuya) + Server Widget Painel

Este guia mostra como instalar Home Assistant no Windows (via WSL + Docker),
manter rodando continuamente e reiniciar no login, no mesmo estilo da API local.

## 1) Pre-requisitos no Windows

1. Windows 10/11 com WSL2 ativo.
2. Docker Desktop instalado e iniciado.
3. Integracao WSL habilitada no Docker Desktop para sua distro (ex.: Ubuntu).
4. Projeto clonado no WSL em um caminho como:
   - `/home/ricardohsm/projetos/server-widget-painel`

## 2) Testar Docker no WSL

No WSL:

```bash
docker info
```

Se falhar, abra o Docker Desktop e aguarde ficar "Running".

## 3) Primeira subida do Home Assistant

No Windows (CMD/Powershell), na raiz do projeto:

```bat
run_home_assistant_wsl_windows.bat
```

Isso chama `scripts/ensure_home_assistant.sh`, que:

1. Cria (ou inicia) o container `server-widget-homeassistant`.
2. Publica a porta `8123`.
3. Usa `data/homeassistant` como persistencia (`/config`).

Acesse:

- `http://127.0.0.1:8123`

Na primeira inicializacao pode demorar alguns minutos.

## 4) Configurar servico continuo no login (Windows)

Execute como Administrador:

```bat
setup_windows_wsl_home_assistant_service.bat
```

O script cria:

1. Tarefa no logon: `ServerWidgetHA-OnLogon`
2. Watchdog por minuto: `ServerWidgetHA-Watchdog`
3. Portproxy `8123` e regra de firewall

Remocao completa:

```bat
remove_windows_wsl_home_assistant_service.bat
```

## 5) Integrar Smart Life / Tuya no Home Assistant

1. Home Assistant -> Settings -> Devices & Services
2. Add Integration -> Tuya
3. Faça login com suas credenciais/projeto Tuya Cloud
4. Confirme qual entidade representa o toque da campainha
   - Nesta instalacao, o trigger usado pelo pacote eh `event.campainha_inteligente_doorbell_picture`.
   - `camera.campainha_inteligente` eh apenas a camera de preview, nao o gatilho.

## 6) Criar automacao da campainha para o painel

Arquivo de exemplo:

- `examples/home_assistant/doorbell_bridge_package.yaml`

Passos sugeridos:

1. No Home Assistant, habilite pacotes em `configuration.yaml`:
   - `homeassistant:`
   - `  packages: !include_dir_named packages`
2. Crie a pasta `/config/packages` se nao existir.
3. Copie o arquivo de exemplo para:
   - `/config/packages/server_widget_doorbell.yaml`
4. Ajuste `entity_id` da campainha no trigger, se sua instalacao usar outro identificador.
5. Reinicie o Home Assistant.

## 7) Verificacao ponta a ponta

1. Toque a campainha.
2. Verifique no backend do painel:

```bash
curl "http://127.0.0.1:8000/integrations/doorbell/state"
```

3. Verifique o frame ativo:

```bash
curl "http://127.0.0.1:8000/screen?img_mode=rgb565_base64"
```

## 8) Observacoes importantes

1. O alerta de campainha usa o GIF separado da campainha (`kind=doorbell`).
   - Se esse asset nao existir, o backend ainda pode cair para um GIF custom ativo como fallback.
2. O trigger de campainha nao altera `widget_config.json`; ele aplica prioridade temporaria em memoria.
3. O endpoint usado pelo Home Assistant no container e `host.docker.internal:8000`.
