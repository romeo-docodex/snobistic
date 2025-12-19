# catalog/urls.py
from django.urls import path

from . import views
from . import views_wizard

app_name = "catalog"

urlpatterns = [
    # /magazin/  (presupunând că în urls.py principal ai ceva gen: path("magazin/", include("catalog.urls")))
    path("", views.ProductListView.as_view(), name="product_list"),

    # /magazin/categorie/<slug>/
    path(
        "categorie/<slug:slug>/",
        views.CategoryListView.as_view(),
        name="category_list",
    ),

    # /magazin/produs/<slug>/
    path(
        "produs/<slug:slug>/",
        views.ProductDetailView.as_view(),
        name="product_detail",
    ),

    # AJAX – subcategorii pentru o categorie
    # /magazin/ajax/subcategorii/
    path(
        "ajax/subcategorii/",
        views.ajax_subcategories,
        name="ajax_subcategories",
    ),

    # Căutare: /magazin/cautare/
    path("cautare/", views.SearchResultsView.as_view(), name="search_results"),

    # Favorite: /magazin/favorite/
    path("favorite/", views.FavoritesListView.as_view(), name="favorites"),

    # Toggle favorite: /magazin/favorite/<pk>/comuta/
    path(
        "favorite/<int:pk>/comuta/",
        views.toggle_favorite,
        name="toggle_favorite",
    ),

    # seller CRUD clasic
    # /magazin/produs/adaugare/
    path(
        "produs/adaugare/",
        views.ProductCreateView.as_view(),
        name="product_create",
    ),
    # /magazin/produs/<pk>/editare/
    path(
        "produs/<int:pk>/editare/",
        views.ProductUpdateView.as_view(),
        name="product_update",
    ),
    # /magazin/produs/<pk>/stergere/
    path(
        "produs/<int:pk>/stergere/",
        views.ProductDeleteView.as_view(),
        name="product_delete",
    ),

    # wizard multi-step pentru create/edit
    # /magazin/vinde/produs/nou/
    path(
        "vinde/produs/nou/",
        views_wizard.ProductCreateWizard.as_view(),
        name="product_create_wizard",
    ),
    # /magazin/vinde/produs/<pk>/editare/
    path(
        "vinde/produs/<int:pk>/editare/",
        views_wizard.ProductEditWizard.as_view(),
        name="product_edit_wizard",
    ),
]
