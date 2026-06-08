# Telegram → Instagram Bot

## Kurulum

```bash
pip install -r requirements.txt
```

## Ayarlar

`.env` dosyasını doldur:

```
TELEGRAM_BOT_TOKEN=buraya_yaz
INSTAGRAM_USERNAME=buraya_yaz
INSTAGRAM_PASSWORD=buraya_yaz
ANTHROPIC_API_KEY=buraya_yaz
```

## Çalıştır

```bash
python bot.py
```

## Kullanım

1. Telegram'da bota fotoğraf gönder
2. **Caption alanına** firma adını yaz (fotoğrafın altındaki metin kutusu)
3. Gönder — bot otomatik olarak:
   - AI ile caption yazar
   - Instagram'a post atar
   - Sana sonucu bildirir

## Notlar

- İlk çalıştırmada Instagram login olur, `ig_session.json` oluşur
- Sonraki çalıştırmalarda session kullanır (daha hızlı)
- Instagram 2FA açıksa kapatman gerekebilir
