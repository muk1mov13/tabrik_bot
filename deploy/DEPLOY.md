# Ubuntu serverga joylash (systemd)

Quyidagi buyruqlar Ubuntu 22.04/24.04 uchun, `sudo` huquqli foydalanuvchidan
bajariladi. Alohida baza serveri kerak emas — ma'lumotlar SQLite faylida
(`/opt/birthdate-bot/data/birthdays.db`) saqlanadi.

## 1. Kerakli paketlar

```bash
sudo apt update
sudo apt install -y python3 python3-venv git sqlite3
```

Python 3.10 yoki undan yangi bo'lishi kerak (`python3 --version`).

## 2. Tizim foydalanuvchisi va kod

```bash
sudo useradd --system --no-create-home --home-dir /opt/birthdate-bot --shell /usr/sbin/nologin botuser
sudo mkdir -p /opt/birthdate-bot
sudo chown botuser:botuser /opt/birthdate-bot
sudo -u botuser git clone <REPO_URL> /opt/birthdate-bot
cd /opt/birthdate-bot
sudo -u botuser mkdir -p data
sudo -u botuser python3 -m venv venv
sudo -u botuser venv/bin/pip install -r requirements.txt
```

## 3. `.env` sozlash

```bash
sudo -u botuser cp .env.example .env
sudo -u botuser nano .env     # BOT_TOKEN ni yozing
sudo chmod 600 .env
```

## 4. Qo'lda sinab ko'rish (ixtiyoriy)

```bash
sudo -u botuser venv/bin/python -m birthday_bot
```

`Bot ishga tushdi` chiqsa — Ctrl+C bilan to'xtating va xizmat sifatida ishga tushiring.

## 5. systemd xizmati

```bash
sudo cp deploy/birthdate-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now birthdate-bot
sudo systemctl status birthdate-bot
```

Bot server qayta yonganda o'zi ishga tushadi va yiqilsa 5 soniyada qayta turadi.
Xizmat faqat `data/` papkaga yoza oladi (`ProtectSystem=strict`).

Loglar:

```bash
journalctl -u birthdate-bot -f
```

## 5.1. Bot rasmi va tavsifi

Tavsif ("What can this bot do?") va qisqa tavsifni bot har ishga tushganda o'zi
o'rnatadi (`texts.BOT_DESCRIPTION`, `texts.BOT_SHORT_DESCRIPTION`).

Rasmni Bot API orqali qo'yib bo'lmaydi — @BotFather da `/setuserpic` → botni
tanlang → `deploy/avatar.png` ni yuboring. Rasmni qayta chizish:
`python deploy/make_avatar.py` (Pillow kerak, serverda shart emas).

## 6. Yangilash

```bash
cd /opt/birthdate-bot
sudo -u botuser git pull
sudo -u botuser venv/bin/pip install -r requirements.txt
sudo systemctl restart birthdate-bot
```

Baza sxemasi o'zgargan bo'lsa, bot ishga tushganda uni o'zi yangilaydi.

## 7. Zaxira nusxa (backup)

Bot ishlab turganda ham xavfsiz nusxa olish (`sqlite3 .backup`). Har kuni
03:00 da, 14 kunlik nusxalar saqlanadi (`sudo crontab -u botuser -e`):

```cron
0 3 * * * sqlite3 /opt/birthdate-bot/data/birthdays.db ".backup /opt/birthdate-bot/data/backup-$(date +\%F).db" && find /opt/birthdate-bot/data -name 'backup-*.db' -mtime +14 -delete
```

Tiklash:

```bash
sudo systemctl stop birthdate-bot
sudo -u botuser cp data/backup-YYYY-MM-DD.db data/birthdays.db
sudo -u botuser rm -f data/birthdays.db-wal data/birthdays.db-shm
sudo systemctl start birthdate-bot
```

Nusxalarni boshqa joyga ham ko'chirib turing — server diski ishdan chiqsa, `data/` bilan birga yo'qoladi.
