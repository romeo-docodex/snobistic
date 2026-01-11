# payments/signals.py
from django.dispatch import Signal

# ✅ Events pentru integrare (wallet / notificări / analytics / audit)
payment_succeeded = Signal()  # kwargs: payment, order
payment_failed = Signal()     # kwargs: payment, order
payment_canceled = Signal()   # kwargs: payment, order

# ✅ Refund event (wallet app poate asculta și credita user-ul)
refund_succeeded = Signal()   # kwargs: refund, payment, order
