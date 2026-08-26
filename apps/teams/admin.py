"""Admin registration for Teams and TeamMemberships."""

from django.contrib import admin

from apps.teams.models import Team, TeamMembership


class TeamMembershipInline(admin.TabularInline):
    model = TeamMembership
    extra = 0
    fields = ("user", "role", "created_at")
    readonly_fields = ("created_at",)


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("name", "id", "created_by", "created_at")
    search_fields = ("name", "description", "created_by__username", "created_by__email")
    list_filter = ("created_at",)
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = [TeamMembershipInline]


@admin.register(TeamMembership)
class TeamMembershipAdmin(admin.ModelAdmin):
    list_display = ("team", "user", "role", "created_at")
    list_filter = ("role", "created_at")
    search_fields = ("team__name", "user__username", "user__email")
    readonly_fields = ("id", "created_at", "updated_at")
