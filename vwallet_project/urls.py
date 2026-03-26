from django.contrib import admin
from django.urls import include, path
from django.shortcuts import redirect
from django.contrib.auth import views as auth_views
from django.contrib.auth import logout as django_logout
from django.views.decorators.csrf import csrf_exempt
from dj_wallet.api.health import health_view
from dj_wallet.api.views import MobileAuthTokenView
from dj_wallet.portal import mobile_view
from dj_wallet.pwa import manifest, service_worker, offline_page


urlpatterns = [
    path("", lambda request: redirect("/api/"), name="root"),
    path("healthz/", health_view, name="healthz"),
    path("admin/", admin.site.urls),
    path("mobile/", mobile_view, name="mobile"),
    path("manifest.webmanifest", manifest, name="pwa-manifest"),
    path("sw.js", service_worker, name="pwa-sw"),
    path("offline/", offline_page, name="pwa-offline"),
    path("api/auth/token", csrf_exempt(MobileAuthTokenView.as_view()), name="auth-token"),
    path(
        "api/auth/token/",
        csrf_exempt(MobileAuthTokenView.as_view()),
        name="auth-token-slash",
    ),
    path("api/", include("dj_wallet.api.urls")),
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", lambda request: (django_logout(request), redirect("/login/"))[1], name="logout"),
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(),
        name="password_reset_done",
    ),
    path(
        "password-reset/confirm/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "password-reset/complete/",
        auth_views.PasswordResetCompleteView.as_view(),
        name="password_reset_complete",
    ),
]
