# orders/admin.py
from django.contrib import admin
from .models import Order, OrderItem, ReturnRequest


@admin.action(description="Eliberează escrow și creditează wallet-urile sellerilor")
def release_escrow_action(modeladmin, request, queryset):
    count = 0
    for order in queryset:
        if order.escrow_status == Order.ESCROW_HELD:
            order.release_escrow()
            count += 1
    modeladmin.message_user(
        request,
        f"Escrow eliberat pentru {count} comenzi.",
    )


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "buyer",
        "total",
        "payment_status",
        "escrow_status",
        "created_at",
    )
    list_filter = ("payment_status", "escrow_status", "created_at")
    actions = [release_escrow_action]

    # NECESAR pentru autocomplete_fields din TicketAdmin (support)
    search_fields = (
        "id",
        "buyer__email",
        "buyer__first_name",
        "buyer__last_name",
    )


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("order", "product", "quantity", "price")


@admin.register(ReturnRequest)
class ReturnRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "buyer", "status", "created_at")
    list_filter = ("status", "created_at")

    # NECESAR pentru autocomplete_fields (return_request) din TicketAdmin
    search_fields = (
        "id",
        "order__id",
        "buyer__email",
        "buyer__first_name",
        "buyer__last_name",
    )
