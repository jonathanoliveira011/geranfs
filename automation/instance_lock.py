"""Trava simples de instância única, via arquivo de heartbeat no volume persistente.

Evita o cenário visto em produção: um deploy que deixa o container antigo rodando
junto com o novo, os dois disputando o polling do Telegram (erro "Conflict").
"""

import datetime
from pathlib import Path

from config import config

LOCK_PATH = Path(config.browser_state_path).parent / "bot.lock"
HEARTBEAT_TIMEOUT_SEGUNDOS = 90


class OutraInstanciaAtivaError(Exception):
    """Já existe outro processo do bot com heartbeat recente."""


def _ler_timestamp() -> datetime.datetime | None:
    try:
        conteudo = LOCK_PATH.read_text(encoding="utf-8").strip()
        return datetime.datetime.fromisoformat(conteudo)
    except (FileNotFoundError, ValueError):
        return None


def garantir_instancia_unica() -> None:
    ultimo = _ler_timestamp()
    if ultimo is not None:
        idade = (datetime.datetime.now() - ultimo).total_seconds()
        if idade < HEARTBEAT_TIMEOUT_SEGUNDOS:
            raise OutraInstanciaAtivaError(
                f"Heartbeat de outra instância com {idade:.0f}s de idade "
                f"(limite: {HEARTBEAT_TIMEOUT_SEGUNDOS}s)."
            )

    atualizar_heartbeat()


def atualizar_heartbeat() -> None:
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOCK_PATH.write_text(datetime.datetime.now().isoformat(), encoding="utf-8")


def liberar_lock() -> None:
    """Remove o lock no encerramento limpo, pra um redeploy logo em seguida não
    esbarrar falsamente no heartbeat desta instância que já foi encerrada."""
    LOCK_PATH.unlink(missing_ok=True)
