from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import TopUpForm, PayoutForm, TransactionFilterForm
from .models import Wallet, Transaction
from django.utils import timezone


@login_required
def wallet_overview_view(request):
    wallet = request.user.wallet
    return render(request, 'wallet/wallet_overview.html', {
        'wallet': wallet
    })


@login_required
def transaction_history_view(request):
    wallet = request.user.wallet
    transactions = wallet.transactions.all()

    form = TransactionFilterForm(request.GET or None)
    if form.is_valid():
        t_type = form.cleaned_data.get('type')
        start = form.cleaned_data.get('start_date')
        end = form.cleaned_data.get('end_date')

        if t_type:
            transactions = transactions.filter(type=t_type)
        if start:
            transactions = transactions.filter(timestamp__gte=start)
        if end:
            transactions = transactions.filter(timestamp__lte=end)

    return render(request, 'wallet/transaction_history.html', {
        'wallet': wallet,
        'transactions': transactions,
        'form': form
    })


@login_required
def topup_view(request):
    if request.method == 'POST':
        form = TopUpForm(request.POST)
        if form.is_valid():
            amount = form.cleaned_data['amount']
            description = form.cleaned_data['description'] or 'Alimentare manuală'
            request.user.wallet.credit(amount, 'topup', description)
            messages.success(request, f"Portofel alimentat cu {amount} RON.")
            return redirect('wallet_overview')
    else:
        form = TopUpForm()

    return render(request, 'wallet/topup.html', {'form': form})


@login_required
def payout_view(request):
    if request.method == 'POST':
        form = PayoutForm(request.POST)
        if form.is_valid():
            amount = form.cleaned_data['amount']
            iban = form.cleaned_data['iban']

            if request.user.wallet.debit(amount, 'payout', f"Retragere către {iban}"):
                messages.success(request, f"{amount} RON vor fi transferați către {iban}.")
                # aici poate fi adăugat un log / email pentru admin
                return redirect('wallet_overview')
            else:
                messages.error(request, "Fonduri insuficiente.")
    else:
        form = PayoutForm()

    return render(request, 'wallet/payout.html', {'form': form})
