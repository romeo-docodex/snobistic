# support/admin.py
from django.contrib import admin

from .models import Ticket, TicketMessage


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "subject",
        "owner",
        "category",
        "status",
        "priority",
        "order",
        "created_at",
    )
    list_filter = ("status", "priority", "category", "created_at")
    search_fields = (
        "id",
        "subject",
        "owner__email",
        "owner__first_name",
        "owner__last_name",
        "order__id",
    )
    autocomplete_fields = ("owner", "order", "return_request")
    ordering = ("-created_at",)


@admin.register(TicketMessage)
class TicketMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "ticket", "author", "created_at")
    search_fields = ("ticket__id", "author__email", "text")
    ordering = ("-created_at",)
