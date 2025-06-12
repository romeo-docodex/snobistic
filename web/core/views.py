from django.shortcuts import render
from django.core.mail import send_mail
from django.contrib import messages
from .forms import ContactForm


# ========================
# HOMEPAGE
# ========================
def homepage_view(request):
    return render(request, 'core/home.html')


# ========================
# DESPRE NOI
# ========================
def about_view(request):
    return render(request, 'core/about.html')


# ========================
# CONTACT
# ========================
def contact_view(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            subject = "Mesaj nou de pe Snobistic"
            body = f"{form.cleaned_data['name']} ({form.cleaned_data['email']}):\n\n{form.cleaned_data['message']}"
            send_mail(subject, body, form.cleaned_data['email'], ['support@snobistic.com'])
            messages.success(request, "Mesajul a fost trimis.")
            form = ContactForm()  # reset form
    else:
        form = ContactForm()
    return render(request, 'core/contact.html', {'form': form})
