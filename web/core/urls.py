# core/urls.py
from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    # Pagina principală: /
    path("", views.home, name="home"),

    # Pagini statice principale
    path("despre-noi/", views.about, name="about"),
    path("termeni-si-conditii/", views.terms, name="terms"),
    path("politica-confidentialitate/", views.privacy, name="privacy"),

    # FAQ / Ajutor
    path("intrebari-frecvente/", views.faq, name="faq"),

    # Politici suplimentare
    path("politica-retur/", views.returns_policy, name="returns"),
    path("politica-cookies/", views.cookies_policy, name="cookies"),

    # Contact
    path("contact/", views.contact, name="contact"),

    # SEO tehnic
    path("robots.txt", views.robots_txt, name="robots_txt"),
    path("sitemap.xml", views.sitemap_xml, name="sitemap_xml"),
]
