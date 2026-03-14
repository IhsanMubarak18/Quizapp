# users/forms.py
from django import forms
from django.contrib.auth import get_user_model
from .models import StudentProfile

User = get_user_model()


class StudentRegistrationForm(forms.Form):
    student_name = forms.CharField(max_length=200, label="Full Name")
    college_name = forms.CharField(max_length=300, label="College / Institution")
    mobile_number = forms.CharField(max_length=15, label="Mobile Number")
    email = forms.EmailField(label="Email ID")

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean_mobile_number(self):
        mobile = self.cleaned_data['mobile_number']
        if not mobile.isdigit():
            raise forms.ValidationError("Mobile number must contain only digits.")
        if len(mobile) < 10:
            raise forms.ValidationError("Enter a valid mobile number.")
        return mobile


class StudentLoginForm(forms.Form):
    email = forms.EmailField(label="Email ID")
    password = forms.CharField(widget=forms.PasswordInput, label="Password")
