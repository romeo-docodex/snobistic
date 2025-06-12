from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.crypto import salted_hmac
from django.utils import timezone
import six


class AccountActivationTokenGenerator(PasswordResetTokenGenerator):
    """
    Token generator pentru activarea contului via email.
    Compatibil cu uidb64 și django.contrib.auth.views.
    """

    def _make_hash_value(self, user, timestamp):
        return (
            six.text_type(user.pk) +
            six.text_type(timestamp) +
            six.text_type(user.verified_email)
        )


account_activation_token = AccountActivationTokenGenerator()
