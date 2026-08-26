"""Authentication and user management routing."""

from django.urls import path

from apps.users.views import LogoutView, MeView, ObtainAuthTokenView, RegisterView

app_name = "users"

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("token/", ObtainAuthTokenView.as_view(), name="token"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/", MeView.as_view(), name="me"),
]
