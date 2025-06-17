# 🎥 Django Video Quiz Application

An interactive Django web application where users watch videos, answer embedded quiz questions at specific timestamps, and earn certificates based on performance.

## 🚀 Features

- Admin can upload videos with embedded quiz questions
- Each video pauses to display questions at specified timestamps
- Users must watch videos in order and complete quizzes
- Final certificate is generated if total score exceeds 60%
- Credit points assigned based on performance
- Certificates are downloadable and include QR verification (optional)

## 🧰 Tech Stack

- Python 3.x
- Django 4.x
- SQLite / PostgreSQL
- HTML / CSS / JavaScript
- Bootstrap (optional for styling)
- AJAX (for quiz submission without page reload)

---

## 📦 Installation Guide

### 🔁 Clone the Repository

```bash
git clone https://github.com/yourusername/video-quiz-app.git
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

## 📁 Folder Structure

```
video-quiz-app/
│
├── quiz/                      # Main Django app
│   ├── models.py              # Models for Video, Question, Result
│   ├── views.py               # Logic for playback, scoring, certificate
│   ├── templates/quiz/        # HTML templates
│   └── static/quiz/           # JS, CSS, and image files
│
├── media/                     # Uploaded video and user media
├── static/                    # Project-wide static files
├── templates/                 # Base templates
├── users/                     # Optional custom user app
├── manage.py
├── requirements.txt
└── README.md
```

---

## 📜 Requirements.txt Example

```
Django>=4.0,<5.0
Pillow
qrcode
reportlab  # For certificate PDF generation
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

## 🧾 License

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.

---

## 🙋‍♂️ Author

- **Your Name** – [@yourgithub](https://github.com/yourgithub)

---

## 📣 Contributions

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

---

## 📌 Notes

- This project assumes videos are stored locally (e.g., `media/videos/`)
- Make sure to enable `MEDIA_URL` and `MEDIA_ROOT` in `settings.py`
- Add URL patterns to serve media in `urls.py` for development

```python
from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```