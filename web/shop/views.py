from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from products.models import Product
from .models import Favorite


# ========================
# CATALOG
# ========================

def catalog_view(request):
    query = request.GET.get('q', '')
    products = Product.objects.filter(is_active=True, is_approved=True)

    if query:
        products = products.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query)
        )

    return render(request, 'shop/catalog.html', {
        'products': products,
        'query': query,
    })


# ========================
# FAVORITE VIEW
# ========================

@login_required
def favorites_view(request):
    favorite_products = Product.objects.filter(favorited_by__user=request.user)
    return render(request, 'shop/favorites.html', {
        'products': favorite_products
    })


# ========================
# ADĂUGARE FAVORITE
# ========================

@login_required
def add_to_favorites(request, product_id):
    product = get_object_or_404(Product, pk=product_id)

    Favorite.objects.get_or_create(user=request.user, product=product)
    return redirect(request.META.get('HTTP_REFERER', 'catalog'))


# ========================
# ȘTERGERE FAVORITE
# ========================

@login_required
def remove_from_favorites(request, product_id):
    product = get_object_or_404(Product, pk=product_id)

    Favorite.objects.filter(user=request.user, product=product).delete()
    return redirect(request.META.get('HTTP_REFERER', 'favorites'))
