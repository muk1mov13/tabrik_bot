# 🎂 Tug'ilgan kun eslatuvchi Telegram bot

aiogram 3.x + APScheduler + PostgreSQL (asyncpg) asosida qurilgan bot. Guruhga
qo'shilgan odamlarning tug'ilgan kunlarini saqlaydi va har kuni ertalab
(default 08:00, Toshkent vaqti) tug'ilgan kuni bor odamni guruhga eslatib
turadi.

## O'rnatish

```bash
pip install -r requirements.txt
```

## Ishga tushirish

1. [@BotFather](https://t.me/BotFather) orqali yangi bot yarating va token oling.
2. Token va Postgres ulanish manzilini muhit o'zgaruvchilariga qo'ying:

```bash
export BOT_TOKEN="123456:ABC-DEF..."
export DATABASE_URL="postgresql://user:password@localhost:5432/dbname"
```

`birthdays` jadvali bot birinchi marta ishga tushganda avtomatik yaratiladi
(agar mavjud bo'lmasa) — qo'lda migration kerak emas.

3. Botni ishga tushiring:

```bash
python bot.py
```

4. Botni kerakli guruhga qo'shing va **admin** qiling (guruhga xabar
   yuborishi uchun admin bo'lishi shart emas, lekin xabarlar o'chib
   ketmasligi uchun tavsiya qilinadi).

## Buyruqlar

| Buyruq | Tavsif |
|---|---|
| `/start`, `/help` | Yordam matni |
| `/add Ism 15.03` | Tug'ilgan kun qo'shish (kun.oy) |
| `/add Ism 15.03.1998` | Yil bilan qo'shish (yosh avtomatik hisoblanadi) |
| `/list` | Guruhdagi barcha saqlangan tug'ilgan kunlar |
| `/upcoming` | Kelasi 7 kun ichidagi tug'ilgan kunlar |
| `/remove ID` | Yozuvni o'chirish (`ID` ni `/list` dan oling) |

## Fayllar tuzilishi

```
birthday-bot/
├── bot.py           # Asosiy kirish nuqtasi
├── database.py      # SQLite bilan ishlash
├── handlers.py       # /add, /list, /upcoming, /remove buyruqlari
├── scheduler.py      # Kunlik tekshiruv va xabar yuborish
└── requirements.txt
```

Ma'lumotlar `DATABASE_URL` orqali ko'rsatilgan PostgreSQL bazasida saqlanadi
(`birthdays` jadvali).

## Keyingi bosqichda qo'shsa bo'ladigan narsalar

- Bir necha kun oldin oldindan eslatma (masalan, 3 kun qolganda)
- `/upcoming` uchun kunlar sonini sozlash imkoniyati
- Guruh admin faqat o'chira oladigan qilib cheklash
- Rasmli/stikerli tabrik xabarlari
- Docker orqali deploy qilish (24/7 ishlashi uchun VPS yoki bepul hosting)
