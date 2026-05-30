"""Download / verify Riot's self-signed cert for the Live Client API."""

from __future__ import annotations

import logging
import os
import ssl
import urllib.request

CERT_URL = "https://static.developer.riotgames.com/docs/lol/riotgames.pem"

log = logging.getLogger(__name__)


def _make_ssl_context() -> ssl.SSLContext:
    """Build an SSL context that works inside PyInstaller bundles on macOS/Windows.

    The frozen Python bundled by PyInstaller doesn't know where the OS
    keychain lives, so urllib's default context can't find a CA bundle.
    `certifi` ships a Mozilla CA bundle that works everywhere.
    """
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def ensure_cert(path: str) -> bool:
    """Download the cert if missing. Returns True on success."""
    if os.path.isfile(path) and os.path.getsize(path) > 200:
        return True
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    try:
        log.info("Downloading Riot cert → %s", path)
        ctx = _make_ssl_context()
        req = urllib.request.Request(CERT_URL, headers={"User-Agent": "lol-turing-dash"})
        with urllib.request.urlopen(req, context=ctx, timeout=10) as resp, open(path, "wb") as f:
            f.write(resp.read())
        return os.path.getsize(path) > 200
    except Exception as e:  # noqa: BLE001
        log.error("Failed to download Riot cert: %s", e)
        return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ok = ensure_cert("lol_dash/certs/riotgames.pem")
    raise SystemExit(0 if ok else 1)
