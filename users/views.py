# users/views.py
import random
import string
from django.shortcuts import render, redirect
from django.contrib.auth import get_user_model, login, logout, authenticate
from django.core.mail import send_mail
from django.conf import settings
from .forms import StudentRegistrationForm, StudentLoginForm
from .models import StudentProfile

User = get_user_model()


def generate_password(length=10):
    """Generate a random alphanumeric password."""
    chars = string.ascii_letters + string.digits
    return ''.join(random.choices(chars, k=length))


def student_register(request):
    """Student self-registration: auto-generates a password and mails it."""
    if request.user.is_authenticated and not request.user.is_staff:
        return redirect('video_app:student_dashboard')

    form = StudentRegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        email = form.cleaned_data['email']
        student_name = form.cleaned_data['student_name']
        college_name = form.cleaned_data['college_name']
        mobile_number = form.cleaned_data['mobile_number']

        # Generate password
        raw_password = generate_password()

        # Create user
        user = User.objects.create_user(
            email=email,
            first_name=student_name,
            last_name='',
            password=raw_password,
        )

        # Create student profile
        StudentProfile.objects.create(
            user=user,
            student_name=student_name,
            college_name=college_name,
            mobile_number=mobile_number,
        )

        # Send password via email
        try:
            send_mail(
                subject="Your Quiz Portal Login Credentials",
                message=(
                    f"Hello {student_name},\n\n"
                    f"You have been registered successfully on the Online Quiz Portal.\n\n"
                    f"Your login credentials:\n"
                    f"  Email   : {email}\n"
                    f"  Password: {raw_password}\n\n"
                    f"Please log in at: http://127.0.0.1:8000/login/\n\n"
                    f"Regards,\nQuiz Portal Team"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=True,
            )
        except Exception:
            pass  # don't crash if email fails

        return render(request, 'users/register_success.html', {
            'email': email,
            'password': raw_password,
        })

    return render(request, 'users/signup.html', {'form': form})


def student_login(request):
    """Student login using email + auto-generated password."""
    if request.user.is_authenticated and not request.user.is_staff:
        return redirect('video_app:student_dashboard')

    form = StudentLoginForm(request.POST or None)
    error = None
    if request.method == 'POST' and form.is_valid():
        email = form.cleaned_data['email']
        password = form.cleaned_data['password']
        user = authenticate(request, username=email, password=password)
        if user is not None and not user.is_staff:
            login(request, user)
            return redirect('video_app:student_dashboard')
        else:
            error = "Invalid email or password."

    return render(request, 'users/student_login.html', {'form': form, 'error': error})


def logout_view(request):
    logout(request)
    return redirect('video_app:home')


def admin_login_view(request):
    """Password-based login for admin (staff) users only."""
    if request.user.is_authenticated and request.user.is_staff:
        return redirect('video_app:admin_dashboard')

    error = None
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=email, password=password)
        if user is not None and user.is_staff:
            login(request, user)
            return redirect('video_app:admin_dashboard')
        else:
            error = "Invalid credentials or you are not an admin."

    return render(request, 'users/admin_login.html', {'error': error})
