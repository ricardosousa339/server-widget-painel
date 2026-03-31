from __future__ import annotations

import argparse
import base64
import secrets
import sys
import time
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import requests
from dotenv import load_dotenv

DEFAULT_SCOPE = "user-read-currently-playing user-read-playback-state"


def _looks_like_placeholder(value: str) -> bool:
    normalized = value.strip().lower()
    placeholder_tokens = {
        "seu_client_id",
        "seu_client_secret",
        "your_client_id",
        "your_client_secret",
        "client_id",
        "client_secret",
    }
    return normalized in placeholder_tokens


@dataclass
class CallbackResult:
    code: str | None = None
    error: str | None = None


def build_authorize_url(
    *,
    client_id: str,
    redirect_uri: str,
    scope: str,
    state: str,
    show_dialog: bool,
) -> str:
    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": scope,
        "state": state,
        "show_dialog": "true" if show_dialog else "false",
    }
    return f"https://accounts.spotify.com/authorize?{urlencode(params)}"


def exchange_code_for_tokens(
    *,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    code: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    raw_credentials = f"{client_id}:{client_secret}".encode("utf-8")
    basic_auth = base64.b64encode(raw_credentials).decode("utf-8")

    response = requests.post(
        "https://accounts.spotify.com/api/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
        },
        headers={
            "Authorization": f"Basic {basic_auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        timeout=timeout_seconds,
    )

    if response.status_code >= 400:
        raise RuntimeError(
            "Falha ao trocar code por token "
            f"(HTTP {response.status_code}): {response.text}"
        )

    return response.json()


def wait_for_callback_code(
    *,
    redirect_uri: str,
    expected_state: str,
    timeout_seconds: int,
) -> str:
    parsed_redirect = urlparse(redirect_uri)
    host = parsed_redirect.hostname or "localhost"
    port = parsed_redirect.port
    callback_path = parsed_redirect.path or "/"

    if not port:
        raise ValueError("A SPOTIPY_REDIRECT_URI precisa incluir porta (ex.: 8888).")

    if host not in {"localhost", "127.0.0.1"}:
        raise ValueError(
            "Para captura automática, use redirect local: http://localhost:<porta>/callback"
        )

    callback_result = CallbackResult()

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed_request = urlparse(self.path)
            if parsed_request.path != callback_path:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"Not Found")
                return

            query = parse_qs(parsed_request.query)
            callback_result.error = query.get("error", [None])[0]
            callback_result.code = query.get("code", [None])[0]
            state = query.get("state", [None])[0]

            if callback_result.error:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(
                    f"Erro no Spotify OAuth: {callback_result.error}".encode("utf-8")
                )
                return

            if not callback_result.code:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Code OAuth nao encontrado na callback.")
                return

            if state != expected_state:
                callback_result.error = "state_mismatch"
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"State invalido. Tente novamente.")
                return

            self.send_response(200)
            self.end_headers()
            self.wfile.write(
                b"Autorizacao recebida! Volte ao terminal para copiar os tokens."
            )

        def log_message(self, format: str, *args: object) -> None:
            return

    server = HTTPServer((host, port), CallbackHandler)
    server.timeout = 0.5

    start = time.time()
    while time.time() - start < timeout_seconds:
        server.handle_request()

        if callback_result.error:
            server.server_close()
            raise RuntimeError(f"Erro na callback OAuth: {callback_result.error}")

        if callback_result.code:
            server.server_close()
            return callback_result.code

    server.server_close()
    raise TimeoutError(
        "Timeout aguardando callback do Spotify. Use --code para modo manual."
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Gera SPOTIFY_ACCESS_TOKEN e SPOTIFY_REFRESH_TOKEN via OAuth do Spotify."
        )
    )
    parser.add_argument("--client-id", default="", help="Spotify Client ID")
    parser.add_argument("--client-secret", default="", help="Spotify Client Secret")
    parser.add_argument(
        "--redirect-uri",
        default="http://localhost:8888/callback",
        help="Redirect URI cadastrada no app do Spotify",
    )
    parser.add_argument(
        "--scope",
        default=DEFAULT_SCOPE,
        help="Escopos OAuth separados por espaço",
    )
    parser.add_argument(
        "--code",
        default="",
        help="Code OAuth (modo manual, sem callback automático)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=180,
        help="Tempo máximo (segundos) para esperar callback automático",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Não tenta abrir o navegador automaticamente",
    )
    parser.add_argument(
        "--show-dialog",
        action="store_true",
        help="Força tela de consentimento do Spotify",
    )
    parser.add_argument(
        "--print-auth-url",
        action="store_true",
        help="Apenas imprime URL de autorização e encerra",
    )
    return parser.parse_args()


def main() -> int:
    load_dotenv()
    args = parse_args()

    client_id = args.client_id.strip() or ""
    client_secret = args.client_secret.strip() or ""

    if not client_id or not client_secret:
        print("Erro: informe --client-id e --client-secret.")
        print("Dica: você pode copiar do Spotify Developer Dashboard.")
        return 1

    if _looks_like_placeholder(client_id) or _looks_like_placeholder(client_secret):
        print("Erro: detectei valor de exemplo em --client-id/--client-secret.")
        print("Use os valores reais do Spotify Developer Dashboard.")
        return 1

    state = secrets.token_urlsafe(24)
    auth_url = build_authorize_url(
        client_id=client_id,
        redirect_uri=args.redirect_uri,
        scope=args.scope,
        state=state,
        show_dialog=args.show_dialog,
    )

    print("\n[1/3] URL de autorização Spotify:\n")
    print(auth_url)

    if args.print_auth_url:
        print("\n--print-auth-url usado: finalize o fluxo e rode novamente com --code.")
        return 0

    code = args.code.strip()

    if not code:
        print("\n[2/3] Aguardando callback OAuth em:")
        print(args.redirect_uri)

        if not args.no_browser:
            opened = webbrowser.open(auth_url)
            if opened:
                print("Navegador aberto automaticamente.")
            else:
                print(
                    "Não foi possível abrir navegador automaticamente neste ambiente."
                )
                print("Abra a URL acima manualmente no navegador.")
        else:
            print("Abra a URL acima manualmente no navegador.")

        try:
            code = wait_for_callback_code(
                redirect_uri=args.redirect_uri,
                expected_state=state,
                timeout_seconds=args.timeout,
            )
        except Exception as exc:
            print(f"Erro ao capturar callback automático: {exc}")
            print("Você pode usar modo manual: --code <valor_do_code>")
            return 1

    print("\n[3/3] Trocando code por tokens...")

    try:
        token_info = exchange_code_for_tokens(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=args.redirect_uri,
            code=code,
            timeout_seconds=15,
        )
    except Exception as exc:
        print(f"Erro ao obter tokens: {exc}")
        return 1

    access_token = token_info.get("access_token", "")
    refresh_token = token_info.get("refresh_token", "")
    expires_in = token_info.get("expires_in")
    scope = token_info.get("scope", args.scope)

    print("\nTokens obtidos com sucesso. Cole no seu .env:\n")
    print(f"SPOTIPY_CLIENT_ID={client_id}")
    print(f"SPOTIPY_CLIENT_SECRET={client_secret}")
    print(f"SPOTIPY_REDIRECT_URI={args.redirect_uri}")
    print(f"SPOTIFY_ACCESS_TOKEN={access_token}")
    print(f"SPOTIFY_REFRESH_TOKEN={refresh_token}")

    print("\nResumo:")
    print(f"- expires_in: {expires_in} segundos")
    print(f"- scope: {scope}")

    if not refresh_token:
        print(
            "\nAviso: não veio refresh_token."
            " Tente novamente com --show-dialog para forçar novo consentimento."
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
