# accounts/views.py

from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import (
    authenticate, login, logout, update_session_auth_hash
)
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.views.generic import FormView, TemplateView, View
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from allauth.account.views import SignupView
from django.template.loader import render_to_string
from django.core.mail import EmailMessage

from .forms import (
    RegisterForm, ResendActivationForm, ReactivateForm, ChangeEmailForm,
    LoginForm, TwoFactorForm, CustomPasswordChangeForm,
    CustomUserForm, ProfileForm, AddressForm
)
from .models import CustomUser, UserAddress
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
        messages.success(request, "Cont activat cu succes.")
        return redirect("accounts:profile")

    return render(request, "accounts/auth/email_activate.html", {"invalid": True})


class ResendActivationView(FormView):
    template_name = "accounts/auth/resend_activation.html"
    form_class = ResendActivationForm
    success_url = reverse_lazy("accounts:login")

    def form_valid(self, form):
        email = form.cleaned_data["email"]
        try:
            user = CustomUser.objects.get(email=email, is_active=False)
            send_activation_email(self.request, user)
            messages.success(self.request, "Email de activare retrimis.")
        except CustomUser.DoesNotExist:
            messages.error(self.request, "Nu am găsit niciun cont inactiv cu acest email.")
        return super().form_valid(form)


class ReactivateAccountView(FormView):
    template_name = "accounts/auth/reactivate.html"
    form_class = ReactivateForm
    success_url = reverse_lazy("accounts:profile")

    def form_valid(self, form):
        email = form.cleaned_data["email"]
        password = form.cleaned_data["password"]
        user = authenticate(self.request, username=email, password=password)
        if user and user.deleted_at is not None:
            user.reactivate()
            login(self.request, user)
            messages.success(self.request, "Cont reactivat cu succes.")
            return super().form_valid(form)
        form.add_error(None, "Date invalide sau cont neexistent ori deja activ.")
        return self.form_invalid(form)


class LoginView(FormView):
    template_name = "accounts/auth/login.html"
    form_class = LoginForm
    success_url = reverse_lazy("accounts:profile")

    def form_valid(self, form):
        email = form.cleaned_data["email"]
        password = form.cleaned_data["password"]
        user = authenticate(self.request, username=email, password=password)
        if user:
            login(self.request, user)
            return super().form_valid(form)
        form.add_error(None, "Date de autentificare invalide.")
        return self.form_invalid(form)


def logout_view(request):
    logout(request)
    return redirect("accounts:login")


class TwoFactorView(FormView):
    template_name = "accounts/auth/two_factor.html"
    form_class = TwoFactorForm
    success_url = reverse_lazy("accounts:profile")

    def form_valid(self, form):
        code = form.cleaned_data["code"]
        # TODO: replace placeholder with real django-two-factor-auth
        if code == "123456":
            uid = self.request.session.pop("pre_2fa_user_id", None)
            user = get_object_or_404(CustomUser, pk=uid)
            login(self.request, user)
            return super().form_valid(form)
        form.add_error("code", "Cod 2FA invalid.")
        return self.form_invalid(form)


class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = "accounts/profile/profile.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["user_form"] = CustomUserForm(instance=self.request.user)
        ctx["profile_form"] = ProfileForm(instance=self.request.user.profile)
        ctx["address_form"] = AddressForm()
        ctx["addresses"] = UserAddress.objects.filter(user=self.request.user)
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


class ChangeEmailView(LoginRequiredMixin, FormView):
    template_name = "accounts/profile/change_email.html"
    form_class = ChangeEmailForm
    success_url = reverse_lazy("accounts:login")

    def form_valid(self, form):
        new_email = form.cleaned_data["new_email"]
        password = form.cleaned_data["password"]
        user = authenticate(self.request, username=self.request.user.email, password=password)
        if user:
            # mark unverified and inactive until reactivated
            self.request.user.email = new_email
            self.request.user.verified_email = False
            self.request.user.is_active = False
            self.request.user.save()
            send_activation_email(self.request, self.request.user)
            logout(self.request)
            messages.success(self.request, "Confirmă noul email din inbox.")
            return super().form_valid(form)

        form.add_error("password", "Parolă incorectă.")
        return self.form_invalid(form)


@require_POST
@login_required
def delete_address_view(request, address_id):
    addr = get_object_or_404(UserAddress, id=address_id, user=request.user)
    addr.delete()
    messages.success(request, "Adresa a fost ștearsă.")
    return redirect("accounts:profile")


@require_POST
@login_required
def set_default_address_view(request, address_id):
    addr = get_object_or_404(UserAddress, id=address_id, user=request.user)
    UserAddress.objects.filter(
        user=request.user,
        address_type=addr.address_type
    ).update(is_default=False)
    addr.is_default = True
    addr.save()
    messages.success(request, f"{addr.get_address_type_display()} setată ca implicită.")
    return redirect("accounts:profile")


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


# Password reset flow (using Django’s built-in views)

from django.contrib.auth.views import (
    PasswordResetView, PasswordResetDoneView,
    PasswordResetConfirmView, PasswordResetCompleteView
)

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
