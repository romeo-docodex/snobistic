# dashboard/urls.py
from django.urls import path
from . import views

app_name = "dashboard"

urlpatterns = [
    # Seller namespace
    # /cont/vanzator/
    path("vanzator/", views.seller_dashboard, name="seller_dashboard"),

    # /cont/vanzator/produse/
    path("vanzator/produse/", views.products_list, name="products_list"),

    # /cont/vanzator/licitatii/
    path("vanzator/licitatii/", views.auctions_list, name="auctions_list"),

    # /cont/vanzator/vandute/
    path("vanzator/vandute/", views.sold_list, name="sold_list"),

    # /cont/vanzator/portofel/
    path("vanzator/portofel/", views.wallet, name="wallet"),

    # Seller – acțiuni pe comenzi vândute (AWB, retur, comision)

    # /cont/vanzator/comenzi/<order_id>/<item_id>/awb/genereaza/
    path(
        "vanzator/comenzi/<int:order_id>/<int:item_id>/awb/genereaza/",
        views.generate_awb,
        name="generate_awb",
    ),

    # /cont/vanzator/comenzi/<order_id>/<item_id>/awb/descarca/
    path(
        "vanzator/comenzi/<int:order_id>/<int:item_id>/awb/descarca/",
        views.download_awb,
        name="download_awb",
    ),

    # /cont/vanzator/comenzi/<order_id>/<item_id>/colet/poze-incarcare/
    path(
        "vanzator/comenzi/<int:order_id>/<int:item_id>/colet/poze-incarcare/",
        views.upload_package_photos,
        name="upload_package",
    ),

    # /cont/vanzator/comenzi/<order_id>/<item_id>/colet/marcheaza-trimis/
    path(
        "vanzator/comenzi/<int:order_id>/<int:item_id>/colet/marcheaza-trimis/",
        views.mark_sent,
        name="mark_sent",
    ),

    # /cont/vanzator/comenzi/<order_id>/<item_id>/colet/poze/
    path(
        "vanzator/comenzi/<int:order_id>/<int:item_id>/colet/poze/",
        views.view_package_photos,
        name="view_package_photos",
    ),

    # /cont/vanzator/comenzi/<order_id>/<item_id>/retur/initiere/
    path(
        "vanzator/comenzi/<int:order_id>/<int:item_id>/retur/initiere/",
        views.initiate_return_seller,
        name="initiate_return",
    ),

    # /cont/vanzator/comenzi/<order_id>/<item_id>/comision/factura/
    path(
        "vanzator/comenzi/<int:order_id>/<int:item_id>/comision/factura/",
        views.download_commission_invoice,
        name="download_commission_invoice",
    ),

    # Buyer namespace

    # /cont/cumparator/
    path("cumparator/", views.buyer_dashboard, name="buyer_dashboard"),

    # /cont/cumparator/comenzi/
    path("cumparator/comenzi/", views.orders_list, name="orders_list"),

    # /cont/cumparator/chat-rapid/
    path("cumparator/chat-rapid/", views.chat_quick, name="chat_quick"),
]
