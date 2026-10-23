"""ModelAdmins covering list_display, filters, actions, inlines and permissions."""

from __future__ import annotations

from typing import Any

from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest

from tests.test_project.library.models import Author
from tests.test_project.library.models import AuthorProfile
from tests.test_project.library.models import Book
from tests.test_project.library.models import Chapter
from tests.test_project.library.models import Publisher
from tests.test_project.library.models import Review
from tests.test_project.library.models import Tag


class PriceFilter(admin.SimpleListFilter):
    title = "price band"
    parameter_name = "band"

    def lookups(self, request: HttpRequest, model_admin: Any) -> list[tuple[str, str]]:
        return [("cheap", "Under 10"), ("premium", "10 and up")]

    def queryset(self, request: HttpRequest, queryset: QuerySet[Any]) -> QuerySet[Any]:
        if self.value() == "cheap":
            return queryset.filter(price__lt=10)
        if self.value() == "premium":
            return queryset.filter(price__gte=10)
        return queryset


class ReviewInline(admin.TabularInline):
    model = Review
    extra = 1


class ChapterInline(admin.StackedInline):
    model = Chapter
    extra = 0
    max_num = 50


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ("name", "email")
    search_fields = ("name", "email")


@admin.register(AuthorProfile)
class AuthorProfileAdmin(admin.ModelAdmin):
    list_display = ("author", "website")


@admin.register(Publisher)
class PublisherAdmin(admin.ModelAdmin):
    list_display = ("name", "country")
    list_filter = ("country",)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False  # publishers are imported, never added by hand


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    search_fields = ("name",)


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "status", "price_display")
    list_display_links = ("title",)
    list_filter = ("status", ("publisher", admin.RelatedOnlyFieldListFilter), PriceFilter)
    search_fields = ("title", "author__name")
    readonly_fields = ("created_at",)
    exclude = ("internal_notes",)
    autocomplete_fields = ("author",)
    prepopulated_fields = {"slug": ("title",)}
    date_hierarchy = "created_at"
    list_per_page = 25
    inlines = (ReviewInline, ChapterInline)
    actions = ("mark_published",)

    @admin.display(description="Price")
    def price_display(self, obj: Book) -> str:
        return f"${obj.price}"

    @admin.action(description="Publish selected %(verbose_name_plural)s", permissions=["publish"])
    def mark_published(self, request: HttpRequest, queryset: QuerySet[Book]) -> None:
        queryset.update(status=Book.Status.PUBLISHED)

    def has_publish_permission(self, request: HttpRequest) -> bool:
        return bool(request.user.has_perm("library.publish_book"))


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("book", "rating")
    fieldsets = (
        (None, {"fields": ("book", "rating")}),
        ("Text", {"fields": ("body",)}),
    )


class OpsSite(admin.AdminSite):
    """A second site: only superusers may use it."""

    site_header = "Ops"

    def has_permission(self, request: HttpRequest) -> bool:
        return bool(request.user.is_active and request.user.is_superuser)


ops_site = OpsSite(name="ops")
ops_site.register(Tag, TagAdmin)
