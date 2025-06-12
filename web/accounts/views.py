from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib import messages
from django.urls import reverse, reverse_lazy
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.template.loader import render_to_string
from django.core.mail import EmailMessage
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.contrib.auth.forms import AuthenticationForm

from .forms import (
    RegisterForm, ProfileForm, CustomUserForm,
    AddressForm, CustomPasswordChangeForm,
    TwoFactorForm, ResendActivationForm, ChangeEmailForm
)
from .models import CustomUser, UserAddress
from .tokens import account_activation_token


def register_view(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False
            user.save()
            # profil şi portofel sunt create de semnal
            send_activation_email(request, user)
            messages.success(request, "Cont creat. Verifică email-ul pentru activare.")
            return redirect('accounts:login')
    else:
        form = RegisterForm()
    return render(request, 'accounts/auth/register.html', {'form': form})


def send_activation_email(request, user):
    subject = "Activează contul tău Snobistic"
    context = {
        'user': user,
        'uid': urlsafe_base64_encode(force_bytes(user.pk)),
        'token': account_activation_token.make_token(user),
    }
    message = render_to_string('accounts/auth/email_activate.html', context)
    EmailMessage(subject, message, to=[user.email]).send()


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
        return redirect('accounts:profile')
    return render(request, 'accounts/auth/email_activate.html', {'invalid': True})


def resend_activation_view(request):
    if request.method == 'POST':
        form = ResendActivationForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            try:
                user = CustomUser.objects.get(email=email, is_active=False)
                send_activation_email(request, user)
                messages.success(request, "Email de activare retrimis.")
                return redirect('accounts:login')
            except CustomUser.DoesNotExist:
                messages.error(request, "Nu am găsit cont inactiv cu acest email.")
    else:
        form = ResendActivationForm()
    return render(request, 'accounts/auth/resend_activation.html', {'form': form})


def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            if user.two_fa_enabled:
                request.session['pre_2fa_user_id'] = user.pk
                return redirect('accounts:two_factor')
            login(request, user)
            return redirect('accounts:profile')
    else:
        form = AuthenticationForm()
    return render(request, 'accounts/auth/login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('accounts:login')


def two_factor_view(request):
    if request.method == 'POST':
        form = TwoFactorForm(request.POST)
        if form.is_valid() and form.cleaned_data['code'] == '123456':
            user_id = request.session.pop('pre_2fa_user_id', None)
            if user_id:
                login(request, get_object_or_404(CustomUser, pk=user_id))
                return redirect('accounts:profile')
        messages.error(request, "Cod 2FA greșit.")
    else:
        form = TwoFactorForm()
    return render(request, 'accounts/auth/two_factor.html', {'form': form})


@login_required
def profile_view(request):
    if request.method == 'POST':
        uform = CustomUserForm(request.POST, instance=request.user)
        pform = ProfileForm(request.POST, request.FILES, instance=request.user.profile)
        aform = AddressForm(request.POST)
        if uform.is_valid() and pform.is_valid() and aform.is_valid():
            uform.save()
            pform.save()
            addr = aform.save(commit=False)
            addr.user = request.user
            addr.save()
            messages.success(request, "Profil actualizat.")
            return redirect('accounts:profile')
    else:
        uform = CustomUserForm(instance=request.user)
        pform = ProfileForm(instance=request.user.profile)
        aform = AddressForm()
    addrs = UserAddress.objects.filter(user=request.user)
    return render(request, 'accounts/profile/profile.html', {
        'user_form': uform,
        'profile_form': pform,
        'address_form': aform,
        'addresses': addrs,
    })


@login_required
def change_password_view(request):
    if request.method == 'POST':
        form = CustomPasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            form.save()
            update_session_auth_hash(request, request.user)
            messages.success(request, "Parola schimbată.")
            return redirect('accounts:profile')
    else:
        form = CustomPasswordChangeForm(request.user)
    return render(request, 'accounts/passwords/change_password.html', {'form': form})


@login_required
def change_email_view(request):
    if request.method == 'POST':
        form = ChangeEmailForm(request.POST)
        if form.is_valid():
            new = form.cleaned_data['new_email']
            pwd = form.cleaned_data['password']
            user = authenticate(request, username=request.user.email, password=pwd)
            if user:
                request.user.email = new
                request.user.verified_email = False
                request.user.is_active = False
                request.user.save()
                send_activation_email(request, request.user)
                logout(request)
                messages.success(request, "Confirmă noul email din inbox.")
                return redirect('accounts:login')
            messages.error(request, "Parolă incorectă.")
    else:
        form = ChangeEmailForm()
    return render(request, 'accounts/profile/change_email.html', {'form': form})


@login_required
@require_http_methods(["POST"])
def delete_address_view(request, address_id):
    addr = get_object_or_404(UserAddress, id=address_id, user=request.user)
    addr.delete()
    messages.success(request, "Adresă ștearsă.")
    return redirect('accounts:profile')


@login_required
@require_http_methods(["POST"])
def set_default_address_view(request, address_id):
    addr = get_object_or_404(UserAddress, id=address_id, user=request.user)
    UserAddress.objects.filter(user=request.user, address_type=addr.address_type).update(is_default=False)
    addr.is_default = True
    addr.save()
    messages.success(request, f"{addr.get_address_type_display()} setată implicit.")
    return redirect('accounts:profile')


@login_required
def account_deletion_view(request):
    if request.method == 'POST':
        request.user.is_active = False
        request.user.save()
        logout(request)
        messages.success(request, "Cont dezactivat.")
        return redirect('accounts:login')
    return render(request, 'accounts/profile/account_deletion_confirm.html')
