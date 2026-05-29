"""Download / verify Riot's self-signed cert for the Live Client API."""

from __future__ import annotations

import logging
import os
import urllib.request

CERT_URL = "https://static.developer.riotgames.com/docs/lol/riotgames.pem"

log = logging.getLogger(__name__)


def ensure_cert(path: str) -> bool:
    """Download the cert if missing. Returns True on success."""
    if os.path.isfile(path) and os.path.getsize(path) > 200:
        return True
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    try:
        log.info("Downloading Riot cert → %s", path)
        urllib.request.urlretrieve(CERT_URL, path)
        return os.path.getsize(path) > 200
    except Exception as e:  # noqa: BLE001
        log.error("Failed to download Riot cert: %s", e)
        return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ok = ensure_cert("lol_dash/certs/riotgames.pem")
    raise SystemExit(0 if ok else 1)
