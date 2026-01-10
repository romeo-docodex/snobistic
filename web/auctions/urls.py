# auctions/urls.py
from django.urls import path

from . import views
from .views_wizard import AuctionCreateWizard, AuctionEditWizard

app_name = "auctions"

urlpatterns = [
    # list/detail/bids
    path("", views.auction_list_view, name="auction_list"),
    path("detalii/<int:pk>/", views.auction_detail_view, name="auction_detail"),
    path("detalii/<int:pk>/liciteaza/", views.place_bid_view, name="place_bid"),

    # ✅ start auction for existing product (from product_detail)
    path("<slug:product_slug>/creeaza/", views.create_auction_for_product_view, name="create_auction"),

    # owner ops
    path("<slug:product_slug>/inchide/", views.close_auction_view, name="close_auction"),
    path("<slug:product_slug>/anuleaza/", views.cancel_auction_view, name="cancel_auction"),

    # ✅ ONLY wizard create/edit (create = creates product+auction)
    path("creeaza/", AuctionCreateWizard.as_view(), name="wizard_create"),
    path("editeaza/<int:pk>/", AuctionEditWizard.as_view(), name="wizard_edit"),
]
