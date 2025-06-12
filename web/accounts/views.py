# accounts/views.py

from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import PasswordResetView, PasswordResetConfirmView, PasswordResetDoneView, PasswordResetCompleteView
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.views import View
from django.views.decorators.http import require_POST
from django.views.generic import FormView, UpdateView, TemplateView
from django_otp.decorators import otp_required
from allauth.account.views import SignupView

from .forms import (
    RegisterForm, ProfileForm, CustomUserForm,
    AddressForm, CustomPasswordChangeForm, TwoFactorForm,
    ResendActivationForm, ChangeEmailForm
)
from .models import CustomUser, UserProfile, UserAddress, EmailToken
from .tokens import account_activation_token


class AccountSignupView(SignupView):
    template_name = "accounts/auth/register.html"
    form_class = RegisterForm
    success_url = reverse_lazy("accounts:login")


def activate_account(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = CustomUser.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, CustomUser.DoesNotExist):
        user = None

    if user and account_activation_token.check_token(user, token):
        user.is_active = True
        user.verified_email = True
        user.save()
        login(request, user)
        messages.success(request, "Cont activat.")
        return redirect("accounts:profile")
    return render(request, "accounts/auth/email_activate.html", {"invalid": True})


class ResendActivationView(FormView):
    template_name = "accounts/auth/resend_activation.html"
    form_class = ResendActivationForm
    success_url = reverse_lazy("accounts:login")

    def form_valid(self, form):
        user = CustomUser.objects.get(email=form.cleaned_data["email"], is_active=False)
        send_activation_email(self.request, user)
        messages.success(self.request, "Email de activare retrimis.")
        return super().form_valid(form)


def send_activation_email(request, user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = account_activation_token.make_token(user)
    subject = "Activează contul tău Snobistic"
    message = render_to_string("accounts/auth/email_activate.html", {
        "user": user,
        "uid": uid,
        "token": token,
    })
    EmailMessage(subject, message, to=[user.email]).send()


class LoginView(View):
    template_name = "accounts/auth/login.html"

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        user = authenticate(request, username=request.POST.get("email"), password=request.POST.get("password"))
        if user:
            login(request, user)
            return redirect("accounts:profile")
        messages.error(request, "Date de autentificare invalide.")
        return render(request, self.template_name)


def logout_view(request):
    logout(request)
    return redirect("accounts:login")


class TwoFactorView(FormView):
    template_name = "accounts/auth/two_factor.html"
    form_class = TwoFactorForm

    def form_valid(self, form):
        code = form.cleaned_data["code"]
        # Aici integrați django-two-factor-auth real
        if code == "123456":
            user_id = self.request.session.pop("pre_2fa_user_id", None)
            user = get_object_or_404(CustomUser, pk=user_id)
            login(self.request, user)
            return redirect("accounts:profile")
        messages.error(self.request, "Cod greșit.")
        return self.form_invalid(form)


class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = "accounts/profile/profile.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["user_form"] = CustomUserForm(instance=self.request.user)
        ctx["profile_form"] = ProfileForm(instance=self.request.user.profile)
        ctx["address_form"] = AddressForm()
        ctx["addresses"] = self.request.user.addresses.all()
        return ctx

    def post(self, request, *args, **kwargs):
        user_form = CustomUserForm(request.POST, instance=request.user)
        profile_form = ProfileForm(request.POST, request.FILES, instance=request.user.profile)
        address_form = AddressForm(request.POST)
        if user_form.is_valid() and profile_form.is_valid() and address_form.is_valid():
            user_form.save()
            profile_form.save()
            addr = address_form.save(commit=False)
            addr.user = request.user
            addr.save()
            messages.success(request, "Datele au fost actualizate.")
            return redirect("accounts:profile")
        return self.get(request, *args, **kwargs)


class ChangePasswordView(LoginRequiredMixin, FormView):
    template_name = "accounts/passwords/change_password.html"
    form_class = CustomPasswordChangeForm
    success_url = reverse_lazy("accounts:profile")

    def form_valid(self, form):
        user = form.save()
        update_session_auth_hash(self.request, user)
        messages.success(self.request, "Parola a fost schimbată.")
        return super().form_valid(form)

@login_required
@require_POST
def delete_address_view(request, address_id):
    addr = get_object_or_404(UserAddress, id=address_id, user=request.user)
    addr.delete()
    messages.success(request, "Adresa a fost ștearsă.")
    return redirect("accounts:profile")

@login_required
@require_POST
def set_default_address_view(request, address_id):
    addr = get_object_or_404(UserAddress, id=address_id, user=request.user)
    UserAddress.objects.filter(user=request.user, address_type=addr.address_type).update(is_default=False)
    addr.is_default = True
    addr.save()
    messages.success(request, f"{addr.get_address_type_display()} setată ca implicită.")
    return redirect("accounts:profile")


class DeleteAccountView(LoginRequiredMixin, View):
    def get(self, request):
        return render(request, "accounts/profile/account_deletion_confirm.html")

    def post(self, request):
        request.user.is_active = False
        request.user.save()
        logout(request)
        messages.success(request, "Contul tău a fost dezactivat.")
        return redirect("accounts:login")


# === Password Reset flows via built-in CBV ===

class CustomPasswordResetView(PasswordResetView):
    template_name = "accounts/passwords/password_reset_form.html"
    email_template_name = "accounts/passwords/password_reset_email.html"
    subject_template_name = "accounts/passwords/password_reset_subject.txt"
    success_url = reverse_lazy("accounts:password_reset_done")

class CustomPasswordResetDoneView(PasswordResetDoneView):
    template_name = "accounts/passwords/password_reset_done.html"

class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = "accounts/passwords/password_reset_confirm.html"
    success_url = reverse_lazy("accounts:password_reset_complete")

class CustomPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = "accounts/passwords/password_reset_complete.html"
