# snobistic/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),

    # Aplicații interne
    path('', include('core.urls')),                              # homepage, despre-noi, contact etc.
    path("auth/", include("allauth.urls")),
    path('cont/', include('accounts.urls')),                     # autentificare, profil, parole
    path('magazin/', include('catalog.urls')),                   # listă produse, categorii, produs
    path('cos/', include('cart.urls')),                          # coș de cumpărături
    path('comenzi/', include('orders.urls')),                    # comenzi + retururi
    path('licitatii/', include('auctions.urls')),                # licitații
    path('autentificare-produs/', include('authenticator.urls')),# verificare autenticitate
    path('mesaje/', include('messaging.urls')),                  # mesagerie între useri
    path('panou/', include('dashboard.urls')),                   # dashboard vânzător/cumpărător
    path('plati/', include('payments.urls')),                    # plăți, portofel
    path('suport/', include('support.urls')),                    # suport & tichete
    path('facturi/', include('invoices.urls')),                  # facturi
    path('logistica/', include('logistics.urls', namespace='logistics')),
]

# Servire fișiere media în dezvoltare
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
