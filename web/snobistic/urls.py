# snobistic/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),

    path('', include('core.urls')),
    path("auth/", include("allauth.urls")),
    path('cont/', include('accounts.urls')),
    path('magazin/', include('catalog.urls')),
    path('cos/', include('cart.urls')),
    path('comenzi/', include('orders.urls')),
    path('licitatii/', include('auctions.urls')),
    path('autentificare-produs/', include('authenticator.urls')),
    path('mesaje/', include('messaging.urls')),
    path('panou/', include('dashboard.urls')),

    # ✅ Wallet separat
    path('portofel/', include('wallet.urls')),

    # Payments rămâne doar pentru plăți
    path('plati/', include('payments.urls')),

    path('suport/', include('support.urls')),
    path('facturi/', include('invoices.urls')),
    path('logistica/', include('logistics.urls', namespace='logistics')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
