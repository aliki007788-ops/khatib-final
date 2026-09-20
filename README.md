# خطیب (Khatib) v5.0 — محصول نهایی

مربیگری سخنرانی فارسی + یادگیری گویش عراقی  
Backend: FastAPI Modular Monolith | PostgreSQL | Redis | AI | ZarinPal | Eitaa

---

## وضعیت فازها (نهایی)

| فاز | موضوع | وضعیت |
|-----|-------|-------|
| ۱ | Auth + Security + DB + Config | ✅ |
| ۲ | Billing (State Machine + Idempotency + ZarinPal) | ✅ |
| ۳ | AI Service (Retry / Fallback / Structured Output) | ✅ |
| ۴ | Speech (Text + Audio Upload + Transcription) | ✅ |
| ۵ | Worker (Job Queue Processor) | ✅ |
| ۶ | Chat (Iraqi Coach Conversations) | ✅ |
| ۷ | Eitaa Webhook (Secure) | ✅ |
| ۸ | Progress + Learning Engine | ✅ |
| ۹ | Admin API + Privacy | ✅ |
| ۱۰ | Observability + Docker + Health + Metrics | ✅ |

---

## API کامل

### Auth
- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/refresh`
- `POST /api/auth/logout`
- `GET  /api/auth/me`

### Billing
- `POST /api/billing/checkout`
- `GET  /api/billing/callback`
- `GET  /api/billing/demo-pay`
- `GET  /api/billing/subscription`
- `GET  /api/billing/history`

### Speech
- `POST /api/speech/text` — تحلیل متن
- `POST /api/speech/audio` — آپلود صوت + تحلیل
- `GET  /api/speech`
- `GET  /api/speech/{id}`
- `DELETE /api/speech/{id}`

### Chat
- `POST /api/chat/conversations`
- `GET  /api/chat/conversations`
- `GET  /api/chat/conversations/{id}`
- `POST /api/chat/conversations/{id}/messages`
- `DELETE /api/chat/conversations/{id}`

### Translate
- `POST /api/translate`

### Progress & Learning
- `GET /api/progress/summary`
- `GET /api/progress/trends`
- `GET /api/learning/levels`
- `GET /api/learning/levels/{id}/scenarios`
- `POST /api/learning/scenarios/{id}/start`
- `POST /api/learning/scenarios/{id}/complete`
- `GET /api/learning/daily-recommendation`

### Admin
- `GET /api/admin/stats`
- `GET /api/admin/users`
- `PATCH /api/admin/users/{id}/plan`
- `PATCH /api/admin/users/{id}/active`
- `GET /api/admin/transactions`
- `GET /api/admin/subscriptions`
- `GET /api/admin/audit`

### Privacy
- `GET /api/privacy/export`
- `POST /api/privacy/delete-account`

### Eitaa
- `POST /api/eitaa/webhook`
- `GET /api/eitaa/link-status`

### Health
- `GET /health/live`
- `GET /health/ready`
- `GET /metrics`

---

## راه‌اندازی سریع (Development)

```bash
# 1. Secretها
python scripts/generate_secrets.py

# 2. محیط
cp .env.example .env
# JWT_SECRET و PASSWORD_PEPPER را جایگزین کنید
# برای AI: AI_API_KEY را پر کنید

# 3. وابستگی‌ها
pip install -r requirements.txt

# 4. دیتابیس
mkdir -p data uploads
# جداول به صورت خودکار در حالت Dev ساخته می‌شوند
# یا: alembic upgrade head

# 5. Seed یادگیری (اختیاری)
python scripts/seed_learning_content.py

# 6. اجرا
uvicorn app.main:app --reload

# 7. Worker (ترمینال جدا)
python worker.py
```

## Production (Docker)

```bash
# .env را با مقادیر production پر کنید
# ENVIRONMENT=production
# DATABASE_URL=postgresql+psycopg://...
# PAYMENT_PROVIDER=zarinpal
# STORAGE_BACKEND=s3
# COOKIE_SECURE=true
# ...

docker compose up -d --build
```

---

## ساختار نهایی

```
khatib/
├── app/
│   ├── core/          config, db, models, security, plans, metrics, health, logging, ai_pricing
│   ├── middleware/    request_id, security_headers
│   ├── routers/       auth, billing, speech, chat, translate, progress, learning, admin, privacy, eitaa, health
│   ├── schemas/       auth, billing, speech, chat, progress, learning, admin, privacy, ai
│   ├── services/      billing, zarinpal, usage, ai*, speech, chat, storage, progress, learning, privacy, admin
│   └── main.py
├── worker.py
├── alembic/
├── scripts/
├── tests/
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

---

## ویژگی‌های کلیدی امنیتی و عملیاتی

- هیچ Secret پیش‌فرضی پذیرفته نمی‌شود
- Refresh Token Rotation + Reuse Detection
- Account Lockout + Rate Limiting
- Payment State Machine با `FOR UPDATE` و Idempotency
- Atomic Usage Counter
- Soft-delete + ناشناس‌سازی حساب
- Structured Logging + Request ID + Prometheus Metrics
- Production Guards سخت‌گیرانه
- Worker جداگانه برای پردازش صوت

---

**نسخه:** 5.0.0  
**وضعیت:** Production Candidate — آماده تست واقعی پرداخت، AI و Eitaa
