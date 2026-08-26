"""Admin registration for Notes, NoteVersions, and Tags."""

from django.contrib import admin

from apps.notes.models import Note, NoteVersion, Tag


class NoteVersionInline(admin.TabularInline):
    model = NoteVersion
    extra = 0
    fields = ("version_number", "title", "edited_by", "change_summary", "created_at")
    readonly_fields = ("version_number", "title", "edited_by", "change_summary", "created_at")
    can_delete = False


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "author",
        "team",
        "visibility",
        "version",
        "is_pinned",
        "is_deleted",
        "created_at",
    )
    list_filter = (
        "visibility",
        "is_pinned",
        "deleted_at",
        "created_at",
        "updated_at",
    )
    search_fields = ("title", "body", "author__username", "team__name")
    readonly_fields = ("id", "version", "search_vector", "created_at", "updated_at", "deleted_at")
    filter_horizontal = ("tags",)
    inlines = [NoteVersionInline]


@admin.register(NoteVersion)
class NoteVersionAdmin(admin.ModelAdmin):
    list_display = ("note", "version_number", "title", "edited_by", "created_at")
    list_filter = ("version_number", "created_at")
    search_fields = ("title", "body", "change_summary", "edited_by__username")
    readonly_fields = (
        "id",
        "note",
        "version_number",
        "title",
        "body",
        "edited_by",
        "change_summary",
        "created_at",
    )


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "color", "team", "created_by", "created_at")
    list_filter = ("created_at", "team")
    search_fields = ("name", "created_by__username", "team__name")
    readonly_fields = ("id", "created_at", "updated_at")
