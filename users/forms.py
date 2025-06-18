# users/forms.py
from django import forms
from django.contrib.auth import get_user_model


class EmailSignUpForm(forms.ModelForm):
    class Meta:
        model = get_user_model()
        fields = ['first_name', 'last_name', 'email']

    def clean_email(self):
        email = self.cleaned_data['email']
        if get_user_model().objects.filter(email=email).exists():
            raise forms.ValidationError("Email already exists.")
        return email


class OTPLoginForm(forms.Form):
    email = forms.EmailField()
    otp = forms.CharField(max_length=6, required=False)
