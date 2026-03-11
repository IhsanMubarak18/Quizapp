from django.shortcuts import render, redirect
from django.contrib.auth import get_user_model, login, logout, authenticate
from django.core.mail import send_mail
from .forms import EmailSignUpForm, OTPLoginForm
from .models import EmailOTP
import random

User = get_user_model()  # Use your CustomUser model

def send_otp_to_email(email):
    otp = str(random.randint(100000, 999999))
    EmailOTP.objects.create(email=email, otp=otp)
    send_mail(
        subject="Your OTP Code",
        message=f"Your OTP is: {otp}",
        from_email=None,  # Uses DEFAULT_FROM_EMAIL from settings.py
        recipient_list=[email],
        fail_silently=False,
    )

def signup_view(request):
    if request.method == 'POST':
        form = EmailSignUpForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            send_otp_to_email(email)
            request.session['signup_data'] = form.cleaned_data
            return redirect('users:verify_signup_otp')
    else:
        form = EmailSignUpForm()
    return render(request, 'users/signup.html', {'form': form})

def verify_signup_otp(request):
    if request.method == 'POST':
        otp = request.POST.get('otp')
        email = request.session.get('signup_data')['email']
        if EmailOTP.objects.filter(email=email, otp=otp).exists():
            data = request.session.get('signup_data')
            user = User.objects.create_user(
                #username=email,
                email=email,
                first_name=data['first_name'],
                last_name=data['last_name'],
            )
            login(request, user)
            # ✅ Delete OTP after successful use
            EmailOTP.objects.filter(email=email, otp=otp).delete()
            return redirect('video_app:video_list')
    return render(request, 'users/verify_otp.html')


def login_view(request):
    form = OTPLoginForm(request.POST or None)
    context = {'form': form, 'step': 'email'}

    if request.method == 'POST':
        if 'send_otp' in request.POST:
            email = form.data.get('email')
            if User.objects.filter(email=email).exists():
                send_otp_to_email(email)
                context.update({'otp_sent': True, 'step': 'otp', 'email': email})
            else:
                form.add_error('email', "You don’t have an account on this site.Sign up first!")
        
        elif 'verify_otp' in request.POST:
            email = form.data.get('email')
            otp = form.data.get('otp')
            context.update({'step': 'otp', 'email': email})
            if EmailOTP.objects.filter(email=email, otp=otp).exists():
                try:
                    user = User.objects.get(email=email)
                    login(request, user)
                    EmailOTP.objects.filter(email=email, otp=otp).delete()
                    return redirect('video_app:video_list')
                except User.DoesNotExist:
                    form.add_error('email', "No user found.")
            else:
                form.add_error('otp', "Invalid OTP.")
    
    return render(request, 'users/otp_login.html', context)




def logout_view(request):
    if request.method == 'POST':
        logout(request)
        return redirect('video_app:home')


def admin_login_view(request):
    """Password-based login for admin (staff) users only."""
    error = None
    if request.user.is_authenticated and request.user.is_staff:
        return redirect('video_app:admin_dashboard')

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
