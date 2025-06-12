from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from .forms import ContactForm
from products.models import Product
from auctions.models import Auction
from django.utils import timezone


def home_view(request):
    # Afișăm câteva produse și licitații „featured”
    featured_products = Product.objects.filter(is_published=True, is_active=True)[:8]
    ongoing_auctions = Auction.objects.filter(is_active=True, end_time__gt=timezone.now())[:4]
    return render(request, 'core/home.html', {
        'featured_products': featured_products,
        'ongoing_auctions': ongoing_auctions,
    })

def about_view(request):
    return render(request, 'core/about.html')

def contact_view(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            # Trimitem email către suport
            send_mail(
                subject=f"[Contact Snobistic] {form.cleaned_data['subject']}",
                message=(
                    f"De la: {form.cleaned_data['name']} <{form.cleaned_data['email']}>\n\n"
                    f"{form.cleaned_data['message']}"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[settings.DEFAULT_FROM_EMAIL],
                fail_silently=False,
            )
            messages.success(request, "Mesajul tău a fost trimis cu succes. Îți mulțumim!")
            return redirect('core:contact')
    else:
        form = ContactForm()
    return render(request, 'core/contact.html', {'form': form})
