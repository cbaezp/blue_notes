"""Notes routing."""

from rest_framework.routers import DefaultRouter

from apps.notes.views import NoteViewSet, TagViewSet

app_name = "notes"

router = DefaultRouter()
router.register(r"tags", TagViewSet, basename="tags")
router.register(r"", NoteViewSet, basename="notes")

urlpatterns = router.urls
