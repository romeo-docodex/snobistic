from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from orders.models import Order
from products.models import Product
from auctions.models import Auction
from support.models import SupportTicket
from chat.models import ChatSession
from wallet.models import Wallet, Transaction
from accounts.models import CustomUser


# ============================
# UTILITARE DE ROLURI
# ============================

def is_admin(user):
    return user.is_staff or user.is_superuser

def is_seller(user):
    return user.groups.filter(name='Seller').exists()

def is_buyer(user):
    return user.groups.filter(name='Buyer').exists()

def is_shopmanager(user):
    return user.groups.filter(name='ShopManager').exists()


# ============================
# DASHBOARD ADMIN
# ============================

@user_passes_test(is_admin)
def admin_dashboard_view(request):
    users = CustomUser.objects.all().count()
    tickets = SupportTicket.objects.count()
    sessions = ChatSession.objects.count()
    return render(request, 'dashboard/admin/overview.html', {
        'users': users,
        'tickets': tickets,
        'sessions': sessions,
    })


# ============================
# DASHBOARD SELLER
# ============================

@user_passes_test(is_seller)
def seller_dashboard_view(request):
    products = Product.objects.filter(user=request.user)
    auctions = Auction.objects.filter(user=request.user)
    return render(request, 'dashboard/seller/overview.html', {
        'products': products,
        'auctions': auctions,
    })


# ============================
# DASHBOARD BUYER
# ============================

@user_passes_test(is_buyer)
def buyer_dashboard_view(request):
    orders = Order.objects.filter(user=request.user)
    wallet = Wallet.objects.filter(user=request.user).first()
    return render(request, 'dashboard/buyer/overview.html', {
        'orders': orders,
        'wallet': wallet,
    })


# ============================
# DASHBOARD SHOP MANAGER
# ============================

@user_passes_test(is_shopmanager)
def shopmanager_dashboard_view(request):
    pending_products = Product.objects.filter(is_approved=False)
    return render(request, 'dashboard/shopmanager/overview.html', {
        'pending_products': pending_products,
    })
