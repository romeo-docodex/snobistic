# core/views.py
import datetime

from django.conf import settings
from django.contrib import messages
from django.core.mail import BadHeaderError, EmailMultiAlternatives
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from catalog.models import Product, Category
from .forms import ContactForm
from .models import ContactMessage, SiteSetting, PageSEO


def _get_client_ip(request):
    # dacă ai reverse proxy, setează corect în settings: USE_X_FORWARDED_HOST, SECURE_PROXY_SSL_HEADER etc.
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _page_seo(key: str):
    return PageSEO.objects.filter(key=key).first()


def home(request):
    # ✅ Homepage public: DOAR produse PUBLISHED + active + ne-arhivate
    product_qs = (
        Product.objects.public()
        .select_related("category", "subcategory", "brand", "base_color", "owner")
        .prefetch_related("images")
        .order_by("-published_at", "-created_at")
    )

    latest_products = list(product_qs[:16])  # păstrezi 16 dacă le folosești și în alte secțiuni

    popular_products = latest_products[:8]
    today_picks = latest_products[:8]  # ✅ max 8 produse pentru secțiunea asta

    homepage_categories = Category.objects.all().order_by("name")

    seo = _page_seo("core:home")
    context = {
        "popular_products": popular_products,
        "latest_products": latest_products,
        "today_picks": today_picks,  # ✅ folosit în template (grid)
        "homepage_categories": homepage_categories,
        "meta_title": seo.meta_title if seo and seo.meta_title else None,
        "meta_description": seo.meta_description if seo and seo.meta_description else None,
        "meta_robots": seo.meta_robots if seo and seo.meta_robots else None,
    }
    return render(request, "core/home.html", context)


def about(request):
    seo = _page_seo("core:about")
    return render(request, "core/about.html", {
        "meta_title": seo.meta_title if seo and seo.meta_title else None,
        "meta_description": seo.meta_description if seo and seo.meta_description else None,
        "meta_robots": seo.meta_robots if seo and seo.meta_robots else None,
    })


def terms(request):
    seo = _page_seo("core:terms")
    return render(request, "core/terms.html", {
        "meta_title": seo.meta_title if seo and seo.meta_title else None,
        "meta_description": seo.meta_description if seo and seo.meta_description else None,
        "meta_robots": seo.meta_robots if seo and seo.meta_robots else None,
    })


def privacy(request):
    seo = _page_seo("core:privacy")
    return render(request, "core/privacy.html", {
        "meta_title": seo.meta_title if seo and seo.meta_title else None,
        "meta_description": seo.meta_description if seo and seo.meta_description else None,
        "meta_robots": seo.meta_robots if seo and seo.meta_robots else None,
    })


def faq(request):
    seo = _page_seo("core:faq")
    return render(request, "core/faq.html", {
        "meta_title": seo.meta_title if seo and seo.meta_title else None,
        "meta_description": seo.meta_description if seo and seo.meta_description else None,
        "meta_robots": seo.meta_robots if seo and seo.meta_robots else None,
    })


def returns_policy(request):
    seo = _page_seo("core:returns")
    return render(request, "core/returns.html", {
        "meta_title": seo.meta_title if seo and seo.meta_title else None,
        "meta_description": seo.meta_description if seo and seo.meta_description else None,
        "meta_robots": seo.meta_robots if seo and seo.meta_robots else None,
    })


def cookies_policy(request):
    seo = _page_seo("core:cookies")
    return render(request, "core/cookies.html", {
        "meta_title": seo.meta_title if seo and seo.meta_title else None,
        "meta_description": seo.meta_description if seo and seo.meta_description else None,
        "meta_robots": seo.meta_robots if seo and seo.meta_robots else None,
    })


def contact(request):
    """
    Contact enterprise-ish:
    - honeypot (spam)
    - salvează în DB
    - email către suport (HTML + text) cu Reply-To = user
    - email confirmare către user (HTML + text)
    """
    site_settings = SiteSetting.objects.first()
    contact_to = getattr(settings, "SNOBISTIC_CONTACT_EMAIL", None) or (site_settings.contact_email if site_settings else "support@snobistic.ro")
    privacy_ver = getattr(settings, "PRIVACY_POLICY_VERSION", None) or (site_settings.privacy_policy_version if site_settings else "1.0")

    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            # anti-spam: honeypot trebuie gol
            if form.cleaned_data.get("honeypot"):
                messages.warning(request, "A apărut o eroare. Te rugăm să încerci din nou.")
                return redirect("core:contact")

            contact_msg: ContactMessage = form.save(commit=False)

            # meta info
            contact_msg.ip_address = _get_client_ip(request)
            contact_msg.user_agent = (request.META.get("HTTP_USER_AGENT", "") or "")[:2000]
            contact_msg.privacy_policy_version = privacy_ver

            # GDPR audit
            if contact_msg.consent:
                contact_msg.consent_at = timezone.now()

            if request.user.is_authenticated:
                contact_msg.user = request.user

            contact_msg.save()

            # email către suport
            subject = f"[Snobistic Contact] {contact_msg.subject}".replace("\r", " ").replace("\n", " ")
            ctx = {"m": contact_msg, "site_settings": site_settings}

            text_body = render_to_string("core/emails/contact_support.txt", ctx)
            html_body = render_to_string("core/emails/contact_support.html", ctx)

            msg = EmailMultiAlternatives(
                subject=subject,
                body=text_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[contact_to],
                reply_to=[contact_msg.email],  # ✅ reply direct la user
            )
            msg.attach_alternative(html_body, "text/html")

            # confirmare către user
            confirm_subject = "Am primit mesajul tău – Snobistic"
            confirm_text = render_to_string("core/emails/contact_confirmation.txt", ctx)
            confirm_html = render_to_string("core/emails/contact_confirmation.html", ctx)
            confirm = EmailMultiAlternatives(
                subject=confirm_subject,
                body=confirm_text,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[contact_msg.email],
            )
            confirm.attach_alternative(confirm_html, "text/html")

            try:
                msg.send(fail_silently=False)
                confirm.send(fail_silently=True)  # confirmarea nu trebuie să strice flow-ul
            except BadHeaderError:
                messages.error(request, "A apărut o eroare la trimiterea mesajului. Te rugăm să încerci din nou.")
                return redirect("core:contact")
            except Exception:
                # aici, ideal: logging + Sentry
                messages.error(request, "A apărut o eroare temporară. Te rugăm să încerci din nou.")
                return redirect("core:contact")

            messages.success(request, "Mesajul tău a fost trimis cu succes. Îți vom răspunde în cel mai scurt timp.")
            return redirect("core:contact")
    else:
        form = ContactForm()

    seo = _page_seo("core:contact")
    return render(request, "core/contact.html", {
        "form": form,
        "meta_title": seo.meta_title if seo and seo.meta_title else None,
        "meta_description": seo.meta_description if seo and seo.meta_description else None,
        "meta_robots": seo.meta_robots if seo and seo.meta_robots else None,
    })


def robots_txt(request):
    sitemap_url = request.build_absolute_uri(reverse("core:sitemap_xml"))
    content = (
        "User-agent: *\n"
        "Disallow: /admin/\n"
        "Disallow: /static/\n"
        f"Sitemap: {sitemap_url}\n"
    )
    return HttpResponse(content, content_type="text/plain")


def sitemap_xml(request):
    """
    Minimal pentru core.
    În producție, recomand să treci pe django.contrib.sitemaps (project-level),
    ca să agregi și produse/categorii/licitatii etc.
    """
    today = datetime.date.today()

    pages = [
        {"url": request.build_absolute_uri(reverse("core:home")), "lastmod": today, "changefreq": "daily", "priority": "1.0"},
        {"url": request.build_absolute_uri(reverse("core:about")), "lastmod": today, "changefreq": "monthly", "priority": "0.5"},
        {"url": request.build_absolute_uri(reverse("core:contact")), "lastmod": today, "changefreq": "monthly", "priority": "0.5"},
        {"url": request.build_absolute_uri(reverse("core:terms")), "lastmod": today, "changefreq": "yearly", "priority": "0.3"},
        {"url": request.build_absolute_uri(reverse("core:privacy")), "lastmod": today, "changefreq": "yearly", "priority": "0.3"},
        {"url": request.build_absolute_uri(reverse("core:faq")), "lastmod": today, "changefreq": "monthly", "priority": "0.4"},
        {"url": request.build_absolute_uri(reverse("core:returns")), "lastmod": today, "changefreq": "yearly", "priority": "0.4"},
        {"url": request.build_absolute_uri(reverse("core:cookies")), "lastmod": today, "changefreq": "yearly", "priority": "0.3"},
    ]

    xml = render_to_string("core/sitemap.xml", {"sitemap_pages": pages, "today": today})
    return HttpResponse(xml, content_type="application/xml")


# ===== Error pages (handlers în root urls.py) =====
def error_400(request, exception=None):
    return render(request, "errors/400.html", status=400)

def error_403(request, exception=None):
    return render(request, "errors/403.html", status=403)

def error_404(request, exception=None):
    return render(request, "errors/404.html", status=404)

def error_500(request):
    return render(request, "errors/500.html", status=500)
