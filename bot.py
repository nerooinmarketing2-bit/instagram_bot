import os
import logging
import tempfile
import requests
from pathlib import Path
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)

import anthropic
from instagrapi import Client

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

ig_client = Client()
IG_SESSION_FILE = "ig_session.json"

# Conversation states
FOTO, FIRMA, KONU = range(3)


def instagram_login():
    if Path(IG_SESSION_FILE).exists():
        try:
            ig_client.load_settings(IG_SESSION_FILE)
            ig_client.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
            ig_client.dump_settings(IG_SESSION_FILE)
            logger.info("Instagram session yüklendi.")
            return
        except Exception as e:
            logger.warning(f"Session geçersiz: {e}")
    else:
        logger.error("ig_session.json bulunamadı!")
        raise FileNotFoundError("ig_session.json bulunamadı")


def generate_caption(firma_adi: str, konu: str) -> str:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    prompt = f"""
Sen bir sosyal medya uzmanısın. Aşağıdaki bilgilere göre Instagram caption yaz.

Firma adı: {firma_adi}
Konu/Brief: {konu}

Kurallar:
- Türkçe yaz
- 3-5 cümle, enerjik ve profesyonel
- Brief'teki mesajı ve tonu yansıt
- Sonuna 10-15 adet ilgili hashtag ekle
- Emoji kullan ama abartma
- Caption doğrudan başlasın
"""

    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text.strip()


def download_photo(file_id: str, bot_token: str) -> str:
    file_info_url = f"https://api.telegram.org/bot{bot_token}/getFile?file_id={file_id}"
    resp = requests.get(file_info_url)
    file_path = resp.json()["result"]["file_path"]
    download_url = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
    img_data = requests.get(download_url).content
    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    tmp.write(img_data)
    tmp.close()
    return tmp.name


# --- Conversation handlers ---

async def foto_al(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fotoğraf geldi, firma adını sor."""
    photo = update.message.photo[-1]
    context.user_data["file_id"] = photo.file_id
    await update.message.reply_text("🏢 Firma adı nedir?")
    return FIRMA


async def firma_al(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Firma adı geldi, konu/brief sor."""
    context.user_data["firma"] = update.message.text.strip()
    await update.message.reply_text("📝 Konu veya brief nedir?\n\n(Örnek: Yeni ürün lansmanı, fiyat indirimi, kampanya detayları...)")
    return KONU


async def konu_al(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Konu geldi, caption üret ve Instagram'a paylaş."""
    konu = update.message.text.strip()
    firma = context.user_data["firma"]
    file_id = context.user_data["file_id"]

    await update.message.reply_text("⏳ İşleniyor...")

    photo_path = None
    try:
        photo_path = download_photo(file_id, TELEGRAM_BOT_TOKEN)

        await update.message.reply_text("✍️ Caption yazılıyor...")
        caption = generate_caption(firma, konu)

        await update.message.reply_text("📤 Instagram'a yükleniyor...")
        ig_client.photo_upload(photo_path, caption=caption)

        await update.message.reply_text(
            f"✅ Paylaşıldı!\n\n📝 Caption:\n{caption}"
        )

    except Exception as e:
        logger.error(f"Hata: {e}")
        await update.message.reply_text(f"❌ Hata oluştu: {str(e)}")

    finally:
        if photo_path:
            try:
                os.unlink(photo_path)
            except Exception:
                pass
        context.user_data.clear()

    return ConversationHandler.END


async def iptal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ İptal edildi.")
    return ConversationHandler.END


def main():
    logger.info("Instagram'a bağlanılıyor...")
    instagram_login()

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.PHOTO, foto_al)],
        states={
            FIRMA: [MessageHandler(filters.TEXT & ~filters.COMMAND, firma_al)],
            KONU: [MessageHandler(filters.TEXT & ~filters.COMMAND, konu_al)],
        },
        fallbacks=[CommandHandler("iptal", iptal)],
    )

    app.add_handler(conv_handler)

    logger.info("Bot başlatıldı. Fotoğraf bekleniyor...")
    app.run_polling()


if __name__ == "__main__":
    main()
