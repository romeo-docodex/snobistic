from django.contrib import admin
from .models import Order, OrderItem, ReturnRequest

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id','user','status','total','created_at')
    list_filter = ('status','created_at')
    search_fields = ('user__email','id')
    date_hierarchy = 'created_at'

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order','product','quantity','price')
    search_fields = ('product__name',)

@admin.register(ReturnRequest)
class ReturnRequestAdmin(admin.ModelAdmin):
    list_display = ('order_item','status','created_at')
    list_filter = ('status','created_at')
    search_fields = ('order_item__product__name',)
