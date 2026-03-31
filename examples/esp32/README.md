# ESP32 Client Example

Exemplo de cliente Arduino para consumir `GET /screen` e desenhar em um painel HUB75 64x32.

## Hardware esperado

- ESP32
- Painel HUB75 64x32 (chain = 1)
- Fonte adequada para o painel

## Bibliotecas Arduino

Instale no Arduino IDE (Library Manager):

- ArduinoJson (>= 6)
- ESP32 HUB75 MatrixPanel I2S DMA (`ESP32-HUB75-MatrixPanel-I2S-DMA`)

As bibliotecas abaixo ja fazem parte do core do ESP32:

- WiFi
- HTTPClient
- mbedtls/base64

## Como usar

1. Abra o sketch em `examples/esp32/esp32_led_panel_client/esp32_led_panel_client.ino`.
2. Ajuste:
   - `WIFI_SSID`
   - `WIFI_PASSWORD`
   - `API_HOST` (IP da maquina que roda o FastAPI)
   - `API_PORT` (padrao 8000)
3. Se necessario, ajuste os pinos HUB75 conforme sua placa no bloco `HUB75_I2S_CFG`.
4. Compile e grave no ESP32.

## Contrato esperado do backend

O sketch usa:

- `GET /screen?img_mode=rgb565_base64`
- `cover.enc = rgb565_base64`
- imagem 32x32 com 2 bytes por pixel (RGB565, big-endian)

Quando o widget recebido for:

- `spotify` ou `book`: renderiza a capa 32x32 e um label lateral.
- `clock`: renderiza hora/data como fallback.

## Dica de rede

Se o backend estiver no Windows, libere a porta 8000 no firewall (como descrito no README raiz) e use o IP local da maquina no `API_HOST`.
