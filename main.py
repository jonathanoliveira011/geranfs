import logging

from bot.handlers import build_application

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)


def main() -> None:
    application = build_application()
    application.run_polling()


if __name__ == "__main__":
    main()
