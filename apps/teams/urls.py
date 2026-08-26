"""Teams routing."""

from rest_framework.routers import DefaultRouter

from apps.teams.views import TeamViewSet

app_name = "teams"

router = DefaultRouter()
router.register(r"", TeamViewSet, basename="teams")

urlpatterns = router.urls
