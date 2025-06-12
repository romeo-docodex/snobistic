from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),

    # Aplicații interne
    path('', include('core.urls')),
    path('cont/', include('accounts.urls')),
    path('produse/', include('products.urls')),
    path('magazin/', include('shop.urls')),
    path('comenzi/', include('orders.urls')),
    path('cos/', include('cart.urls')),
    path('portofel/', include('wallet.urls')),
    path('plati/', include('payments.urls')),
    path('licitatii/', include('auctions.urls')),
    path('suport/', include('support.urls')),
    path('chat/', include('chat.urls')),

    # Dashboard (roluri separate)
    path('dashboard/admin/', include('dashboard.admin_urls')),
    path('dashboard/seller/', include('dashboard.seller_urls')),
    path('dashboard/buyer/', include('dashboard.buyer_urls')),
    path('dashboard/manager/', include('dashboard.shopmanager_urls')),
]

# Servire fișiere media în dezvoltare
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
