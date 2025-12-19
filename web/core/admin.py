from django.contrib import admin
from .models import ContactMessage


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'subject',
        'name',
        'email',
        'created_at',
        'is_processed',
        'processed_by',
    )
    list_display_links = ('id', 'subject')
    list_filter = (
        'is_processed',
        'created_at',
        'processed_by',
    )
    search_fields = (
        'name',
        'email',
        'subject',
        'message',
        'ip_address',
        'user__username',
        'user__email',
    )
    readonly_fields = (
        'name',
        'email',
        'subject',
        'message',
        'created_at',
        'ip_address',
        'user_agent',
        'user',
        'processed_at',
        'processed_by',
    )
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    list_per_page = 50

    actions = ['mark_as_processed', 'mark_as_unprocessed']

    fieldsets = (
        ("Detalii mesaj", {
            'fields': ('name', 'email', 'subject', 'message', 'created_at'),
        }),
        ("Meta & tracking", {
            'fields': ('ip_address', 'user_agent', 'user'),
            'classes': ('collapse',),
        }),
        ("Procesare suport", {
            'fields': ('is_processed', 'processed_at', 'processed_by'),
        }),
    )

    def mark_as_processed(self, request, queryset):
        updated = queryset.update(
            is_processed=True,
            processed_at=None,  # poți schimba în timezone.now() dacă vrei să setezi aici
            processed_by=request.user,
        )
        self.message_user(request, f"{updated} mesaj(e) marcate ca procesate.")
    mark_as_processed.short_description = "Marchează ca procesate"

    def mark_as_unprocessed(self, request, queryset):
        updated = queryset.update(
            is_processed=False,
            processed_at=None,
            processed_by=None,
        )
        self.message_user(request, f"{updated} mesaj(e) marcate ca NEprocesate.")
    mark_as_unprocessed.short_description = "Marchează ca neprocesate"
