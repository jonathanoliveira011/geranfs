"""Histórico local das notas emitidas - útil para conferência sem depender do portal."""

import csv
import datetime
from pathlib import Path

from config import config

HISTORICO_PATH = Path(config.browser_state_path).parent / "historico.csv"
CABECALHO = ["data_hora", "quantidade", "valor_unitario", "valor_total", "chave_acesso"]


def registrar(quantidade: int, valor_total: float, chave_acesso: str) -> None:
    HISTORICO_PATH.parent.mkdir(parents=True, exist_ok=True)
    novo_arquivo = not HISTORICO_PATH.exists()

    with HISTORICO_PATH.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if novo_arquivo:
            writer.writerow(CABECALHO)
        writer.writerow(
            [
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                quantidade,
                f"{config.valor_unitario:.2f}",
                f"{valor_total:.2f}",
                chave_acesso,
            ]
        )


def ultimas(n: int = 5) -> list[dict]:
    if not HISTORICO_PATH.exists():
        return []

    with HISTORICO_PATH.open(encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))
    return linhas[-n:]
