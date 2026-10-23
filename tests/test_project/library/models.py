"""A small catalogue exercising every relation and admin feature we graph."""

from __future__ import annotations

from django.db import models


class Author(models.Model):
    name = models.CharField(max_length=120)
    email = models.EmailField(unique=True)
    bio = models.TextField(blank=True, help_text="Shown on the author page.")

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class AuthorProfile(models.Model):
    author = models.OneToOneField(Author, on_delete=models.CASCADE, related_name="profile")
    website = models.URLField(blank=True)

    def __str__(self) -> str:
        return f"Profile of {self.author}"


class Publisher(models.Model):
    class Country(models.TextChoices):
        AR = "AR", "Argentina"
        ES = "ES", "Spain"

    name = models.CharField(max_length=120)
    country = models.CharField(max_length=2, choices=Country.choices, default=Country.AR)

    def __str__(self) -> str:
        return self.name


class Tag(models.Model):
    name = models.CharField(max_length=40, unique=True)

    def __str__(self) -> str:
        return self.name


class Book(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"

    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    author = models.ForeignKey(Author, on_delete=models.PROTECT, related_name="books")
    publisher = models.ForeignKey(Publisher, on_delete=models.SET_NULL, null=True, blank=True)
    tags = models.ManyToManyField(Tag, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    price = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    internal_notes = models.TextField(blank=True, help_text="Never shown in the admin.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        permissions = [("publish_book", "Can publish book")]

    def __str__(self) -> str:
        return self.title


class Review(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="reviews")
    rating = models.PositiveSmallIntegerField(choices=[(i, str(i)) for i in range(1, 6)])
    body = models.TextField()

    def __str__(self) -> str:
        return f"{self.rating}/5"


class Chapter(models.Model):
    """Edited only through the Book inline — not registered on its own."""

    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    number = models.PositiveIntegerField()
    title = models.CharField(max_length=200)

    def __str__(self) -> str:
        return f"{self.number}. {self.title}"


class AuditEntry(models.Model):
    """Not registered on any admin site — must never appear in a graph."""

    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    message = models.TextField()

    def __str__(self) -> str:
        return self.message
