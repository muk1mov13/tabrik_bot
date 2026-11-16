# 🎂 Tug'ilgan kun eslatuvchi Telegram bot

aiogram 3.x + APScheduler + PostgreSQL (asyncpg) asosida qurilgan bot. Guruh
a'zolarining tug'ilgan kunlarini saqlaydi va har kuni belgilangan vaqtda
(default 08:00, Toshkent vaqti) tug'ilgan kuni bor odamni guruhda bir marta
tabriklaydi.

## O'rnatish (lokal)

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # qiymatlarni to'ldiring
python bot.py
```

`birthdays` jadvali bot birinchi marta ishga tushganda avtomatik yaratiladi —
qo'lda migration kerak emas.

Serverga joylash: [deploy/DEPLOY.md](deploy/DEPLOY.md) (Ubuntu + systemd).

## Sozlamalar (`.env`)

| O'zgaruvchi | Majburiy | Tavsif |
|---|---|---|
| `BOT_TOKEN` | ha | [@BotFather](https://t.me/BotFather) tokeni |
| `DATABASE_URL` | ha | `postgresql://user:parol@localhost:5432/db` |
| `DEFAULT_GROUP_ID` | yo'q | Shaxsiy chatdan yozilgan buyruqlar shu guruhga tegishli bo'ladi |
| `NOTIFICATION_TIME` | yo'q | Tabrik vaqti, `HH:MM` (default `08:00`) |
| `TIMEZONE` | yo'q | Vaqt mintaqasi (default `Asia/Tashkent`) |

## Buyruqlar

| Buyruq | Kim uchun | Tavsif |
|---|---|---|
| `/start`, `/help` | hamma | Yordam matni |
| `/add Ism 15.03` | admin | Tug'ilgan kun qo'shish (kun.oy) |
| `/add Ism 15.03.1998` | admin | Yil bilan qo'shish (yosh avtomatik hisoblanadi) |
| `/list` | hamma | Guruhdagi barcha saqlangan tug'ilgan kunlar |
| `/upcoming` | hamma | Kelasi 7 kun ichidagi tug'ilgan kunlar |
| `/remove ID` | admin | Yozuvni o'chirish (`ID` ni `/list` dan oling) |

Shaxsiy chatda `/add` va `/remove` faqat `DEFAULT_GROUP_ID` guruhining
adminlari uchun ishlaydi.

29-fevralda tug'ilganlar kabisa bo'lmagan yillarda 28-fevralda tabriklanadi.

## Fayllar tuzilishi

```
birthdate-bot/
├── bot.py           # Asosiy kirish nuqtasi
├── database.py      # PostgreSQL bilan ishlash
├── handlers.py      # /add, /list, /upcoming, /remove buyruqlari
├── scheduler.py     # Kunlik tekshiruv va xabar yuborish
├── utils.py         # Vaqt mintaqasi, sana tekshiruvi, umumiy konstantalar
├── tests/           # pytest testlari
└── deploy/          # systemd xizmati va deploy qo'llanmasi
```

## Testlar

```bash
pip install -r requirements-dev.txt
pytest
```
