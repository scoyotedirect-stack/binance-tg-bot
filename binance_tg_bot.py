import os
import logging
from datetime import datetime
import httpx
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes


# Импорты из локальных модулей
from scraper import get_filtered_symbols
from natr_calculator import get_natr_for_symbols

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def format_volume(volume):
    """Форматирует объём в читаемый вид с символом $."""
    if volume < 1_000_000:
        return f"${volume:,.0f}"
    elif volume < 1_000_000_000:
        return f"${volume / 1_000_000:.1f}M$"
    else:
        return f"${volume / 1_000_000_000:.1f}B$"

def get_trend_emoji(change):
    """Возвращает эмодзи в зависимости от изменения цены."""
    return "🟢" if change >= 0 else "🔴"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Получен /start от {update.effective_user.id}")


    # 1. Получаем отфильтрованные символы
    symbols = get_filtered_symbols()
    if not symbols:
        await update.message.reply_text("❌ Нет символов для анализа (фильтр).")
        return

    # 2. Рассчитываем NATR
    try:
        natr_data = await get_natr_for_symbols(symbols)
    except Exception as e:
        logger.error(f"Ошибка расчёта NATR: {e}")
        await update.message.reply_text("❌ Ошибка при расчёте NATR.")
        return

    # 3. Получаем тикеры с Binance
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://fapi.binance.com/fapi/v1/ticker/24hr",
                timeout=10
            )
            response.raise_for_status()
            ticker_data = {t["symbol"]: t for t in response.json()}
    except Exception as e:
        logger.error(f"Ошибка загрузки тикеров: {e}")
        await update.message.reply_text("❌ Ошибка загрузки данных с Binance.")
        return

    # 4. Фильтруем и собираем результат
    result = []
    natr_threshold = float(os.environ["NATR_THRESHOLD"])  # Обязательная переменная


    for symbol in natr_data:
        ticker = ticker_data.get(symbol)
        if not ticker:
            continue

        volume_usd = float(ticker["lastPrice"]) * float(ticker["volume"])
        price_change = float(ticker["priceChangePercent"])
        natr = natr_data[symbol]


        if natr is not None and natr >= natr_threshold:
            result.append({
                "symbol": symbol,
                "volume_usd": round(volume_usd, 2),
                "price_change": round(price_change, 1),
                "natr": natr
            })

    if not result:
        await update.message.reply_text(f"❌ Нет пар с NATR ≥ {natr_threshold}%.")
        return

    # 5. Сортируем по объёму
    result.sort(key=lambda x: x["volume_usd"], reverse=True)


    # 6. Формируем сообщение
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    msg_lines = [f"📊 <b>Инплей</b> ({now})", ""]


    for item in result:
        emoji = get_trend_emoji(item["price_change"])
        change_sign = "+" if item["price_change"] >= 0 else ""
        line = (
            f"{emoji}{change_sign}{item['price_change']}% "
            f"<code>{item['symbol']}</code> "
            f"{format_volume(item['volume_usd'])} "
            f"N={item['natr']}"
        )
        msg_lines.append(line)


    message = "\n".join(msg_lines)


    # 7. Отправляем ответ
    if len(message) > 4096:
        parts = [message[i:i+4096] for i in range(0, len(message), 4096)]
        for part in parts:
            await update.message.reply_text(part, parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(message, parse_mode=ParseMode.HTML)


async def main():
    token = os.environ["TELEGRAM_BOT_TOKEN"]

    app = Application.builder().token(token).build()

    try:
        await app.bot.delete_webhook()
    except Exception as e:
        logger.warning(f"Не удалось удалить webhook: {e}")

    app.add_handler(CommandHandler("start", start))
    logger.info("Бот запущен. Ожидает команд...")

    app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())  # ← Ключевое изменение!

if __name__ == "__main__":
    main()
