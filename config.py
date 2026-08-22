import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _parse_ids(raw: str) -> set[int]:
    return {int(v.strip()) for v in raw.split(",") if v.strip()}


@dataclass(frozen=True)
class Config:
    telegram_bot_token: str = os.environ["TELEGRAM_BOT_TOKEN"]
    allowed_user_ids: set[int] = field(
        default_factory=lambda: _parse_ids(os.environ["TELEGRAM_ALLOWED_USER_IDS"])
    )
    group_chat_id: int | None = field(
        default_factory=lambda: (
            int(os.environ["TELEGRAM_GROUP_CHAT_ID"])
            if os.environ.get("TELEGRAM_GROUP_CHAT_ID")
            else None
        )
    )

    prestador_cnpj: str = os.environ["PRESTADOR_CNPJ"]
    tomador_cnpj: str = os.environ["TOMADOR_CNPJ"]
    valor_unitario: float = float(os.environ["VALOR_UNITARIO"])

    codigo_tributacao_nacional: str = "14.06.01"
    descricao_servico: str = (
        "Montagem de equipamentos exclusivos para aplicação em máquinas de auto atendimento."
    )

    playwright_headless: bool = os.environ.get("PLAYWRIGHT_HEADLESS", "true").lower() == "true"
    browser_state_path: str = os.environ.get("BROWSER_STATE_PATH", "data/govbr_session.json")


config = Config()
