# user_manager/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import User

class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField()
    major = forms.CharField(max_length=100)

    class Meta:
        model = User
        fields = ['username', 'email', 'major', 'password1', 'password2']

class UserLoginForm(AuthenticationForm):
    pass