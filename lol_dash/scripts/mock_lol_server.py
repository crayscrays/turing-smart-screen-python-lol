"""
Mock Riot Live Client Data API for offline development.

Mimics the real local server on https://127.0.0.1:2999 with a self-signed
cert. Cycles a "fake game" so you can see the dashboard react without
launching League.

Usage:
    python scripts/mock_lol_server.py

The main app will hit it as-is — just leave `lol.endpoint` pointing at
https://127.0.0.1:2999/liveclientdata/allgamedata.
"""

from __future__ import annotations

import json
import ssl
import sys
import tempfile
import time
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# Cycle a simulated game over time so you can see the dashboard react.
START = time.monotonic()
CHAMPION = "Annie"
SUMMONER = "MockSummoner"


def fake_active():
    t = time.monotonic() - START
    # Level up over time
    level = min(18, 1 + int(t / 30))
    q = min(5, max(0, level // 2))
    w = min(5, max(0, (level - 1) // 3))
    e = min(5, max(0, (level - 4) // 3)) if level >= 4 else 0
    r = min(3, max(0, (level - 5) // 5)) if level >= 6 else 0

    # Oscillate mana to simulate spell casts
    mana_max = 250 + level * 25
    cycle = int(t) % 8
    mana_value = mana_max - (60 if cycle == 0 else 0)

    return {
        "abilities": {
            "Q": {"abilityLevel": q, "displayName": "Disintegrate", "id": "AnnieQ"},
            "W": {"abilityLevel": w, "displayName": "Incinerate",   "id": "AnnieW"},
            "E": {"abilityLevel": e, "displayName": "Molten Shield","id": "AnnieE"},
            "R": {"abilityLevel": r, "displayName": "Summon: Tibbers","id": "AnnieR"},
            "Passive": {"displayName": "Pyromania"},
        },
        "championStats": {
            "currentHealth": 500 + level * 80 - (t % 100),
            "maxHealth": 560 + level * 90,
            "resourceValue": mana_value,
            "resourceMax": mana_max,
            "resourceType": "MANA",
        },
        "currentGold": 350 + (t * 8) % 4000,
        "level": level,
        "summonerName": SUMMONER,
    }


def fake_scores():
    t = time.monotonic() - START
    return {
        "kills":    int(t / 60),
        "deaths":   int(t / 110),
        "assists":  int(t / 35),
        "creepScore": int(t * 0.9),
        "wardScore": float(int(t / 20)),
    }


def fake_playerlist():
    return [{
        "championName": CHAMPION,
        "rawChampionName": f"game_character_displayname_{CHAMPION}",
        "summonerName": SUMMONER,
        "team": "ORDER",
        "level": fake_active()["level"],
        "isBot": False,
        "isDead": False,
    }]


def fake_gamestats():
    return {"gameTime": time.monotonic() - START, "mapName": "Map11"}


class Handler(BaseHTTPRequestHandler):
    def _send(self, body):
        payload = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):  # noqa: N802
        if self.path.startswith("/liveclientdata/activeplayer"):
            return self._send(fake_active())
        if self.path.startswith("/liveclientdata/playerlist"):
            return self._send(fake_playerlist())
        if self.path.startswith("/liveclientdata/playerscores"):
            return self._send(fake_scores())
        if self.path.startswith("/liveclientdata/gamestats"):
            return self._send(fake_gamestats())
        if self.path.startswith("/liveclientdata/allgamedata"):
            return self._send({
                "activePlayer": fake_active(),
                "allPlayers": fake_playerlist(),
                "gameData": fake_gamestats(),
                "events": {"Events": []},
            })
        self.send_error(404)

    def log_message(self, *_):  # silence
        pass


def _selfsigned_cert():
    """Generate an ephemeral self-signed cert for 127.0.0.1."""
    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID
        import datetime as _dt
    except ImportError:
        print("Install cryptography for the mock server: pip install cryptography", file=sys.stderr)
        sys.exit(1)

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "LocalHost")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name).issuer_name(name).public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(_dt.datetime.utcnow())
        .not_valid_after(_dt.datetime.utcnow() + _dt.timedelta(days=1))
        .add_extension(x509.SubjectAlternativeName([x509.IPAddress(__import__("ipaddress").IPv4Address("127.0.0.1"))]), False)
        .sign(key, hashes.SHA256())
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    key_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    f = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")
    f.write(cert_pem + key_pem)
    f.close()
    return f.name


def main():
    pem = _selfsigned_cert()
    server = HTTPServer(("127.0.0.1", 2999), Handler)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(pem)
    server.socket = ctx.wrap_socket(server.socket, server_side=True)
    print("Mock LoL server running on https://127.0.0.1:2999")
    print("Tip: in the main app, the TLS verify will fail against this cert —")
    print("      either point cert_path at an empty file or pass --mock to disable verify.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
