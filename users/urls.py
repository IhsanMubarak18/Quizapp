from django.urls import path  # type: ignore
from .import views

app_name = 'users'

urlpatterns = [
    path('register/',views.user_register_view, name='user_register'),
    path('login/',views.user_login_view, name='login'),
    path('logout/',views.logout_view, name='logout'),
]