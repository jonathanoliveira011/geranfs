import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from automation.nfse_emitter import NfseEmitter, SessaoExpiradaError, sessao_esta_ativa
from config import config

logger = logging.getLogger(__name__)

AGUARDANDO_QUANTIDADE = 1
KEEP_ALIVE_INTERVALO_SEGUNDOS = 15 * 60


def _autorizado(update: Update) -> bool:
    user = update.effective_user
    return user is not None and user.id in config.allowed_user_ids


async def nota_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not _autorizado(update):
        await update.message.reply_text("Você não está autorizado a usar este bot.")
        return ConversationHandler.END

    await update.message.reply_text("Quantas peças foram produzidas?")
    return AGUARDANDO_QUANTIDADE


async def receber_quantidade(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    texto = update.message.text.strip()

    if not texto.isdigit() or int(texto) <= 0:
        await update.message.reply_text("Digite um número válido de peças (ex: 100).")
        return AGUARDANDO_QUANTIDADE

    quantidade = int(texto)
    valor_total = round(quantidade * config.valor_unitario, 2)
    context.user_data["quantidade"] = quantidade

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Confirmar", callback_data="confirmar"),
                InlineKeyboardButton("❌ Cancelar", callback_data="cancelar"),
            ]
        ]
    )
    await update.message.reply_text(
        f"Resumo da nota:\n\n"
        f"Quantidade: {quantidade} peças\n"
        f"Valor unitário: R$ {config.valor_unitario:.2f}\n"
        f"Valor total: R$ {valor_total:.2f}\n\n"
        f"Confirma a emissão?",
        reply_markup=keyboard,
    )
    return ConversationHandler.END


async def confirmar_emissao(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if not _autorizado(update):
        await query.edit_message_text("Você não está autorizado a usar este bot.")
        return

    if query.data == "cancelar":
        await query.edit_message_text("Emissão cancelada.")
        return

    quantidade = context.user_data.get("quantidade")
    if not quantidade:
        await query.edit_message_text("Sessão expirada, use /nota novamente.")
        return

    await query.edit_message_text("Emitindo nota fiscal, aguarde...")

    try:
        async with NfseEmitter() as emitter:
            resultado = await emitter.emitir(quantidade)
    except SessaoExpiradaError:
        await query.edit_message_text(
            "A sessão de login expirou. Avise o Oliver para reautenticar o bot."
        )
        return
    except Exception:
        logger.exception("Falha ao emitir NFS-e")
        await query.edit_message_text(
            "Erro ao emitir a nota. Vou avisar o Oliver para verificar."
        )
        return

    await query.edit_message_text(
        f"✅ Nota fiscal emitida com sucesso!\n\n"
        f"Chave de acesso: {resultado.chave_acesso}\n"
        f"Valor total: R$ {resultado.valor_total:.2f}\n\n"
        f"O PDF pode ser baixado no portal nfse.gov.br quando precisar."
    )


async def chatid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _autorizado(update):
        return
    await update.message.reply_text(f"Chat ID: {update.effective_chat.id}")


async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Operação cancelada.")
    return ConversationHandler.END


async def keep_alive_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Visita o Dashboard periodicamente para evitar expiração da sessão por inatividade."""
    ja_avisou = context.bot_data.get("sessao_avisada_expirada", False)

    try:
        ativa = await sessao_esta_ativa()
    except Exception:
        logger.exception("Erro ao checar keep-alive da sessão")
        return

    if ativa:
        context.bot_data["sessao_avisada_expirada"] = False
        return

    if not ja_avisou and config.group_chat_id:
        await context.bot.send_message(
            chat_id=config.group_chat_id,
            text=(
                "⚠️ A sessão do gov.br expirou. Peça para o Oliver reexportar os "
                "cookies para o bot voltar a emitir notas."
            ),
        )
    context.bot_data["sessao_avisada_expirada"] = True


def build_application() -> Application:
    application = Application.builder().token(config.telegram_bot_token).build()

    if application.job_queue is not None:
        application.job_queue.run_repeating(
            keep_alive_job, interval=KEEP_ALIVE_INTERVALO_SEGUNDOS, first=60
        )

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("nota", nota_start)],
        states={
            AGUARDANDO_QUANTIDADE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receber_quantidade)
            ],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
    )

    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(confirmar_emissao))
    application.add_handler(CommandHandler("chatid", chatid))

    return application
