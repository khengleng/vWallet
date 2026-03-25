from django.contrib import admin
from django.urls import include, path
from django.contrib.auth import views as auth_views
from rest_framework.authtoken import views as drf_views
from dj_wallet.api.health import health_view


urlpatterns = [
    path("healthz/", health_view, name="healthz"),
    path("admin/", admin.site.urls),
    path("api/", include("dj_wallet.api.urls")),
    path("api/auth/token", drf_views.obtain_auth_token, name="auth-token"),
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
]
