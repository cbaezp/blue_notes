"""Factory Boy factories for test data generation."""

import factory
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token

from apps.notes.models import Note, NoteVisibility, Tag
from apps.teams.models import Team, TeamMembership, TeamRole

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    """Factory for creating User instances with authentication tokens."""

    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user_{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@example.com")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")

    @factory.post_generation
    def password(obj, create, extracted, **kwargs):
        password = extracted or "StrongSecretPassword123!"
        obj.set_password(password)
        if create:
            obj.save()
            Token.objects.get_or_create(user=obj)


class TeamFactory(factory.django.DjangoModelFactory):
    """Factory for creating Team workspaces."""

    class Meta:
        model = Team

    name = factory.Sequence(lambda n: f"Team {n}")
    description = factory.Faker("sentence")
    created_by = factory.SubFactory(UserFactory)

    @factory.post_generation
    def create_owner_membership(obj, create, extracted, **kwargs):
        if create and obj.created_by:
            TeamMembership.objects.get_or_create(
                team=obj,
                user=obj.created_by,
                defaults={"role": TeamRole.OWNER},
            )


class TeamMembershipFactory(factory.django.DjangoModelFactory):
    """Factory for creating team memberships."""

    class Meta:
        model = TeamMembership

    team = factory.SubFactory(TeamFactory)
    user = factory.SubFactory(UserFactory)
    role = TeamRole.MEMBER


class TagFactory(factory.django.DjangoModelFactory):
    """Factory for creating tags."""

    class Meta:
        model = Tag

    name = factory.Sequence(lambda n: f"tag_{n}")
    color = "#3B82F6"
    created_by = factory.SubFactory(UserFactory)


class NoteFactory(factory.django.DjangoModelFactory):
    """Factory for creating notes."""

    class Meta:
        model = Note

    author = factory.SubFactory(UserFactory)
    title = factory.Sequence(lambda n: f"Note Title {n}")
    body = factory.Faker("paragraph")
    visibility = NoteVisibility.TEAM
    version = 1
    is_pinned = False
