# users/forms.py
from django import forms
from django.contrib.auth import get_user_model
from .models import StudentProfile

User = get_user_model()


class StudentRegistrationForm(forms.Form):
    student_name = forms.CharField(max_length=200, label="Full Name")
    college_name = forms.CharField(max_length=300, label="College Name")
    qualification = forms.ChoiceField(choices=[
        ('SSLC', 'SSLC'),
        ('Plus Two', 'Plus Two'),
        ('Degree', 'Degree'),
        ('Others', 'Others')
    ], label="Qualification")
    qualification_other = forms.CharField(max_length=200, label="Other Qualification", required=False)
    district = forms.ChoiceField(choices=[
        ('Thiruvananthapuram', 'Thiruvananthapuram'),
        ('Kollam', 'Kollam'),
        ('Pathanamthitta', 'Pathanamthitta'),
        ('Alappuzha', 'Alappuzha'),
        ('Kottayam', 'Kottayam'),
        ('Idukki', 'Idukki'),
        ('Ernakulam', 'Ernakulam'),
        ('Thrissur', 'Thrissur'),
        ('Palakkad', 'Palakkad'),
        ('Malappuram', 'Malappuram'),
        ('Kozhikode', 'Kozhikode'),
        ('Wayanad', 'Wayanad'),
        ('Kannur', 'Kannur'),
        ('Kasaragod', 'Kasaragod'),
        ('Others', 'Others')
    ], label="District")
    district_other = forms.CharField(max_length=200, label="Other District", required=False)
    mobile_number = forms.CharField(max_length=15, label="Mobile Number")
    email = forms.EmailField(label="Email ID")

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists. Please log in instead.")
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


class AdminUserBaseForm(forms.ModelForm):
    can_manage_admins = forms.BooleanField(
        required=False,
        label="Can manage other admins",
        help_text="Enable full admin management access for this account.",
    )

    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'is_active']
        widgets = {
            'email': forms.EmailInput(attrs={'placeholder': 'admin@example.com'}),
            'first_name': forms.TextInput(attrs={'placeholder': 'First name'}),
            'last_name': forms.TextInput(attrs={'placeholder': 'Last name (optional)'}),
        }
        labels = {
            'is_active': 'Active account',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['last_name'].required = False
        self.fields['is_active'].required = False
        if self.instance and self.instance.pk:
            self.fields['can_manage_admins'].initial = self.instance.is_superuser

    def clean_email(self):
        email = self.cleaned_data['email']
        existing = User.objects.filter(email__iexact=email)
        if self.instance and self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_staff = True
        user.is_superuser = self.cleaned_data.get('can_manage_admins', False)
        if commit:
            user.save()
        return user


class AdminUserCreationForm(AdminUserBaseForm):
    password1 = forms.CharField(widget=forms.PasswordInput, label="Password")
    password2 = forms.CharField(widget=forms.PasswordInput, label="Confirm Password")

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get('password1')
        password2 = cleaned.get('password2')
        if password1 != password2:
            self.add_error('password2', "Passwords do not match.")
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user


class AdminUserChangeForm(AdminUserBaseForm):
    password1 = forms.CharField(
        widget=forms.PasswordInput,
        label="New Password",
        required=False,
    )
    password2 = forms.CharField(
        widget=forms.PasswordInput,
        label="Confirm New Password",
        required=False,
    )

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get('password1')
        password2 = cleaned.get('password2')
        if password1 or password2:
            if password1 != password2:
                self.add_error('password2', "Passwords do not match.")
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        if self.cleaned_data.get('password1'):
            user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user
