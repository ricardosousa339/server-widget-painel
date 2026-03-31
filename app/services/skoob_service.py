from __future__ import annotations

from collections.abc import Iterable
import importlib
import re
import time
from typing import Any
from urllib.parse import urljoin

import requests


class SkoobSyncError(Exception):
    pass


class SkoobSyncService:
    base_url = "https://www.skoob.com.br"
    user_agent = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    reading_keywords = (
        "lendo",
        "leitura atual",
        "estou lendo",
        "lendo atualmente",
    )

    def __init__(
        self,
        profile_url: str = "",
        user_id: str = "",
        auth_cookie: str = "",
        reading_types: Iterable[str] = ("2",),
        timeout_seconds: float = 8.0,
    ) -> None:
        self.profile_url = profile_url.strip()
        self.user_id = user_id.strip()
        self.auth_cookie = auth_cookie.strip()
        self.reading_types = {value.strip() for value in reading_types if value.strip()}
        self.timeout_seconds = timeout_seconds

    def sync(
        self,
        profile_url: str | None = None,
        user_id: str | None = None,
        auth_cookie: str | None = None,
    ) -> dict[str, Any]:
        active_profile_url = (profile_url or self.profile_url).strip()
        active_user_id = (user_id or self.user_id).strip()
        active_auth_cookie = (auth_cookie or self.auth_cookie).strip()
        profile_state: dict[str, Any] | None = None

        errors: list[str] = []

        if active_profile_url:
            try:
                profile_state = self._sync_from_profile(
                    active_profile_url,
                    auth_cookie=active_auth_cookie,
                )
                if profile_state.get("is_reading"):
                    return profile_state
            except requests.RequestException as exc:
                errors.append(f"Falha ao acessar perfil Skoob: {exc}")

        if not active_user_id and active_profile_url and active_auth_cookie:
            try:
                active_user_id = self._resolve_user_id_from_profile(
                    profile_url=active_profile_url,
                    auth_cookie=active_auth_cookie,
                )
            except requests.RequestException as exc:
                errors.append(f"Falha ao inferir user_id no perfil Skoob: {exc}")

        if profile_state is not None and (not active_user_id or not active_auth_cookie):
            return profile_state

        if active_user_id and active_auth_cookie:
            try:
                return self._sync_from_private_api(
                    user_id=active_user_id,
                    auth_cookie=active_auth_cookie,
                    profile_url=active_profile_url,
                )
            except requests.RequestException as exc:
                errors.append(f"Falha ao consultar API interna do Skoob: {exc}")

        if errors:
            raise SkoobSyncError("; ".join(errors))

        raise SkoobSyncError(
            "Configure SKOOB_PROFILE_URL ou SKOOB_USER_ID + SKOOB_AUTH_COOKIE para sincronizar."
        )

    def _sync_from_profile(self, profile_url: str, auth_cookie: str = "") -> dict[str, Any]:
        BeautifulSoup = self._load_bs4()
        response = requests.get(
            profile_url,
            timeout=self.timeout_seconds,
            headers=self._headers(auth_cookie=auth_cookie),
        )
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding

        soup = BeautifulSoup(response.text, "html.parser")
        container = self._find_reading_container(soup)
        if container is None:
            return self._empty_state(source="skoob_profile", profile_url=profile_url)

        book_data = self._extract_book_data(container, base_url=profile_url)
        if not book_data:
            return self._empty_state(source="skoob_profile", profile_url=profile_url)

        state = self._empty_state(source="skoob_profile", profile_url=profile_url)
        state.update(
            {
                "is_reading": True,
                "title": book_data.get("title", ""),
                "author": book_data.get("author", ""),
                "cover_url": book_data.get("cover_url", ""),
            }
        )
        return state

    def _sync_from_private_api(
        self,
        user_id: str,
        auth_cookie: str,
        profile_url: str,
    ) -> dict[str, Any]:
        response = requests.get(
            f"{self.base_url}/v1/bookcase/books/{user_id}/shelf_id:0/limit:1000000",
            timeout=self.timeout_seconds,
            headers=self._headers(auth_cookie=auth_cookie),
        )
        response.raise_for_status()

        payload = response.json()
        if not isinstance(payload, dict):
            raise SkoobSyncError("Resposta invalida da API interna do Skoob.")

        if payload.get("cod_error"):
            cod_description = payload.get("cod_description") or "erro desconhecido"
            raise SkoobSyncError(f"Skoob retornou erro: {cod_description}")

        bookshelf = payload.get("response")
        if not isinstance(bookshelf, list):
            raise SkoobSyncError("Estante retornada pelo Skoob em formato inesperado.")

        reading_book = self._select_reading_book(bookshelf)
        if not reading_book:
            return self._empty_state(source="skoob_api", profile_url=profile_url)

        edition = reading_book.get("edicao") if isinstance(reading_book.get("edicao"), dict) else {}
        title = self._normalize_text(str(edition.get("titulo", "")))
        author = self._normalize_text(str(edition.get("autor", "")))
        cover_url = self._normalize_cover_url(
            str(
                edition.get("capa_grande")
                or edition.get("capa_media")
                or edition.get("img_url")
                or ""
            ),
            base_url=self.base_url,
        )

        state = self._empty_state(source="skoob_api", profile_url=profile_url)
        state.update(
            {
                "is_reading": bool(title or author or cover_url),
                "title": title,
                "author": author,
                "cover_url": cover_url,
            }
        )

        edition_id = edition.get("id")
        if edition_id is not None:
            state["skoob_book_id"] = edition_id

        return state

    def _select_reading_book(self, books: list[dict[str, Any]]) -> dict[str, Any] | None:
        if not books:
            return None

        reading_candidates = [
            book
            for book in books
            if str(book.get("tipo", "")).strip() in self.reading_types
        ]

        if not reading_candidates:
            reading_candidates = [book for book in books if self._looks_like_reading(book)]

        if not reading_candidates:
            return None

        return max(reading_candidates, key=self._candidate_score)

    def _looks_like_reading(self, book: dict[str, Any]) -> bool:
        read_date = str(book.get("dt_leitura", "")).strip()
        pages = str(book.get("paginas", "")).strip()
        return not read_date and pages not in {"", "0"}

    def _candidate_score(self, book: dict[str, Any]) -> tuple[int, int, int]:
        update_flag = 1 if str(book.get("update", "")).strip() else 0
        pages = self._to_int(book.get("paginas"))
        rating = self._to_int(book.get("ranking"))
        return (update_flag, pages, rating)

    def _find_reading_container(self, soup: Any) -> Any:
        selector_candidates = [
            "[id*='lendo']",
            "[class*='lendo']",
            "[data-section*='lendo']",
        ]
        for selector in selector_candidates:
            for container in soup.select(selector):
                if not self._is_tag(container):
                    continue
                if self._extract_book_data(container, base_url=self.base_url):
                    return container

        for text_node in soup.find_all(string=True):
            normalized = self._normalize_text(text_node)
            if not normalized:
                continue
            normalized_lower = normalized.lower()
            if not any(keyword in normalized_lower for keyword in self.reading_keywords):
                continue

            parent = text_node.parent
            hops = 0
            while self._is_tag(parent) and hops < 6:
                if self._extract_book_data(parent, base_url=self.base_url):
                    return parent
                parent = parent.parent
                hops += 1

        return None

    def _extract_book_data(self, container: Any, base_url: str) -> dict[str, str] | None:
        book_anchor = container.select_one("a[href*='/livro/']")
        if self._is_tag(book_anchor):
            title = self._extract_title(book_anchor)
            author = self._extract_author(container)
            cover_url = self._extract_cover_from_tag(book_anchor, base_url=base_url)
            if title or author or cover_url:
                return {
                    "title": title,
                    "author": author,
                    "cover_url": cover_url,
                }

        image_tag = container.find("img")
        if self._is_tag(image_tag):
            title = self._normalize_text(str(image_tag.get("alt", "")))
            author = self._extract_author(container)
            cover_url = self._extract_cover_from_tag(image_tag, base_url=base_url)
            if title or author or cover_url:
                return {
                    "title": title,
                    "author": author,
                    "cover_url": cover_url,
                }

        return None

    def _extract_title(self, anchor: Any) -> str:
        title = self._normalize_text(str(anchor.get("title", "")))
        if title:
            return title

        image = anchor.find("img")
        if self._is_tag(image):
            image_alt = self._normalize_text(str(image.get("alt", "")))
            if image_alt:
                return image_alt

        return self._normalize_text(anchor.get_text(" ", strip=True))

    def _extract_author(self, container: Any) -> str:
        author_selectors = [
            ".autor",
            ".author",
            "[class*='autor']",
            "[class*='author']",
            "a[href*='/autor/']",
        ]

        for selector in author_selectors:
            tag = container.select_one(selector)
            if not self._is_tag(tag):
                continue
            text = self._normalize_text(tag.get_text(" ", strip=True))
            if text:
                return text

        text_block = self._normalize_text(container.get_text(" ", strip=True))
        if not text_block:
            return ""

        match = re.search(r"\bpor\s+([^|\n\r]{2,80})", text_block, flags=re.IGNORECASE)
        if not match:
            return ""
        return self._normalize_text(match.group(1))

    def _extract_cover_from_tag(self, tag: Any, base_url: str) -> str:
        image_tag: Any = None
        if tag.name == "img":
            image_tag = tag
        else:
            image_tag = tag.find("img")

        if not self._is_tag(image_tag):
            return ""

        for attribute in ("data-src", "data-original", "src"):
            value = str(image_tag.get(attribute, "")).strip()
            normalized = self._normalize_cover_url(value, base_url=base_url)
            if normalized:
                return normalized

        return ""

    def _resolve_user_id_from_profile(self, profile_url: str, auth_cookie: str) -> str:
        response = requests.get(
            profile_url,
            timeout=self.timeout_seconds,
            headers=self._headers(auth_cookie=auth_cookie),
        )
        response.raise_for_status()

        html = response.text
        patterns = (
            r"/v1/bookcase/books/(\d+)/",
            r"bookcase/books/(\d+)/",
            r'"user_id"\s*:\s*"?(\d+)"?',
            r'"id_usuario"\s*:\s*"?(\d+)"?',
            r"userId\s*[:=]\s*'?(\d+)'?",
            r"idUsuario\s*[:=]\s*'?(\d+)'?",
        )

        for pattern in patterns:
            match = re.search(pattern, html, flags=re.IGNORECASE)
            if not match:
                continue
            return match.group(1).strip()

        return ""

    def _normalize_cover_url(self, value: str, base_url: str) -> str:
        if not value or value.startswith("data:image"):
            return ""
        return urljoin(base_url, value)

    def _normalize_text(self, text: str) -> str:
        normalized = re.sub(r"\s+", " ", text or "").strip()
        normalized = normalized.strip("-|\u2014")
        return normalized

    def _headers(self, auth_cookie: str | None = None) -> dict[str, str]:
        headers = {
            "User-Agent": self.user_agent,
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        }
        cookie = auth_cookie if auth_cookie is not None else self.auth_cookie
        if cookie.strip():
            headers["Cookie"] = cookie.strip()
        return headers

    def _to_int(self, value: Any) -> int:
        try:
            return int(str(value).strip())
        except (TypeError, ValueError):
            return 0

    def _load_bs4(self) -> Any:
        try:
            module = importlib.import_module("bs4")
            return module.BeautifulSoup
        except ModuleNotFoundError as exc:
            raise SkoobSyncError(
                "Dependencia beautifulsoup4 nao instalada. Execute pip install -r requirements.txt"
            ) from exc

    def _is_tag(self, value: Any) -> bool:
        return hasattr(value, "select_one") and hasattr(value, "get_text")

    def _empty_state(self, source: str, profile_url: str = "") -> dict[str, Any]:
        return {
            "is_reading": False,
            "title": "",
            "author": "",
            "cover_url": "",
            "sync_source": source,
            "profile_url": profile_url,
            "last_sync_ts": int(time.time()),
        }
