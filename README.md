# 🎂 Tug'ilgan kun eslatuvchi Telegram bot

aiogram 3.x + APScheduler + SQLite asosida qurilgan bot. Guruh a'zolarining
tug'ilgan kunlarini saqlaydi, har kuni belgilangan vaqtda (default 08:00,
Toshkent vaqti) tug'ilgan kuni bor odamni guruhda bir marta tabriklaydi va
xohlasangiz bir necha kun oldin eslatib qo'yadi. Alohida baza serveri kerak
emas — ma'lumotlar bitta faylda saqlanadi.

## O'rnatish (lokal)

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # BOT_TOKEN ni yozing
python -m birthday_bot
```

Baza fayli (`data/birthdays.db`) va jadvallar birinchi ishga tushishda
avtomatik yaratiladi.

## Qanday ishlatiladi

1. Botni oila guruhiga qo'shing (admin qilish shart emas). Bot salomlashadi va
   **➕ Tug'ilgan kun qo'shish** tugmasini yuboradi.
2. Guruh admini tugmani bosadi — botning shaxsiy chati ochiladi. U yerda
   **➕ Qo'shish**, **📋 Ro'yxat** va **⚙️ Sozlamalar** tugmalari bor: bot ism va
   sanani so'raydi, buyruq yodlash shart emas.
3. Tug'ilgan kun kelganda bot guruhda tabriklaydi — hamma xabardor bo'ladi.

Keyinchalik shaxsiy chatda `/menu` yozish kifoya. Bir necha guruh admini bo'lsangiz,
bot qaysi guruh bilan ishlashni so'raydi. Tugma ko'rinmay qolsa, guruhda `/menu`
yozing. Tug'ilgan kunlarni faqat guruh adminlari qo'sha oladi; boshqalar
`/list` va `/upcoming` dan foydalanadi.

Serverga joylash: [deploy/DEPLOY.md](deploy/DEPLOY.md) (Ubuntu + systemd).

## Sozlamalar (`.env`)

| O'zgaruvchi | Majburiy | Tavsif |
|---|---|---|
| `BOT_TOKEN` | ha | [@BotFather](https://t.me/BotFather) tokeni |
| `DATABASE_PATH` | yo'q | SQLite fayli (default `data/birthdays.db`) |
| `DEFAULT_GROUP_ID` | yo'q | Shaxsiy chatdan yozilgan buyruqlar shu guruhga tegishli bo'ladi |
| `NOTIFICATION_TIME` | yo'q | Default tabrik vaqti, `HH:MM` (default `08:00`); guruhda `/settings time` bilan o'zgartiriladi |
| `TIMEZONE` | yo'q | Vaqt mintaqasi (default `Asia/Tashkent`) |

## Buyruqlar

| Buyruq | Kim uchun | Tavsif |
|---|---|---|
| `/menu`, `/start` | admin | Shaxsiy chatda — tugmali menyu; guruhda — qo'shish tugmasi |
| `/help` | hamma | Yordam matni |
| `/list` | hamma | Saqlangan tug'ilgan kunlar (20 tadan sahifalab, ◀️ ▶️ tugmalari) |
| `/upcoming` | hamma | Yaqin kunlardagi tug'ilgan kunlar (default 7 kun) |
| `/find Ism` | hamma | Ism bo'yicha qidirish |
| `/settings` | hamma | Guruh sozlamalarini ko'rish |
| `/add Ism 15.03[.1998]` | admin | Tug'ilgan kun qo'shish (yil bilan — yosh hisoblanadi) |
| reply + `/add 15.03` | admin | Odam xabariga reply qilib qo'shish — tabrikda u belgilanadi (mention) |
| `/edit ID Ism 15.03.1998` | admin | Ism va sanani o'zgartirish (`/edit ID 15.03` — faqat sana) |
| `/remove ID` | admin | Yozuvni o'chirish |
| `/settings time 09:00` | admin | Guruh tabrik vaqti |
| `/settings remind 3` | admin | Tug'ilgan kunga 3 kun qolganda eslatma (`0` — o'chirish) |
| `/settings upcoming 14` | admin | `/upcoming` necha kunni ko'rsatadi |
| reply + `/setsticker` | admin | Stikerga reply qilib — tabrikdan keyin shu stiker yuboriladi (`/setsticker off`) |

`ID` ni `/list` dan oling. Shaxsiy chatda admin buyruqlari faqat
`DEFAULT_GROUP_ID` guruhining adminlari uchun ishlaydi.

29-fevralda tug'ilganlar kabisa bo'lmagan yillarda 28-fevralda tabriklanadi.
Tabrik va eslatma har bir odam uchun kuniga bir marta yuboriladi; bot
belgilangan vaqtdan keyin ishga tushsa, o'tkazib yuborilganlari darhol ketadi.

## Fayllar tuzilishi

```
birthdate-bot/
├── birthday_bot/
│   ├── __main__.py      # Kirish nuqtasi: python -m birthday_bot
│   ├── config.py        # .env dan sozlamalar
│   ├── database.py      # SQLite: sxema, migratsiyalar, so'rovlar
│   ├── models.py        # Birthday, Group, GroupSettings, Upcoming
│   ├── dates.py         # Sana/vaqt: validatsiya, 29-fevral, yosh
│   ├── parsing.py       # Buyruq argumentlari, ism/sana, /start payloadi
│   ├── texts.py         # Barcha xabar matnlari
│   ├── keyboards.py     # Menyu tugmalari va CallbackData
│   ├── permissions.py   # Guruhni aniqlash va admin tekshiruvi
│   ├── scheduler.py     # Har daqiqalik tekshiruv: tabrik va eslatma
│   └── handlers/        # buyruqlar (common, birthdays, settings) va menyu
│                        # (group_events, menu, add_flow, manage, settings_menu)
├── tests/               # pytest testlari
└── deploy/              # systemd xizmati va deploy qo'llanmasi
```

## Testlar

```bash
pip install -r requirements-dev.txt
pytest
```
