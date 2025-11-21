from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

app_name = "purchase_requests"

urlpatterns = [
    # Authentication endpoints
    path("auth/register/", views.RegisterView.as_view(), name="register"),
    path("auth/login/", views.login_view, name="login"),
    path("auth/logout/", views.logout_view, name="logout"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/profile/", views.profile_view, name="profile"),
]
