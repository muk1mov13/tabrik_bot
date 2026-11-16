# Boshqaruvchilar uchun qulayliklar

## Context

Rollar, a'zo o'zini qo'shishi, Telegram'dan tanlash va ro'yxatni birdaniga
qo'shish tayyor (`feature/button-menu`, worktree
`D:\ENG_MUHIM_LOYIHALAR\LOYIHALAR\birthdate_bot-menu`, 131 test, hali merge
qilinmagan). Endi admin va boshqaruvchilarning kundalik ishini osonlashtiramiz.
Hozirgi og'riqlar: menyuga kirish uchun `/menu` ni eslab qolish kerak va
"/" ro'yxatida buyruqlar yo'q; boshqaruvchi bugun/ertaga kim tug'ilganini
bilmaydi; katta ro'yxatda odamni topish qiyin; boshqaruvchi tayinlash faqat
guruhda reply + `/manager`; ro'yxat orqali qo'shilganlar keyin belgilanmaydi;
tabrik matni hamma joyda bir xil; zaxira nusxa olib bo'lmaydi.

Foydalanuvchi tanlovi: tez kirish, ertalabki xabar (tabrikdan 1 soat oldin),
qidirish, havola orqali tayinlash (admin **va** boshqaruvchi yaratadi),
keyin belgilash, o'z tabrik matni (+ ko'rish, stiker menyu orqali),
ro'yxatni yuklab olish.

## Baza — migratsiya 4 (`database.py` MIGRATIONS oxiriga)

```sql
ALTER TABLE groups ADD COLUMN last_digest TEXT;               -- ertalabki xabar yuborilgan sana
ALTER TABLE group_links ADD COLUMN digest INTEGER NOT NULL DEFAULT 1;  -- foydalanuvchi o'chirib qo'ya oladi
ALTER TABLE group_settings ADD COLUMN greeting_template TEXT; -- NULL — standart tabriklar
CREATE TABLE manager_invites (
    token TEXT PRIMARY KEY,
    group_id INTEGER NOT NULL,
    created_by INTEGER,
    created_at TEXT NOT NULL,   -- ISO sana
    used_by INTEGER
);
```

Yangi metodlar: `set_birthday_user(group_id, id, user_id)`,
`create_invite(group_id, created_by, today) -> token` (`secrets.token_urlsafe(9)`),
`use_invite(token, user_id, today) -> Optional[(group_id, created_by)]`
(mavjud, ishlatilmagan, 7 kundan eski emas — aks holda None; atomik UPDATE),
`get_digest_enabled/set_digest_enabled(user_id, group_id)`,
`mark_digest_sent(group_id, date)` va `get_digest_due(date, at) -> list[Group]`
(faol, `last_digest != date`, `COALESCE(notify_time, default) - 60 daqiqa <= at`).
`GroupSettings.greeting_template: Optional[str] = None`, `SETTING_FIELDS` ga qo'shiladi.
`migrate_group` `manager_invites` ni ham ko'chiradi.

## O'zgarishlar

### 1. Tez kirish
- Yangi `birthday_bot/commands.py`: `set_bot_commands(bot)` —
  `BotCommandScopeAllPrivateChats`: `menu`, `help`;
  `BotCommandScopeAllGroupChats`: `upcoming`, `list`, `find`, `menu`, `help`
  (o'zbekcha tavsif). `__main__.py` da polling'dan oldin; `TelegramAPIError`
  logga yoziladi, bot to'xtamaydi. Telegram'ning "Menu" tugmasi shu ro'yxatni ochadi.
- Boshqaruvchi menyusi matnida yaqin 30 kundagi 3 ta tug'ilgan kun
  (`db.get_upcoming(..., 30)[:3]` + mavjud `upcoming_line`): `menu_text(title, upcoming)`
  (`texts.py`, `handlers/menu.py: main_menu_view`).

### 2. Ertalabki xabar (`scheduler.py`)
- `check_and_notify` boshida `db.get_digest_due(on_date, at)`: har guruh uchun
  bugungi va ertangi tug'ilgan kunlar (`get_upcoming(group, today, 1)`).
  Bo'lsa — qabul qiluvchilarga xabar: "☀️ «Oila»: bugun — Karim aka (56 yosh),
  tabrik 08:00 da guruhga ketadi. Ertaga — Ali." Bo'sh bo'lsa xabar yo'q.
  Har holda `mark_digest_sent` (kuniga bir marta, restartda ham).
- Qabul qiluvchilar: `_report_failure` dagi ro'yxat (boshqaruvchilar ∪ bog'langan
  adminlar) umumiy `_manager_recipients(bot, db, group_id)` ga ajratiladi; digest
  uchun `digest` o'chirilganlar chiqariladi.
- Sozlamalar menyusida shaxsiy "🔔 Ertalabki xabar: yoqilgan/o'chirilgan" tugmasi
  (`ToggleDigest` CallbackData, `settings_menu.py`).

### 3. Qidirish (`handlers/manage.py`)
- Ro'yxat ostida [🔎 Qidirish] [📤 Yuklab olish]. Qidirish → `ManageSearch.query`
  holati → mavjud `db.find_birthdays` → natijalar yozuv tugmalari sifatida
  (`records_keyboard` qayta ishlatiladi, sahifasiz, 20 tagacha) + [🏠 Menyu].
  Topilmasa: "«x» bo'yicha hech kim topilmadi" + qayta qidirish.

### 4. Ro'yxatni yuklab olish (`manage.py`, `texts.py`)
- `export_text(birthdays)`: har qatorda `Ism 27 may 2021` — `parse_bulk` qayta
  o'qiy oladigan format (oy nomi kichik harf). `bot.send_document` +
  `BufferedInputFile(..., filename="tugilgan_kunlar.txt")`, izoh: "Shu faylni
  ➕ Qo'shish orqali qayta yuborsangiz — tiklanadi."

### 5. Havola orqali boshqaruvchi (`menu.py`, `parsing.py`, `keyboards.py`)
- "👥 Boshqaruvchilar" ekranida (MANAGER va ADMIN) [🔗 Taklif havolasi] →
  `create_invite` → `https://t.me/<bot>?start=m_<token>` matn sifatida (nusxalash
  uchun `<code>`) + "bir martalik, 7 kun".
- `parse_invite_payload("m_<token>")`; `cmd_start_link` `g_`/`m_` ni ajratadi.
  Qabul: `use_invite` None → "Havola eskirgan yoki ishlatilgan"; foydalanuvchi
  guruh a'zosi emas (`get_role == NONE`) → `NOT_IN_GROUP_TEXT` (havola ishlatilmaydi —
  `use_invite` rol tekshiruvidan keyin); allaqachon MANAGER/ADMIN → menyu;
  aks holda `add_manager(added_by=created_by)`, `link_user`, menyu va taklif
  qilganga DM: "✅ X endi boshqaruvchi".
- Olib tashlash avvalgidek faqat ADMIN.

### 6. Keyin belgilash (`manage.py`)
- Yozuv kartasida "👤 Telegram'dan belgilash" (`RecordAction(action="link")`) →
  `EditBirthday.user` holati, karta matni yo'riqnomaga almashadi va
  `pick_user_keyboard(request_id=PICK_LINK_REQUEST)` (mavjud funksiyaga
  `request_id` parametri) yuboriladi; `pick_keyboard=True` — bekor qilinganda
  `menu.cb_home` klaviaturani yopadi.
- `F.users_shared.request_id == PICK_LINK_REQUEST` → shu odam boshqa yozuvga
  bog'langan bo'lsa rad ("… allaqachon «Ali» yozuviga bog'langan");
  aks holda `set_birthday_user`, `ReplyKeyboardRemove` bilan "👤 Bog'landi" + karta.

### 7. O'z tabrik matni, ko'rish, stiker (`settings_menu.py`, `texts.py`, `parsing.py`)
- Sozlamalarda [✍️ Tabrik matni] [👁 Ko'rish] [🎨 Stiker].
- Tabrik matni: `SettingsInput.greeting` holati; `parse_greeting_template`:
  `{ism}` bo'lishi shart, 500 belgigacha. Saqlanadi `greeting_template`.
  [↩️ Standart matn] — `None`.
- `texts.greeting(b, on_date, rng, template=None)`: template bo'lsa
  `escape(template).replace("{ism}", "<b>mention</b>")`, aks holda `GREETINGS`;
  yil bo'lsa yosh qatori ikkalasida ham qo'shiladi. Scheduler tabrikdan oldin
  `db.get_settings(group).greeting_template` ni oladi (DB so'rovi o'zgarmaydi).
- Ko'rish: namunaviy odam ("Karim aka", 1980) bilan tabrik matni shaxsiy chatga.
- Stiker: `SettingsInput.sticker` holati, `F.sticker` → `set_setting("sticker_file_id")`;
  [🗑 Stikerni o'chirish]. `/setsticker` buyrug'i qoladi.

## Bosqichlar (har biri TDD, alohida commit)

1. Migratsiya 4 + DB metodlari (`tests/test_database.py`).
2. Bot buyruqlari ro'yxati + menyudagi yaqin tug'ilgan kunlar.
3. Qidirish + yuklab olish.
4. Keyin belgilash.
5. Taklif havolasi.
6. O'z tabrik matni, ko'rish, stiker.
7. Ertalabki xabar + shaxsiy yoqish/o'chirish.
8. HELP_TEXT, README, CLAUDE.md.

## Test yordamchilari (`tests/test_handlers.py`)
- `MockSession`: `SetMyCommands` → True, `SendDocument` → `Message`
  (`requests` dan fayl mazmunini tekshirish).
- `users_shared` yordamchisi `request_id` ni qabul qiladi.
- `tests/test_scheduler.py` `FakeBot` mavjud; digest uchun vaqt bo'yicha testlar.

## Verification
- `pytest` — hammasi yashil (hozir 131).
- Asosiy ssenariylar: menyu matnida yaqin 3 ta odam; qidirish topadi/topmaydi;
  yuklab olingan fayl `parse_bulk` bilan aynan o'sha yozuvlarga qaytadi;
  kartadan belgilash `user_id` qo'yadi, band odam rad etiladi; taklif havolasi
  bir martalik, eskirgani va guruhdan tashqaridagi odam rad etiladi, taklif
  qilganga DM; o'z matni `{ism}` siz qabul qilinmaydi, tabrik va ko'rishda
  ishlatiladi; digest tabrikdan 60 daqiqa oldin bir marta, o'chirgan
  boshqaruvchiga kelmaydi, bo'sh kunda kelmaydi.
- Jonli: bazadan nusxa olib botni qayta ishga tushirish (worktree); Telegram'da
  "/" menyusi, taklif havolasini boshqa akkauntga yuborish, tabrik matnini
  o'zgartirib "👁 Ko'rish", fayl yuklab olib qayta yuborish.

## Qamrovdan tashqari
- A'zolardan so'rash xabari (tanlanmadi).
- Doimiy "🏠 Menyu" reply-klaviaturasi — Telegram'ning "Menu" tugmasi va buyruqlar
  ro'yxati yetarli; reply-klaviatura "Telegram'dan tanlash" bilan to'qnashadi.
- Botni serverga joylash — alohida tavsiya.
