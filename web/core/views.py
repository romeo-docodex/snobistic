# core/views.py
import datetime

from django.conf import settings
from django.contrib import messages
from django.core.mail import BadHeaderError, send_mail
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse

from .forms import ContactForm
from .models import ContactMessage

from catalog.models import Product, Category


def home(request):
    """
    Homepage view
    Renders the main landing page with real products + categories.
    """

    # produse active și aprobate, ordonate explicit după cele mai noi
    product_qs = (
        Product.objects.filter(
            is_active=True,
            is_archived=False,
            moderation_status="APPROVED",
        )
        .select_related("category", "brand")
        .order_by("-created_at")  # 👈 asigurăm ordinea: cele mai noi primele
    )

    # ultimele 16 produse
    latest_products = list(product_qs[:16])

    # secțiuni derivate
    popular_products = latest_products[:8]
    todays_picks = latest_products[8:] if len(latest_products) > 8 else latest_products

    # toate categoriile
    homepage_categories = Category.objects.all().order_by("name")

    context = {
        "popular_products": popular_products,
        "todays_picks": todays_picks,

        # ultimele produse
        "latest_products": latest_products,

        # compatibilitate cu cod mai vechi
        "featured_products": latest_products,
        "today_picks": todays_picks,

        # categorii
        "homepage_categories": homepage_categories,
    }
    return render(request, "core/home.html", context)


def about(request):
    """
    About page view
    Renders the About Us static page.
    """
    return render(request, "core/about.html")


def terms(request):
    """
    Terms and Conditions page view
    Renders the Terms & Conditions static page.
    """
    return render(request, "core/terms.html")


def privacy(request):
    """
    Privacy Policy page view
    Renders the Privacy Policy static page.
    """
    return render(request, "core/privacy.html")


def faq(request):
    """
    FAQ / Help – întrebări frecvente.
    """
    return render(request, "core/faq.html")


def returns_policy(request):
    """
    Politica de retur.
    """
    return render(request, "core/returns.html")


def cookies_policy(request):
    """
    Politica de cookies.
    """
    return render(request, "core/cookies.html")


def contact(request):
    """
    Contact page view
    - afișează formularul de contact
    - salvează mesajul în DB
    - trimite e-mail către suport
    - protecție anti-spam (honeypot)
    """
    if request.method == "POST":
        form = ContactForm(request.POST)

        if form.is_valid():
            # anti-spam: dacă honeypot NU e gol, ignorăm
            if form.cleaned_data.get("honeypot"):
                messages.warning(
                    request,
                    "A apărut o eroare. Te rugăm să încerci din nou.",
                )
                return redirect("core:contact")

            contact_msg: ContactMessage = form.save(commit=False)

            # meta info
            contact_msg.ip_address = request.META.get("REMOTE_ADDR")
            contact_msg.user_agent = request.META.get("HTTP_USER_AGENT", "")[:2000]
            if request.user.is_authenticated:
                contact_msg.user = request.user

            contact_msg.save()

            # trimitem e-mail
            subject = f"[Snobistic Contact] {contact_msg.subject}"
            body = (
                f"From: {contact_msg.name} <{contact_msg.email}>\n\n"
                f"Message:\n{contact_msg.message}\n\n"
                f"ID mesaj: {contact_msg.pk}\n"
                f"IP: {contact_msg.ip_address}\n"
            )

            to_email = getattr(
                settings,
                "SNOBISTIC_CONTACT_EMAIL",
                "support@snobistic.ro",
            )

            try:
                send_mail(
                    subject,
                    body,
                    settings.DEFAULT_FROM_EMAIL,
                    [to_email],
                    fail_silently=False,
                )
            except BadHeaderError:
                messages.error(
                    request,
                    "A apărut o eroare la trimiterea mesajului. Te rugăm să încerci din nou.",
                )
                return redirect("core:contact")

            messages.success(
                request,
                "Mesajul tău a fost trimis cu succes. Îți vom răspunde în cel mai scurt timp.",
            )
            return redirect("core:contact")
    else:
        form = ContactForm()

    return render(request, "core/contact.html", {"form": form})


def robots_txt(request):
    """
    Serves the robots.txt file dynamically.
    """
    content = (
        "User-agent: *\n"
        "Disallow: /admin/\n"
        "Disallow: /static/\n"
        f"Sitemap: https://{request.get_host()}/sitemap.xml\n"
    )
    return HttpResponse(content, content_type="text/plain")


def sitemap_xml(request):
    """
    Serves the sitemap.xml dynamically.
    Include paginile statice esențiale din core.
    Pentru produse / blog se recomandă django.contrib.sitemaps în proiectul root.
    """
    today = datetime.date.today()

    pages = [
        {
            "url": request.build_absolute_uri(reverse("core:home")),
            "lastmod": today,
            "changefreq": "daily",
            "priority": "1.0",
        },
        {
            "url": request.build_absolute_uri(reverse("core:about")),
            "lastmod": today,
            "changefreq": "monthly",
            "priority": "0.5",
        },
        {
            "url": request.build_absolute_uri(reverse("core:contact")),
            "lastmod": today,
            "changefreq": "monthly",
            "priority": "0.5",
        },
        {
            "url": request.build_absolute_uri(reverse("core:terms")),
            "lastmod": today,
            "changefreq": "yearly",
            "priority": "0.3",
        },
        {
            "url": request.build_absolute_uri(reverse("core:privacy")),
            "lastmod": today,
            "changefreq": "yearly",
            "priority": "0.3",
        },
        {
            "url": request.build_absolute_uri(reverse("core:faq")),
            "lastmod": today,
            "changefreq": "monthly",
            "priority": "0.4",
        },
        {
            "url": request.build_absolute_uri(reverse("core:returns")),
            "lastmod": today,
            "changefreq": "yearly",
            "priority": "0.4",
        },
        {
            "url": request.build_absolute_uri(reverse("core:cookies")),
            "lastmod": today,
            "changefreq": "yearly",
            "priority": "0.3",
        },
    ]

    xml = render_to_string(
        "core/sitemap.xml",
        {"sitemap_pages": pages, "today": today},
    )
    return HttpResponse(xml, content_type="application/xml")
