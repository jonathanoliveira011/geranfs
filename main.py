import logging
import sys

from automation.instance_lock import OutraInstanciaAtivaError
from bot.handlers import build_application

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def main() -> None:
    try:
        application = build_application()
    except OutraInstanciaAtivaError as e:
        logger.critical(
            "Recusando iniciar: já existe outra instância do bot rodando (%s). "
            "Provavelmente sobrou um container antigo de um deploy anterior.",
            e,
        )
        sys.exit(1)

    application.run_polling()


if __name__ == "__main__":
    main()
