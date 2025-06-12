from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from django.db import transaction

from cart.models import CartItem
from .models import Order, OrderItem
from .forms import OrderAddressForm, ReturnRequestForm

@login_required
def checkout_view(request):
    cart_items = CartItem.objects.filter(user=request.user)
    if not cart_items:
        messages.warning(request, "Coșul este gol.")
        return redirect('cart:cart_detail')

    if request.method == 'POST':
        form = OrderAddressForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                order = form.save(commit=False)
                order.user = request.user
                order.total = sum(ci.subtotal() for ci in cart_items)
                order.save()
                for ci in cart_items:
                    OrderItem.objects.create(
                        order=order,
                        product=ci.product,
                        quantity=ci.quantity,
                        price=ci.product.price
                    )
                cart_items.delete()
            messages.success(request, "Comanda a fost plasată.")
            return redirect('payments:checkout', order_id=order.pk)
    else:
        form = OrderAddressForm()

    return render(request, 'orders/checkout.html', {
        'form': form,
        'cart_items': cart_items
    })


@login_required
def order_list_view(request):
    orders = request.user.orders.all()
    return render(request, 'orders/order_list.html', {'orders': orders})


@login_required
def order_detail_view(request, order_id):
    order = get_object_or_404(Order, pk=order_id, user=request.user)
    return render(request, 'orders/order_detail.html', {'order': order})


@login_required
def return_request_view(request, item_id):
    order_item = get_object_or_404(
        OrderItem, pk=item_id, order__user=request.user
    )
    order = order_item.order
    if not order.is_returnable():
        messages.error(request, "Comanda nu poate fi returnată.")
        return redirect('orders:order_detail', order_id=order.pk)
    if hasattr(order_item, 'return_request'):
        messages.info(request, "Cerere de retur deja trimisă.")
        return redirect('orders:order_detail', order_id=order.pk)

    if request.method == 'POST':
        form = ReturnRequestForm(request.POST)
        if form.is_valid():
            rr = form.save(commit=False)
            rr.order_item = order_item
            rr.save()
            messages.success(request, "Cererea de retur a fost trimisă.")
            return redirect('orders:order_detail', order_id=order.pk)
    else:
        form = ReturnRequestForm()

    return render(request, 'orders/return_form.html', {
        'form': form,
        'order_item': order_item
    })
