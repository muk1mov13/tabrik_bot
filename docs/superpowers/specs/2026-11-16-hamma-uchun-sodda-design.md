# Botni hamma uchun sodda qilish — dizayn

Sana: 2026-11-16

## Maqsad

Har qanday oila (qarindoshlar) guruhi botni qo'shib, buyruq yodlamasdan
tug'ilgan kunlarni kiritishi mumkin bo'lsin. Bot tug'ilgan kuni bor odamni
guruhda tabriklaydi (mavjud mexanizm), shunda hamma xabardor bo'ladi.

## Qarorlar

- Tug'ilgan kunlarni **faqat guruh adminlari** qo'shadi/o'zgartiradi
  (hozirgidek). Oddiy a'zolar `/list`, `/upcoming`, `/find` dan foydalanadi.
- Qo'shish, ro'yxat (tahrirlash/o'chirish) va sozlamalar — **tugmalar va
  savol-javob** orqali, **botning shaxsiy chatida**.
- Admin–guruh bog'lanishi guruhdagi deep-link tugma orqali o'rnatiladi va
  bazada eslab qolinadi (yondashuv A).
- Bot bir vaqtda ko'p guruhga xizmat qiladi. `DEFAULT_GROUP_ID` ixtiyoriy
  bo'lib qoladi va eski buyruqlar uchun avvalgidek ishlaydi.
- Eski buyruqlar (`/add`, `/edit`, `/remove`, `/settings`, `/setsticker`)
  o'zgarmaydi. Stiker faqat `/setsticker` orqali o'rnatiladi.

## Foydalanuvchi jarayoni

### Guruhda

1. Bot guruhga qo'shilganda salomlashadi:
   "Salom! Men shu guruhdagilarning tug'ilgan kunini eslab, o'z vaqtida
   tabriklayman 🎉" + URL tugma **[➕ Tug'ilgan kun qo'shish]** →
   `https://t.me/<bot_username>?start=g_<group_id>`.
2. Guruhda `/menu` (va guruhdagi `/start`) — xuddi shu xabar va tugmani qayta
   chiqaradi. Guruhdagi `/help` avvalgidek `HELP_TEXT` ni ko'rsatadi.

### Shaxsiy chatda (admin)

- `/start g_<id>`: bot `is_admin` ni tekshiradi. Admin bo'lsa —
  `group_admins` ga bog'lanish yoziladi, guruh tanlangan guruh bo'ladi va
  asosiy menyu chiqadi. Admin bo'lmasa: "Qo'shish faqat guruh adminlariga
  ruxsat etilgan. Tug'ilgan kuningizni qo'shishni admindan so'rang 🙂".
  Payload noto'g'ri bo'lsa (`g_` dan keyin butun son emas) — oddiy `/start`
  kabi.
- `/start` (payloadsiz) yoki `/menu` shaxsiy chatda: adminning bog'langan
  guruhlari olinadi (har biri `is_admin` bilan tekshiriladi, admin bo'lmaganlari
  bog'lanishdan o'chiriladi).
  - 0 ta: qisqa yo'riqnoma — "Botni oila guruhingizga qo'shing va guruhdagi
    ➕ tugmasini bosing" + `HELP_TEXT`.
  - 1 ta: avtomatik tanlanadi, asosiy menyu.
  - bir nechta: guruh tanlash tugmalari.
- **Asosiy menyu:** `🏠 <guruh nomi>` + **[➕ Qo'shish] [📋 Ro'yxat]
  [⚙️ Sozlamalar]**, bir nechta guruh bo'lsa **[🔄 Guruhni almashtirish]**.
- **Qo'shish:** "Kimning tug'ilgan kuni? Ismini yozing" → ism →
  "Sanasi? (masalan 15.03 yoki 15.03.1980)" → sana → "Karim aka — 15 Mart 1980"
  **[✅ Saqlash] [❌ Bekor qilish]**. Har bir savolda **[❌ Bekor qilish]**
  tugmasi bor. Xato ism (bo'sh yoki `MAX_NAME_LENGTH` dan uzun) yoki xato
  sana — sababi aytilib, shu savol qayta so'raladi. Saqlangach: "✅ Qo'shildi"
  + **[➕ Yana qo'shish] [🏠 Menyu]**. `user_id` bog'lanmaydi
  (`added_by` = admin).
- **Ro'yxat:** har bir yozuv bitta tugma (`Ism — 15 Mart`), sahifasi 10 ta,
  **[⬅️] [➡️]** va **[🏠 Menyu]**. Bo'sh bo'lsa: "Hali hech kim qo'shilmagan"
  + **[➕ Qo'shish]**.
- **Yozuv kartasi:** ism, sana, (yil bo'lsa) yosh + **[✏️ Ismni o'zgartirish]
  [📅 Sanani o'zgartirish] [🗑 O'chirish] [⬅️ Orqaga]**.
  - Ismni o'zgartirish: yangi ism so'raladi → saqlanadi → karta.
  - Sanani o'zgartirish: yangi sana so'raladi (yil ixtiyoriy) → saqlanadi →
    karta.
  - O'chirish: "<Ism> rostdan o'chirilsinmi?" **[Ha, o'chirish] [Yo'q]**.
- **Sozlamalar:** joriy qiymatlar + tabrik vaqti **[07:00] [08:00] [09:00]
  [10:00] [12:00] [✍️ Boshqa vaqt]** (qo'lda `HH:MM`), eslatma **[O'chiq]
  [1 kun] [3 kun] [7 kun]**, **[🏠 Menyu]**. Tanlangan qiymat ✅ bilan
  belgilanadi.

## Texnik tuzilish

### Baza — `MIGRATIONS` ga 2-skript qo'shiladi

```sql
CREATE TABLE groups (
    group_id INTEGER PRIMARY KEY,
    title TEXT NOT NULL DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE group_admins (
    user_id INTEGER NOT NULL,
    group_id INTEGER NOT NULL,
    PRIMARY KEY (user_id, group_id)
);
```

Yangi `Database` metodlari: `upsert_group(group_id, title)`,
`set_group_active(group_id, active)`, `get_group(group_id)`,
`link_admin(user_id, group_id)`, `unlink_admin(user_id, group_id)`,
`admin_groups(user_id)` (faqat faol guruhlar, `Group` modellari).
`migrate_group` `groups` va `group_admins` jadvallarini ham ko'chiradi.
`models.py` ga `Group(group_id, title, active)` frozen dataclass qo'shiladi.

Scheduler nofaol guruhlarni (`groups.active = 0`) o'tkazib yuboradi.
`groups` da yozuvi bo'lmagan guruhlar (migratsiyadan oldingi) faol deb
hisoblanadi.

### Guruhlarni ro'yxatga olish

- `my_chat_member`: bot `member`/`administrator` bo'lsa — `upsert_group`,
  `active=1`, salomlashish xabari (faqat avval a'zo bo'lmagan holatdan
  o'tganda). `left`/`kicked` — `active=0`.
- Guruhdagi `/menu`/`/start` ham `upsert_group` qiladi (bu yangilanishdan
  oldin qo'shilgan guruhlar uchun). Boshqa buyruqlar guruhni ro'yxatga
  olmaydi.
- Deep link'dagi guruh bazada bo'lmasa, lekin `is_admin` muvaffaqiyatli
  o'tsa — `bot.get_chat` dan nom olinib `upsert_group` qilinadi.

### Fayllar

- `birthday_bot/keyboards.py` — `CallbackData` klasslari va tugma
  yasovchi toza funksiyalar.
- `handlers/group_events.py` — `my_chat_member`, guruhdagi `/menu`/`/start`.
- `handlers/menu.py` — shaxsiy chatdagi `/start [g_<id>]`, `/menu`, asosiy
  menyu, guruh tanlash/almashtirish.
- `handlers/add_flow.py` — qo'shish FSM.
- `handlers/manage.py` — ro'yxat, karta, tahrirlash FSM, o'chirish.
- `handlers/settings_menu.py` — sozlamalar tugmalari va "boshqa vaqt" FSM.
- `permissions.py` — `is_admin(bot, group_id, user_id) -> bool` ajratiladi,
  `editable_group_id` undan foydalanadi (xatti-harakati o'zgarmaydi).
- `texts.py` — barcha yangi matnlar.
- `handlers/__init__.py` — routerlar tartibi: `group_events`, `menu`,
  `common`, `birthdays`, `settings`, keyin FSM matnini ushlovchi `add_flow`,
  `manage`, `settings_menu`. Mavjud `/start`/`/help` handleri
  shaxsiy chatdagi `/start` uchun `menu` ga, guruhdagi `/start` uchun
  `group_events` ga o'tadi; `/help` `common` da qoladi.

### Holat (FSM)

aiogram `MemoryStorage` (Dispatcher standarti). Holatlar:
`AddBirthday.name`, `AddBirthday.date`, `AddBirthday.confirm`,
`EditBirthday.name`, `EditBirthday.date`, `SettingsInput.time`.
FSM ma'lumotida: `group_id` (tanlangan guruh), kerak bo'lsa `record_id`,
`name`, `day`, `month`, `year`. Holatdagi matn handlerlari buyruqlarni
(`/` bilan boshlanuvchi) ushlamaydi; holatda turib buyruq yozilsa holat
tozalanadi va buyruq odatdagidek ishlaydi.

Tanlangan guruh yo'q bo'lsa (masalan restartdan keyin) `menu` qoidasi
qo'llanadi: 1 ta guruh — avtomatik, ko'p — tanlash.

### Ruxsat va xavfsizlik

- Har bir callback va FSM qadamida (saqlashdan oldin) `is_admin` qayta
  tekshiriladi; callback ma'lumotidagi `group_id` ga ishonilmaydi.
  Ruxsat yo'q bo'lsa — rad xabari, holat tozalanadi, bog'lanish o'chiriladi.
- Yozuv ID'si bilan ishlaganda har doim `group_id` bilan birga olinadi
  (boshqa guruh yozuviga tegib bo'lmaydi).
- Foydalanuvchi matni `mention()`/`escape()` orqali o'tadi.

### Xatolar

- Eskirgan tugma (yozuv o'chirilgan, guruh topilmadi, holat yo'q):
  callback `answer` qilinadi ("Menyu eskirgan") va yangi asosiy menyu
  chiqariladi.
- `TelegramBadRequest` "message is not modified" — e'tiborsiz qoldiriladi.
- `is_admin` dagi `TelegramAPIError` — ruxsat yo'q deb hisoblanadi (hozirgidek).

## Testlar

- `tests/test_keyboards.py` — tugmalar tarkibi, sahifalash chegaralari.
- `tests/test_database.py` — yangi metodlar, migratsiya 2, `migrate_group`
  yangi jadvallar bilan, scheduler nofaol guruhni o'tkazishi.
- `tests/test_handlers.py` — `MockSession` `my_chat_member` update'lari va
  callback query (`AnswerCallbackQuery`, `EditMessageText`) bilan
  kengaytiriladi. Ssenariylar: salomlashish; admin deep link → menyu;
  admin bo'lmagan deep link → rad; to'liq qo'shish jarayoni; xato sana qayta
  so'raladi; bekor qilish; o'chirish tasdiqlash bilan; sozlama tugmasi
  saqlanadi; soxta `group_id` li callback rad etiladi.
- Mavjud testlar o'zgarishsiz o'tadi.

## Qamrovdan tashqari

- Oddiy a'zolarning o'z tug'ilgan kunini qo'shishi.
- Telegram foydalanuvchisini (`user_id`) tugmalar orqali bog'lash — reply
  bilan `/add` orqali avvalgidek mumkin.
- Stikerni tugmalar orqali o'rnatish.
- FSM holatini restartdan keyin saqlash.
