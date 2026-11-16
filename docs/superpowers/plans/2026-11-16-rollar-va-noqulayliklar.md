# Admin bo'lmaganlar uchun boshqaruv va noqulayliklarni tuzatish

## Context

Hozir tug'ilgan kunlarni faqat guruh adminlari boshqaradi. Oila guruhlarida botni
ko'pincha admin bo'lmagan qarindosh topib qo'shadi — u hech narsa qila olmaydi,
admin esa bot haqida bilmaydi. Foydalanuvchi tanlovi:

- **Botni guruhga qo'shgan odam avtomatik boshqaruvchi** bo'ladi; adminlar ham
  boshqaradi va boshqaruvchilarni tayinlaydi/olib tashlaydi.
- **Oddiy a'zo faqat o'z tug'ilgan kunini** qo'shadi/o'zgartiradi (tabrikda
  belgilanadi).
- Tabrik yuborilmasa boshqaruvchilarga xabar.
- Qo'shishda odamni Telegram'dan tanlab belgilash (mention).
- Guruh ID o'zgarganda eskirgan tugma to'g'ri ishlashi; takror yozuv haqida
  ogohlantirish.

Ish `feature/button-menu` branch'ida davom etadi (worktree
`D:\ENG_MUHIM_LOYIHALAR\LOYIHALAR\birthdate_bot-menu`, hali merge qilinmagan).
Diagnostika uchun qo'shilgan `permissions.is_admin` dagi INFO log commit
qilinmagan — rol modeliga o'tishda o'rniga yangi log keladi.

## Rollar

`permissions.py` ga yagona tekshiruv (bitta `get_chat_member` chaqiruvi):

```python
class Role(IntEnum):
    NONE = 0      # guruhda emas yoki tekshirib bo'lmadi
    MEMBER = 1    # faqat o'z yozuvi
    MANAGER = 2   # qo'shgan odam yoki admin tayinlagan
    ADMIN = 3     # creator/administrator + boshqaruvchilarni tayinlash

async def get_role(bot, db, group_id, user_id) -> Role
```

- creator/administrator → ADMIN; member yoki `restricted` (`is_member=True`) →
  `db.is_manager()` bo'lsa MANAGER, aks holda MEMBER; left/kicked/xato → NONE.
- Rad etilganda INFO log: guruh, user, status (diagnostika saqlanadi).
- `is_admin` o'rniga hamma joyda `get_role`. `editable_group_id(message, bot, db, config)`
  (yangi `db` parametri) `>= MANAGER` ni qabul qiladi — `/add`, `/edit`,
  `/remove`, `/settings`, `/setsticker` boshqaruvchilarga ham ochiladi
  (`handlers/birthdays.py`, `handlers/settings.py` dagi 5 ta chaqiruv).
- `handlers/ui.ensure_admin` → `ensure_role(event, bot, db, group_id, minimum)`;
  `Role` yoki `None` qaytaradi, ruxsat bo'lmasa alert/xabar va bog'lanishni o'chiradi.

## Baza — migratsiya 3 (`database.py` MIGRATIONS oxiriga)

```sql
ALTER TABLE group_admins RENAME TO group_links;  -- endi har qanday bog'langan foydalanuvchi
CREATE TABLE group_managers (
    group_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    added_by INTEGER,
    PRIMARY KEY (group_id, user_id)
);
```

Metodlar: `link_admin/unlink_admin/admin_groups` → `link_user/unlink_user/linked_groups`
(nomini o'zgartirish, chaqiruvchilarni yangilash); yangi `add_manager`,
`remove_manager`, `is_manager`, `list_managers(group_id)`,
`get_birthday_by_user(group_id, user_id)`, `find_same_name(group_id, name)`
(casefold, Python'da — `find_birthdays` kabi). `migrate_group` `group_links` va
`group_managers` ni ham ko'chiradi.

## O'zgarishlar

### 1. Qo'shgan odam boshqaruvchi (`handlers/group_events.py`)
- `on_bot_membership`: bot qo'shilganda `event.from_user` (bot bo'lmasa) →
  `add_manager` + `link_user`. Salomlashish matni qo'shgan odamni `mention()` bilan
  aytadi: "Meni X qo'shdi — u tug'ilgan kunlarni boshqaradi. Har kim o'z tug'ilgan
  kunini pastdagi tugma orqali qo'sha oladi." Tugma: "🎂 Tug'ilgan kun qo'shish".
- Guruhda `/manager` (admin, biror xabarga reply) → tayinlash;
  `/manager off` (reply) → olib tashlash. Admin bo'lmasa ⛔. Bot/o'zini emas.

### 2. Rolga qarab menyu (`handlers/menu.py`, `keyboards.py`, `texts.py`)
- `available_groups` → `(Group, Role)` juftliklari; NONE bo'lsa bog'lanish o'chadi.
- Deep link: MEMBER ham bog'lanadi (avval rad etilardi) va a'zo menyusini ko'radi.
- MANAGER/ADMIN: hozirgi menyu + "👥 Boshqaruvchilar" (ro'yxat; ADMIN uchun har
  birida 🗑, pastda "guruhda xabarga reply qilib /manager yozing" yo'riqnomasi).
- MEMBER menyusi: o'z yozuvi bo'lmasa [🎂 Tug'ilgan kunimni qo'shish], bo'lsa
  karta + [📅 Sanani o'zgartirish] [🗑 O'chirish]; ko'p guruh bo'lsa almashtirish.

### 3. A'zo o'zini qo'shadi (yangi `handlers/self_flow.py`)
- FSM: sana so'raladi → tasdiqlash → saqlash: `name=from_user.full_name[:MAX_NAME_LENGTH]`,
  `user_id=` o'zi, `added_by=` o'zi. Yozuvi bo'lsa — `update_birthday`.
- Har amalda `ensure_role(..., Role.MEMBER)` va yozuv `user_id == from_user.id`
  ekani tekshiriladi (boshqaning yozuviga tegib bo'lmaydi).
- `parse_date`, `add_preview`, `record_card` qayta ishlatiladi.

### 4. Telegram'dan tanlash (`handlers/add_flow.py`)
- Ism so'ralganda reply-klaviatura: [👤 Telegram'dan tanlash]
  (`KeyboardButtonRequestUsers(request_id=1, user_is_bot=False, max_quantity=1, request_name=True)`)
  va [❌ Bekor qilish] (matnli tugma). Ism yozish ham ishlaydi.
- `F.users_shared` handleri (`AddBirthday.name` holatida): `users[0]` dan
  `user_id` va `first_name + last_name` → ism; sana savoliga o'tadi.
- "❌ Bekor qilish" matni har qanday menyu holatida holatni tozalaydi va
  `ReplyKeyboardRemove` bilan menyuni ko'rsatadi; `TEXT_INPUT` uni o'tkazib yuboradi.
- Saqlashda `user_id` yoziladi → tabrikda belgilanadi.

### 5. Takror yozuv (`add_flow.py`, `self_flow.py`, `texts.add_preview`)
- Tasdiqlashdan oldin `find_same_name`; topilsa preview'ga
  "⚠️ Ro'yxatda allaqachon bor: Karim aka — 15 Mart. Baribir saqlaymizmi?".
  A'zo uchun: `user_id` siz bir xil ismli yozuv bo'lsa xuddi shu ogohlantirish.

### 6. Eskirgan tugma / guruh ID o'zgarishi (`permissions.py`, `menu.py`)
- `resolve_group(bot, db, group_id) -> Optional[int]`: `bot.get_chat`;
  `TelegramMigrateToChat` bo'lsa `db.migrate_group(old, exc.migrate_to_chat_id)` va
  yangi ID; boshqa `TelegramAPIError` → `None`.
- Deep link avval `resolve_group` dan o'tadi; `None` bo'lsa:
  "Bot bu guruhda topilmadi yoki guruh o'zgargan. Guruhda /menu yozing."
  (noto'g'ri "admin emas" o'rniga).

### 7. Tabrik ketmasa xabar (`scheduler.py`)
- `_send` → `Optional[str]` (None — muvaffaqiyat, aks holda xato matni).
- `check_and_notify(bot, db, current, failures: set | None = None)`; muvaffaqiyatsizlikda
  `(group_id, on_date)` `failures` da bo'lmasa — qo'shiladi va guruhning
  `list_managers` ∪ `linked_groups` foydalanuvchilaridan `get_role >= MANAGER`
  bo'lganlarga shaxsiy xabar: "⚠️ «test» guruhiga tabrik yubora olmadim (sabab).
  Botga guruhda yozish ruxsatini bering." Kuniga bir marta (xabar yuborilmasa jim).
- `setup_scheduler` bitta `set()` yaratib `kwargs` orqali uzatadi (global emas).

## Bosqichlar (har biri TDD, alohida commit)

1. Migratsiya 3 + DB metodlari + nom o'zgarishi (`tests/test_database.py`).
2. `Role`/`get_role`/`resolve_group`, `ensure_role`, `editable_group_id(db)`
   (`tests/test_permissions.py`; mavjud handler testlari o'tishi kerak).
3. Qo'shgan odam boshqaruvchi + `/manager` (`tests/test_handlers.py`).
4. Rolga qarab menyu + boshqaruvchilar ro'yxati.
5. `self_flow.py` — a'zo o'zini qo'shadi.
6. Telegram'dan tanlash + reply-klaviaturali bekor qilish.
7. Takror yozuv ogohlantirishi.
8. Eskirgan tugma (migratsiya) holati.
9. Tabrik ketmasa xabar (`tests/test_scheduler.py`).
10. README, CLAUDE.md, HELP_TEXT yangilash.

Batafsil qadamlar `docs/superpowers/plans/` ga yangi reja fayli sifatida yoziladi
(avvalgi kabi), keyin shu sessiyada bajariladi.

## Test yordamchilari (`tests/test_handlers.py`)
- `MockSession.GetChatMember`: ADMIN=1 → owner, MEMBER=2 → member, yangi
  `OUTSIDER=3` → `ChatMemberLeft`.
- `GetChat` uchun `migrated` guruh ID'sida `TelegramMigrateToChat` tashlash.
- `membership_update(..., by=user_id)` — kim qo'shganini berish.
- `users_shared` xabarini yasovchi yordamchi.

## Verification
- `pytest` — barcha testlar (hozir 97) yashil.
- Asosiy ssenariylar testda: a'zo botni qo'shadi → boshqaruvchi → menyu va qo'shish;
  boshqa a'zo deep link → faqat o'z sanasi; a'zo soxta callback bilan boshqaning
  yozuvini o'chira olmaydi; admin `/manager` reply bilan tayinlaydi/olib tashlaydi;
  guruhdan chiqqan boshqaruvchi rad etiladi; `users_shared` → yozuvda `user_id`;
  migratsiya qilingan guruh ID'si bilan deep link yangi ID'ga o'tadi;
  yuborib bo'lmagan tabrik → boshqaruvchiga bitta DM, keyingi daqiqada takror yo'q.
- Jonli: botni qayta ishga tushirish (worktree, asosiy baza — avval nusxa), Telegram'da
  "test" guruhida: botni chiqarib admin bo'lmagan akkauntdan qo'shish, a'zo sifatida
  o'zini qo'shish, "👤 Telegram'dan tanlash", guruhda yozishni cheklab tabrik
  xatosi DM'ini ko'rish.

## Qamrovdan tashqari (alohida tavsiya)
- Botni serverga joylash (`deploy/DEPLOY.md`) — kompyuter o'chsa tabrik ketmaydi.
- Bot nomidagi "Tu'gilgan" xatosi — @BotFather `/setname`.
- Guruh bo'yicha alohida vaqt mintaqasi.
