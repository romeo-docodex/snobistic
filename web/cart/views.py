from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.db import transaction
from .models import CartItem
from .forms import AddToCartForm, UpdateCartItemForm
from products.models import Product


def _get_or_create_session_key(request):
    key = request.session.session_key
    if not key:
        request.session.create()
        key = request.session.session_key
    return key


def _get_cart_items(request):
    if request.user.is_authenticated:
        return CartItem.objects.filter(user=request.user)
    session_key = _get_or_create_session_key(request)
    return CartItem.objects.filter(session_key=session_key)


@require_POST
def add_to_cart_view(request):
    form = AddToCartForm(request.POST)
    if form.is_valid():
        prod_id = form.cleaned_data['product_id']
        product = get_object_or_404(Product, pk=prod_id)

        # Nu adăugăm produse licitație
        if product.listing_type == 'auction':
            messages.error(request, "Produsele din licitație nu pot fi adăugate în coș.")
            return redirect('products:product_detail', slug=product.slug)

        qty = form.cleaned_data['quantity']
        if request.user.is_authenticated:
            item, created = CartItem.objects.get_or_create(
                user=request.user, product=product,
                defaults={'quantity': qty}
            )
        else:
            session_key = _get_or_create_session_key(request)
            item, created = CartItem.objects.get_or_create(
                session_key=session_key, product=product,
                defaults={'quantity': qty}
            )

        if not created:
            item.quantity += qty
            item.save()

        messages.success(request, f"Am adăugat {qty}×{product.name} în coș.")
    else:
        messages.error(request, "Cantitate invalidă.")
    return redirect('cart:cart_detail')


def cart_detail_view(request):
    items = _get_cart_items(request)
    total = sum(item.subtotal() for item in items)
    forms = {item.id: UpdateCartItemForm(instance=item) for item in items}
    return render(request, 'cart/cart_detail.html', {
        'cart_items': items,
        'total': total,
        'forms': forms,
    })


@require_POST
def update_cart_item_view(request, item_id):
    item = get_object_or_404(CartItem, pk=item_id)
    # verific ownership
    if request.user.is_authenticated:
        if item.user != request.user:
            return redirect('cart:cart_detail')
    else:
        if item.session_key != _get_or_create_session_key(request):
            return redirect('cart:cart_detail')

    form = UpdateCartItemForm(request.POST, instance=item)
    if form.is_valid():
        form.save()
        messages.success(request, "Cantitatea a fost actualizată.")
    else:
        messages.error(request, "Cantitate invalidă.")
    return redirect('cart:cart_detail')


@require_POST
def remove_cart_item_view(request, item_id):
    item = get_object_or_404(CartItem, pk=item_id)
    if request.user.is_authenticated and item.user == request.user:
        item.delete()
        messages.success(request, "Produsul a fost eliminat din coș.")
    else:
        if not request.user.is_authenticated and item.session_key == _get_or_create_session_key(request):
            item.delete()
            messages.success(request, "Produsul a fost eliminat din coș.")
    return redirect('cart:cart_detail')
