from django.contrib import admin
from django.urls import path, include
from two_factor.urls import urlpatterns as tf_urls

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),

    # Two-Factor Authentication (django-two-factor-auth)
    path('', include(tf_urls)),

    # Social & Account (django-allauth)
    path('accounts/', include('allauth.urls')),

    # Custom account views (register, profile, change-password etc.)
    path('accounts/', include(('accounts.urls', 'accounts'), namespace='accounts')),

    # Core (home, about, contact)
    path('', include(('core.urls', 'core'), namespace='core')),

    # Shop (catalog, favorites, search)
    path('shop/', include(('shop.urls', 'shop'), namespace='shop')),

    # Products
    path('products/', include(('products.urls', 'products'), namespace='products')),

    # Cart
    path('cart/', include(('cart.urls', 'cart'), namespace='cart')),

    # Orders & Returns
    path('orders/', include(('orders.urls', 'orders'), namespace='orders')),

    # Payments
    path('payments/', include(('payments.urls', 'payments'), namespace='payments')),

    # Auctions
    path('auctions/', include(('auctions.urls', 'auctions'), namespace='auctions')),

    # Chat/Inbox
    path('chat/', include(('chat.urls', 'chat'), namespace='chat')),

    # Support/Ticketing
    path('support/', include(('support.urls', 'support'), namespace='support')),

    # Wallet/Transactions
    path('wallet/', include(('wallet.urls', 'wallet'), namespace='wallet')),
]
