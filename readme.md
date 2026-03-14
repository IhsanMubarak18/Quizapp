# 🎥 Django Video Quiz Application

An interactive Django web application where users watch videos, answer embedded quiz questions at specific timestamps, and earn certificates based on performance.

## 🚀 Features

- Admin can upload videos with embedded quiz questions
- Each video pauses to display questions at specified timestamps
- Users must watch videos in order and complete quizzes
- Final certificate is generated if total score exceeds 60%
- Credit points assigned based on performance
- Certificates are downloadable and include QR verification (optional)

---

## 📦 Installation Guide

### 🔁 Clone the Repository

```bash
git clone https://github.com/IhsanMubarak18/Quizapp.git
cd video-quiz-app
```

### 📦 Create Virtual Environment

```bash
python -m venv env
source env/bin/activate  # On Windows: env\Scripts\activate
```

### 📥 Install Requirements

```bash
pip install -r requirements.txt
```

### 🛠️ Run Migrations

```bash
python manage.py migrate
```

### 📂 Create Superuser (Admin)

```bash
python manage.py createsuperuser
```

### ▶️ Run Server

```bash
python manage.py runserver
```

Open your browser and go to `http://127.0.0.1:8000/`

### 🐳 Run with Docker

Build and start the app:

```bash
docker compose up --build
```

The container will automatically run migrations and collect static files before starting Django on `http://127.0.0.1:8000/`.

Useful commands:

```bash
docker compose up --build -d
docker compose exec web python manage.py createsuperuser
docker compose down
```

Notes:

- `docker-compose.yml` stores SQLite data in a named Docker volume at `/app/data/db.sqlite3`
- media uploads and collected static files are also persisted in named Docker volumes
- the compose setup reads environment variables from the project `.env` file

---

## 🧪 How It Works

1. Admin uploads videos and sets quiz questions with timestamps.
2. Users watch videos. The video pauses automatically to display quiz questions.
3. After answering all questions in all videos:
   - Score is calculated
   - If score ≥ 60%, a certificate is generated with credit points:
     - 60–69%: 3 credits
     - 70–79%: 4 credits
     - 80–90%: 5 credits
     - 91–100%: 6 credits
4. Users can download their certificate as a PDF (with optional QR code verification).

---

## 📜 Requirements.txt Example

```
asgiref==3.4.1
Brotli==1.1.0
cffi==1.15.1
cssselect2==0.4.1
Django==3.2
fonttools==4.27.1
html5lib==1.1
Pillow==8.4.0
pkg-resources==0.0.0
pycparser==2.21
pydyf==0.1.2
pyphen==0.11.0
pytz==2025.2
qrcode==7.3.1
reportlab==3.6.8
six==1.17.0
sqlparse==0.4.4
tinycss2==1.1.1
typing-extensions==4.1.1
weasyprint==54.3
webencodings==0.5.1
zopfli==0.1.9

```

> If you use a different certificate generator (e.g., manually rendering HTML to PDF), include its dependency here.

---

## 🧑‍💻 Admin Panel

Visit `http://127.0.0.1:8000/admin/` and log in using your superuser account to:
- Upload videos
- Add quiz questions
- Monitor user scores
- Manage users and certificates

---
