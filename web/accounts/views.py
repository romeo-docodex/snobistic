# web/accounts/views.py
import uuid
from django.contrib import messages
from django.contrib.auth import (
    login, logout, authenticate, update_session_auth_hash
)
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import (
    PasswordResetView, PasswordResetDoneView,
    PasswordResetConfirmView, PasswordResetCompleteView
)
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.views import View
from django.views.generic import FormView, TemplateView
from django.views.decorators.http import require_POST
from allauth.account.views import SignupView
from django.template.loader import render_to_string
from django.core.mail import EmailMessage

from .forms import (
    RegisterForm, ProfileForm, CustomUserForm,
    AddressForm, CustomPasswordChangeForm, TwoFactorForm,
    ResendActivationForm, ChangeEmailForm, ReactivateForm
)
from .models import CustomUser, UserProfile, EmailToken, UserAddress
from .tokens import account_activation_token


def _send_activation_email(request, user, purpose='activation'):
    token = uuid.uuid4().hex
    EmailToken.objects.create(user=user, token=token, purpose=purpose)
    uid  = urlsafe_base64_encode(force_bytes(user.pk))
    link = request.build_absolute_uri(
        reverse_lazy("accounts:activate", args=[uid, token])
    )
    subject = {
        'activation':     "Activează contul tău Snobistic",
        'email_change':   "Confirmă noul email Snobistic",
    }[purpose]
    template = "accounts/auth/email_activate.html"
    ctx = {'user': user, 'activation_link': link}
    EmailMessage(subject, render_to_string(template, ctx), to=[user.email]).send()


class AccountSignupView(SignupView):
    template_name = "accounts/auth/register.html"
    form_class    = RegisterForm
    success_url   = reverse_lazy("accounts:login")


def activate_account(request, uidb64, token):
    try:
        uid    = force_str(urlsafe_base64_decode(uidb64))
        user   = CustomUser.objects.get(pk=uid)
        etoken = EmailToken.objects.get(user=user, token=token, purpose='activation', used=False)
    except Exception:
        messages.error(request, "Link invalid.")
        return redirect("accounts:resend_activation")

    if not etoken.is_expired():
        user.is_active      = True
        user.verified_email = True
        user.save()
        etoken.used = True
        etoken.save()
        login(request, user)
        messages.success(request, "Cont activat cu succes.")
        return redirect("accounts:profile")
    messages.error(request, "Link expirat.")
    return redirect("accounts:resend_activation")


class ResendActivationView(FormView):
    template_name = "accounts/auth/resend_activation.html"
    form_class    = ResendActivationForm
    success_url   = reverse_lazy("accounts:login")

    def form_valid(self, form):
        email = form.cleaned_data['email']
        user  = CustomUser.objects.filter(email=email, is_active=False).first()
        if user:
            _send_activation_email(self.request, user)
            messages.success(self.request, "Email de activare retrimis.")
        else:
            messages.error(self.request, "Cont inactiv negăsit.")
        return super().form_valid(form)


class ReactivateAccountView(FormView):
    template_name = "accounts/auth/reactivate_account.html"
    form_class    = ReactivateForm
    success_url   = reverse_lazy("accounts:login")

    def form_valid(self, form):
        email = form.cleaned_data['email']
        user  = CustomUser.objects.get(email=email, deleted_at__isnull=False)
        user.reactivate()
        messages.success(self.request, "Cont reactivat. Verifică email-ul.")
        _send_activation_email(self.request, user)
        return super().form_valid(form)


class LoginView(View):
    template_name = "accounts/auth/login.html"

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        user = authenticate(
            request,
            username=request.POST.get("email"),
            password=request.POST.get("password")
        )
        if user:
            if user.two_fa_enabled:
                request.session['pre_2fa_user_id'] = user.pk
                return redirect("accounts:two_factor")
            login(request, user)
            return redirect("accounts:profile")
        messages.error(request, "Date invalide.")
        return render(request, self.template_name)


def logout_view(request):
    logout(request)
    return redirect("accounts:login")


class TwoFactorView(FormView):
    template_name = "accounts/auth/two_factor.html"
    form_class    = TwoFactorForm

    def form_valid(self, form):
        code = form.cleaned_data['code']
        if code == "123456":
            uid  = self.request.session.pop("pre_2fa_user_id", None)
            user = get_object_or_404(CustomUser, pk=uid)
            login(self.request, user)
            return redirect("accounts:profile")
        messages.error(self.request, "Cod greșit.")
        return super().form_invalid(form)


class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = "accounts/profile/profile.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update({
            "user_form":    CustomUserForm(instance=self.request.user),
            "profile_form": ProfileForm(instance=self.request.user.profile),
            "address_form": AddressForm(),
            "addresses":    self.request.user.addresses.all(),
        })
        return ctx

    def post(self, request, *args, **kwargs):
        uform = CustomUserForm(request.POST, instance=request.user)
        pform = ProfileForm(request.POST, request.FILES, instance=request.user.profile)
        aform = AddressForm(request.POST)
        if uform.is_valid() and pform.is_valid() and aform.is_valid():
            uform.save()
            pform.save()
            addr = aform.save(commit=False)
            addr.user = request.user
            if addr.is_default:
                request.user.addresses.filter(address_type=addr.address_type).update(is_default=False)
            addr.save()
            messages.success(request, "Date salvate.")
            return redirect("accounts:profile")
        return self.get(request, *args, **kwargs)


class ChangePasswordView(LoginRequiredMixin, FormView):
    template_name = "accounts/passwords/change_password.html"
    form_class    = CustomPasswordChangeForm
    success_url   = reverse_lazy("accounts:profile")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # PasswordChangeForm needs the current user
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        user = form.save()
        update_session_auth_hash(self.request, user)
        messages.success(self.request, "Parola a fost schimbată.")
        return super().form_valid(form)


class ChangeEmailView(LoginRequiredMixin, FormView):
    template_name = "accounts/profile/change_email.html"
    form_class    = ChangeEmailForm
    success_url   = reverse_lazy("accounts:login")

    def form_valid(self, form):
        new  = form.cleaned_data["new_email"]
        pwd  = form.cleaned_data["password"]
        user = authenticate(self.request, username=self.request.user.email, password=pwd)
        if user:
            self.request.user.email = new
            self.request.user.is_active = False
            self.request.user.verified_email = False
            self.request.user.save()
            messages.success(self.request, "Confirmă noul email din inbox.")
            _send_activation_email(self.request, self.request.user, purpose='email_change')
            logout(self.request)
            return super().form_valid(form)
        messages.error(self.request, "Parolă incorectă.")
        return super().form_invalid(form)


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
    request.user.addresses.filter(address_type=addr.address_type).update(is_default=False)
    addr.is_default = True
    addr.save()
    messages.success(request, f"{addr.get_address_type_display()} implicită.")
    return redirect("accounts:profile")


class DeleteAccountView(LoginRequiredMixin, View):
    def get(self, request):
        return render(request, "accounts/profile/account_deletion_confirm.html")

    def post(self, request):
        request.user.delete()
        logout(request)
        messages.success(request, "Cont dezactivat.")
        return redirect("accounts:login")


# password‐reset CBVs below
class CustomPasswordResetView(PasswordResetView):
    template_name       = "accounts/passwords/password_reset_form.html"
    email_template_name = "accounts/passwords/password_reset_email.html"
    subject_template_name = "accounts/passwords/password_reset_subject.txt"
    success_url         = reverse_lazy("accounts:password_reset_done")


class CustomPasswordResetDoneView(PasswordResetDoneView):
    template_name = "accounts/passwords/password_reset_done.html"


class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = "accounts/passwords/password_reset_confirm.html"
    success_url   = reverse_lazy("accounts:password_reset_complete")


class CustomPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = "accounts/passwords/password_reset_complete.html"
