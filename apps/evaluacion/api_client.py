import os
import requests


def fetch_json(url: str, api_key: str | None = None, timeout: int = 15) -> dict:
    """Consume una API externa y retorna JSON (dict).

    - Si api_key está presente se envía como Bearer token.
    - Para cambiar el esquema de auth, modifica headers en esta función.
    """
    if not url:
        raise ValueError("URL vacía para la API")

    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    r = requests.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.json()

