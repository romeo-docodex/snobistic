from django.db import models
from django.conf import settings
from django.utils import timezone


class Wallet(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wallet')
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Portofel: {self.user.email} - {self.balance} RON"

    def credit(self, amount, type='topup', description=''):
        self.balance += amount
        self.save()
        Transaction.objects.create(
            wallet=self,
            type=type,
            amount=amount,
            description=description,
            timestamp=timezone.now()
        )

    def debit(self, amount, type='payment', description=''):
        if self.balance >= amount:
            self.balance -= amount
            self.save()
            Transaction.objects.create(
                wallet=self,
                type=type,
                amount=-amount,
                description=description,
                timestamp=timezone.now()
            )
            return True
        return False


class Transaction(models.Model):
    TRANSACTION_TYPES = [
        ('topup', 'Alimentare'),
        ('payment', 'Plată'),
        ('refund', 'Ramburs'),
        ('payout', 'Retragere'),
        ('internal', 'Transfer intern'),
    ]

    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='transactions')
    type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True)
    timestamp = models.DateTimeField()

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.get_type_display()} - {self.amount} RON ({self.timestamp:%d.%m.%Y %H:%M})"
