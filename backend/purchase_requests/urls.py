from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

app_name = "purchase_requests"

# Router for viewsets
router = DefaultRouter()
router.register(r'requests', views.StaffRequestViewSet, basename='staff-request')
router.register(r'approvals', views.ApproverRequestViewSet, basename='approver-request')
router.register(r'finance', views.FinanceRequestViewSet, basename='finance-request')

urlpatterns = [
    # Authentication endpoints
    path("auth/register/", views.RegisterView.as_view(), name="register"),
    path("auth/login/", views.login_view, name="login"),
    path("auth/logout/", views.logout_view, name="logout"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/profile/", views.profile_view, name="profile"),
    
    # Include router URLs
    path("", include(router.urls)),
]
