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
    filters,
    ContextTypes,
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

# Instagram client — bir kez login, session sakla
ig_client = Client()
IG_SESSION_FILE = "ig_session.json"


def instagram_login():
    """Instagram'a giriş yap, session varsa yükle."""
    if Path(IG_SESSION_FILE).exists():
        try:
            ig_client.load_settings(IG_SESSION_FILE)
            ig_client.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
            ig_client.dump_settings(IG_SESSION_FILE)
            logger.info("Instagram session yüklendi.")
            return
        except Exception as e:
            logger.warning(f"Session geçersiz, yeniden login: {e}")
    else:
        logger.error("ig_session.json bulunamadı! Lütfen login.py ile session oluşturun.")
        raise FileNotFoundError("ig_session.json bulunamadı")


def generate_caption(firma_adi: str) -> str:
    """Claude API ile Instagram caption oluştur."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    prompt = f"""
Sen bir sosyal medya uzmanısın. Aşağıdaki firma için Instagram'da paylaşılacak bir caption yaz.

Firma adı: {firma_adi}

Kurallar:
- Türkçe yaz
- 3-5 cümle, enerjik ve profesyonel
- Sonuna 10-15 adet ilgili hashtag ekle
- Emoji kullan ama abartma
- Caption doğrudan başlasın, "İşte caption:" gibi giriş yapma
"""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )

    return message.content[0].text.strip()


def download_photo(file_id: str, bot_token: str) -> str:
    """Telegram'dan fotoğrafı indir, geçici dosya yolunu döndür."""
    # Dosya bilgisini al
    file_info_url = f"https://api.telegram.org/bot{bot_token}/getFile?file_id={file_id}"
    resp = requests.get(file_info_url)
    file_path = resp.json()["result"]["file_path"]

    # Dosyayı indir
    download_url = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
    img_data = requests.get(download_url).content

    # Geçici dosyaya kaydet
    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    tmp.write(img_data)
    tmp.close()

    return tmp.name


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fotoğraf + caption geldiğinde çalışır."""
    message = update.message

    # Caption (firma adı) kontrolü
    firma_adi = message.caption
    if not firma_adi:
        await message.reply_text(
            "⚠️ Fotoğrafın altına firma adını yaz, sonra tekrar gönder."
        )
        return

    await message.reply_text("⏳ İşleniyor...")

    try:
        # 1. Fotoğrafı indir (en yüksek kalite)
        photo = message.photo[-1]
        photo_path = download_photo(photo.file_id, TELEGRAM_BOT_TOKEN)
        logger.info(f"Fotoğraf indirildi: {photo_path}")

        # 2. Caption oluştur
        await message.reply_text("✍️ Caption yazılıyor...")
        caption = generate_caption(firma_adi)
        logger.info(f"Caption oluşturuldu: {caption[:50]}...")

        # 3. Instagram'a post at
        await message.reply_text("📤 Instagram'a yükleniyor...")
        ig_client.photo_upload(photo_path, caption=caption)
        logger.info("Instagram'a yüklendi.")

        # 4. Başarı mesajı
        await message.reply_text(
            f"✅ Paylaşıldı!\n\n📝 Caption:\n{caption}"
        )

    except Exception as e:
        logger.error(f"Hata: {e}")
        await message.reply_text(f"❌ Hata oluştu: {str(e)}")

    finally:
        # Geçici dosyayı sil
        try:
            os.unlink(photo_path)
        except Exception:
            pass


def main():
    # Instagram login
    logger.info("Instagram'a bağlanılıyor...")
    instagram_login()

    # Telegram bot başlat
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    logger.info("Bot başlatıldı. Fotoğraf bekleniyor...")
    app.run_polling()


if __name__ == "__main__":
    main()
