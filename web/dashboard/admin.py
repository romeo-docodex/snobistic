# dashboard/admin.py
from django.contrib import admin

# Momentan aplicația "dashboard" nu are modele proprii.
# Când vei avea modele de configurare/raportare pentru dashboard,
# le vei importa și înregistra aici.
#
# exemplu:
# from .models import SellerStats
#
# @admin.register(SellerStats)
# class SellerStatsAdmin(admin.ModelAdmin):
#     list_display = ("seller", "total_sales", "total_revenue", "updated_at")
#     search_fields = ("seller__username", "seller__email")
#     list_filter = ("updated_at",)
