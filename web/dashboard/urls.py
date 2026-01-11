# dashboard/urls.py
from django.urls import path
from . import views

app_name = "dashboard"

urlpatterns = [
    # Seller namespace
    path("vanzator/", views.seller_dashboard, name="seller_dashboard"),
    path("vanzator/produse/", views.products_list, name="products_list"),
    path("vanzator/licitatii/", views.auctions_list, name="auctions_list"),
    path("vanzator/vandute/", views.sold_list, name="sold_list"),

    # ✅ păstrăm ruta veche, dar view-ul face redirect -> wallet app
    path("vanzator/portofel/", views.wallet, name="wallet"),

    # Seller – acțiuni pe comenzi vândute (AWB, retur, comision)
    path(
        "vanzator/comenzi/<int:order_id>/<int:item_id>/awb/genereaza/",
        views.generate_awb,
        name="generate_awb",
    ),
    path(
        "vanzator/comenzi/<int:order_id>/<int:item_id>/awb/descarca/",
        views.download_awb,
        name="download_awb",
    ),
    path(
        "vanzator/comenzi/<int:order_id>/<int:item_id>/colet/poze-incarcare/",
        views.upload_package_photos,
        name="upload_package",
    ),
    path(
        "vanzator/comenzi/<int:order_id>/<int:item_id>/colet/marcheaza-trimis/",
        views.mark_sent,
        name="mark_sent",
    ),
    path(
        "vanzator/comenzi/<int:order_id>/<int:item_id>/colet/poze/",
        views.view_package_photos,
        name="view_package_photos",
    ),
    path(
        "vanzator/comenzi/<int:order_id>/<int:item_id>/retur/initiere/",
        views.initiate_return_seller,
        name="initiate_return",
    ),
    path(
        "vanzator/comenzi/<int:order_id>/<int:item_id>/comision/factura/",
        views.download_commission_invoice,
        name="download_commission_invoice",
    ),

    # Buyer namespace
    path("cumparator/", views.buyer_dashboard, name="buyer_dashboard"),
    path("cumparator/comenzi/", views.orders_list, name="orders_list"),
    path("cumparator/chat-rapid/", views.chat_quick, name="chat_quick"),
]
