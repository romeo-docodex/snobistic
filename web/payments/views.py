import uuid
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.urls import reverse

from .models import Payment
from orders.models import Order

@login_required
def checkout_payment_view(request, order_id):
    """
    Afișează pagina de checkout, cu alegerea metodei de plată.
    """
    order = get_object_or_404(Order, pk=order_id, user=request.user)
    if order.total <= 0:
        messages.warning(request, "Această comandă nu necesită plată.")
        return redirect('orders:order_detail', order_id=order.pk)

    return render(request, 'payments/payment_checkout.html', {'order': order})

@login_required
def payment_redirect_view(request, order_id, method):
    """
    Inițiază plata pentru comanda dată, cu metoda aleasă.
    """
    order = get_object_or_404(Order, pk=order_id, user=request.user)
    payment, created = Payment.objects.get_or_create(
        order=order,
        defaults={
            'user': request.user,
            'amount': order.total,
            'method': method,
            'processor_payment_id': str(uuid.uuid4())
        }
    )
    # Actualizare metodă dacă user a ales altceva
    if not created and payment.method != method:
        payment.method = method
        payment.save()

    # Simulare redirect URL al procesatorului
    if not payment.redirect_url:
        payment.redirect_url = reverse('payments:payment_success') + f"?ref={payment.processor_payment_id}"
        payment.save()

    return redirect(payment.redirect_url)

@login_required
def payment_success_view(request):
    """
    Pagina de succes: marchează plata ca plătită.
    """
    ref = request.GET.get('ref')
    payment = get_object_or_404(Payment, processor_payment_id=ref)
    if payment.status != 'paid':
        payment.status = 'paid'
        payment.save()
        # Actualizează și comanda
        order = payment.order
        order.status = 'paid'
        order.save()
        messages.success(request, "Plata a fost procesată cu succes.")
    return render(request, 'payments/payment_success.html', {'payment': payment})

@login_required
def payment_fail_view(request):
    """
    Pagina de eșec a plății.
    """
    messages.error(request, "Plata a eșuat. Încearcă din nou.")
    return render(request, 'payments/payment_fail.html')

@csrf_exempt
def payment_webhook_view(request):
    """
    Endpoint pentru webhook-urile procesatorului (Stripe, Plati.ro).
    Așteaptă POST cu 'payment_id' și 'status'.
    """
    if request.method != 'POST':
        return HttpResponse(status=405)

    processor_id = request.POST.get('payment_id')
    status = request.POST.get('status')
    try:
        payment = Payment.objects.get(processor_payment_id=processor_id)
        payment.status = status
        payment.save()
        return JsonResponse({'status': 'ok'})
    except Payment.DoesNotExist:
        return JsonResponse({'error': 'payment not found'}, status=404)
