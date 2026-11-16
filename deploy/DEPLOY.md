# Ubuntu serverga joylash (Dockersiz, systemd)

Quyidagi buyruqlar Ubuntu 22.04/24.04 uchun, `sudo` huquqli foydalanuvchidan bajariladi.

## 1. Kerakli paketlar

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip postgresql git
```

## 2. PostgreSQL baza va foydalanuvchi

```bash
sudo -u postgres psql <<'SQL'
CREATE USER birthdate WITH PASSWORD 'KUCHLI_PAROL_YOZING';
CREATE DATABASE birthdate OWNER birthdate;
SQL
```

Postgres faqat `localhost` da tinglaydi (standart sozlama) — tashqi portni ochish shart emas.

## 3. Tizim foydalanuvchisi va kod

```bash
sudo useradd --system --no-create-home --home-dir /opt/birthdate-bot --shell /usr/sbin/nologin botuser
sudo mkdir -p /opt/birthdate-bot
sudo chown botuser:botuser /opt/birthdate-bot
sudo -u botuser git clone <REPO_URL> /opt/birthdate-bot
cd /opt/birthdate-bot
sudo -u botuser python3 -m venv venv
sudo -u botuser venv/bin/pip install -r requirements.txt
```

## 4. `.env` sozlash

```bash
sudo -u botuser cp .env.example .env
sudo -u botuser nano .env
sudo chmod 600 .env
```

`DATABASE_URL=postgresql://birthdate:KUCHLI_PAROL_YOZING@localhost:5432/birthdate`

## 5. systemd xizmati

```bash
sudo cp deploy/birthdate-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now birthdate-bot
sudo systemctl status birthdate-bot
```

Loglar:

```bash
journalctl -u birthdate-bot -f
```

Logda `Scheduler ishga tushdi` va `Bot ishga tushdi` chiqishi kerak.

## 6. Yangilash

```bash
cd /opt/birthdate-bot
sudo -u botuser git pull
sudo -u botuser venv/bin/pip install -r requirements.txt
sudo systemctl restart birthdate-bot
```

## 7. Zaxira nusxa (backup)

Har kuni 03:00 da bazani saqlash (`sudo crontab -u postgres -e`):

```cron
0 3 * * * pg_dump birthdate | gzip > /var/lib/postgresql/backup-birthdate-$(date +\%F).sql.gz && find /var/lib/postgresql -name 'backup-birthdate-*.sql.gz' -mtime +14 -delete
```

Tiklash:

```bash
gunzip -c backup-birthdate-YYYY-MM-DD.sql.gz | sudo -u postgres psql birthdate
```
