"""Converte export do Cookie-Editor (JSON) para o formato storage_state do Playwright."""

import json
from pathlib import Path

SRC = Path("cookies.json")
DST = Path("data/govbr_session.json")


def map_same_site(value: str | None) -> str:
    mapping = {
        "no_restriction": "None",
        "lax": "Lax",
        "strict": "Strict",
        "unspecified": "Lax",
    }
    if not value:
        return "Lax"
    return mapping.get(value.lower(), "Lax")


def main():
    raw_cookies = json.loads(SRC.read_text(encoding="utf-8"))

    cookies = []
    for c in raw_cookies:
        cookies.append(
            {
                "name": c["name"],
                "value": c["value"],
                "domain": c["domain"],
                "path": c.get("path", "/"),
                "expires": c.get("expirationDate", -1) if not c.get("session") else -1,
                "httpOnly": c.get("httpOnly", False),
                "secure": c.get("secure", False),
                "sameSite": map_same_site(c.get("sameSite")),
            }
        )

    storage_state = {"cookies": cookies, "origins": []}

    DST.parent.mkdir(parents=True, exist_ok=True)
    DST.write_text(json.dumps(storage_state, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{len(cookies)} cookies convertidos -> {DST}")


if __name__ == "__main__":
    main()
