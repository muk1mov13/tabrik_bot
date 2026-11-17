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

1. Botni guruhga qo'shing (oila, do'stlar, ishxona — istalgan) (admin qilish shart emas). Bot salomlashadi va
   **🎂 Tug'ilgan kun qo'shish** tugmasini yuboradi.
2. Tugmani bosing — botning shaxsiy chati ochiladi. Botni qo'shgan odam
   **boshqaruvchi** bo'ladi: unda **➕ Qo'shish**, **📋 Ro'yxat**, **⚙️ Sozlamalar** va
   **👥 Boshqaruvchilar** tugmalari bor. Bot ism va sanani so'raydi, odamni
   **👤 Telegram'dan tanlash** ham mumkin — shunda tabrikda u belgilanadi.
   Bir nechta odamni birdaniga qo'shish uchun ism o'rniga ro'yxat yuboring — har
   qatorga bittadan (`Adolatxon 27 may 2021`, `Usmonbek 29.11.2022`). Bot saqlashdan
   oldin hammasini ko'rsatadi, tushunilmagan qatorlar va takrorlarni aytadi.
3. Guruhning boshqa a'zolari ham tugmani bosib, **o'z** tug'ilgan kunini qo'sha oladi.
4. Tug'ilgan kun kelganda bot guruhda tabriklaydi — hamma xabardor bo'ladi.

Kim nima qila oladi:

| Rol | Kim | Nima qiladi |
|---|---|---|
| Admin | guruh egasi va adminlari | hammasi + boshqaruvchini olib tashlash |
| Boshqaruvchi | botni qo'shgan odam, admin tayinlagan yoki taklif havolasi bilan kelgan | hamma tug'ilgan kunlar, sozlamalar, yangi boshqaruvchini taklif qilish |
| A'zo | guruhning boshqa a'zolari | faqat o'z tug'ilgan kuni |

Keyinchalik shaxsiy chatda `/menu` yozish kifoya. Bir necha guruhda bo'lsangiz,
bot qaysi guruh bilan ishlashni so'raydi. Tugma ko'rinmay qolsa, guruhda `/menu`
yozing. Bot guruhga tabrik yubora olmasa (masalan, guruhda yozish cheklangan bo'lsa),
boshqaruvchilarga shaxsiy chatda kuniga bir marta xabar beradi.

Boshqaruvchilar uchun qulayliklar:

- **Menyu** — Telegram'dagi "Menu" tugmasi yoki `/menu`. Menyuning o'zida yaqin 3 ta
  tug'ilgan kun ko'rinadi.
- **Ertalabki xabar** — tabrikdan 1 soat oldin: bugun va ertaga kimning tug'ilgan kuni.
  Sozlamalarda har kim o'zi uchun o'chirib qo'yishi mumkin.
- **Ro'yxat** — 🔎 Qidirish (ismning bir qismi bo'yicha) va 📤 Yuklab olish (fayl,
  uni ➕ Qo'shish orqali qayta yuborsangiz ro'yxat tiklanadi).
- **Yozuv kartasi** — 👤 Telegram'dan belgilash: ro'yxat orqali qo'shilgan odamni
  keyin Telegram akkauntiga bog'lash, tabrikda u belgilanadi.
- **👥 Boshqaruvchilar** → 🔗 Taklif havolasi: bir martalik, 7 kun amal qiladi,
  faqat guruh a'zosida ishlaydi. Guruhda reply qilib `/manager` yozish ham mumkin.
- **⚙️ Sozlamalar** — ✍️ o'z tabrik matni (`{ism}` o'rniga ism qo'yiladi),
  👁 Ko'rish, 🎨 Stiker.

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
| `/menu`, `/start` | hamma | Shaxsiy chatda — rolga qarab tugmali menyu; guruhda — qo'shish tugmasi |
| reply + `/manager` | admin | Odamni boshqaruvchi qilish (`/manager off` — olib tashlash) |
| `/help` | hamma | Yordam matni |
| `/list` | hamma | Saqlangan tug'ilgan kunlar (20 tadan sahifalab, ◀️ ▶️ tugmalari) |
| `/upcoming` | hamma | Yaqin kunlardagi tug'ilgan kunlar (default 7 kun) |
| `/find Ism` | hamma | Ism bo'yicha qidirish |
| `/settings` | hamma | Guruh sozlamalarini ko'rish |
| `/add Ism 15.03[.1998]` | boshqaruvchi | Tug'ilgan kun qo'shish (yil bilan — yosh hisoblanadi) |
| reply + `/add 15.03` | boshqaruvchi | Odam xabariga reply qilib qo'shish — tabrikda u belgilanadi (mention) |
| `/edit` | boshqaruvchi | Ro'yxatdan tanlab ism va sanani o'zgartirish (yoki `/list` ostidagi ✏️ tugmasi) |
| `/remove` | boshqaruvchi | Ro'yxatdan tanlab o'chirish (yoki `/list` ostidagi 🗑 tugmasi) |
| `/settings time 09:00` | boshqaruvchi | Guruh tabrik vaqti |
| `/settings remind 3` | boshqaruvchi | Tug'ilgan kunga 3 kun qolganda eslatma (`0` — o'chirish) |
| `/settings upcoming 14` | boshqaruvchi | `/upcoming` necha kunni ko'rsatadi |
| reply + `/setsticker` | boshqaruvchi | Stikerga reply qilib — tabrikdan keyin shu stiker yuboriladi (`/setsticker off`) |

Shaxsiy chatda bu buyruqlar faqat
`DEFAULT_GROUP_ID` guruhining boshqaruvchilari uchun ishlaydi.

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
│                        # (group_events, menu, add_flow, manage, settings_menu, self_flow)
├── tests/               # pytest testlari
└── deploy/              # systemd xizmati va deploy qo'llanmasi
```

## Testlar

```bash
pip install -r requirements-dev.txt
pytest
```
