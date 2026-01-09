# accounts/management/commands/bootstrap_roles.py

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from accounts.constants import GROUP_SHOP_MANAGER


class Command(BaseCommand):
    help = "Bootstrap roles/groups for Snobistic (Shop Manager + permissions)."

    DEFAULT_PERMS = [
        # accounts KYC
        ("accounts", "kycrequest", "view_kycrequest"),
        ("accounts", "kycrequest", "change_kycrequest"),
        ("accounts", "kycdocument", "view_kycdocument"),
        ("accounts", "kycdocument", "change_kycdocument"),
        # accounts basic (optional)
        ("accounts", "profile", "view_profile"),
        ("accounts", "profile", "change_profile"),
        # catalog approvals / moderation (best-effort; ignore if missing)
        ("catalog", "product", "view_product"),
        ("catalog", "product", "change_product"),
    ]

    def _get_perm(self, app_label: str, model: str, codename: str):
        try:
            ct = ContentType.objects.get(app_label=app_label, model=model)
        except ContentType.DoesNotExist:
            return None
        return Permission.objects.filter(content_type=ct, codename=codename).first()

    @transaction.atomic
    def handle(self, *args, **options):
        group, created = Group.objects.get_or_create(name=GROUP_SHOP_MANAGER)
        self.stdout.write(
            self.style.SUCCESS(f"Group '{GROUP_SHOP_MANAGER}' {'created' if created else 'loaded'} (id={group.id}).")
        )

        added = 0
        missing = []

        for app_label, model, codename in self.DEFAULT_PERMS:
            perm = self._get_perm(app_label, model, codename)
            if not perm:
                missing.append(f"{app_label}.{codename}")
                continue
            if not group.permissions.filter(id=perm.id).exists():
                group.permissions.add(perm)
                added += 1

        group.save()

        if added:
            self.stdout.write(self.style.SUCCESS(f"Added {added} permissions to '{GROUP_SHOP_MANAGER}'."))

        if missing:
            self.stdout.write(
                self.style.WARNING(
                    "Some permissions/content types were not found (ok if apps/models not installed yet):\n- "
                    + "\n- ".join(missing)
                )
            )

        self.stdout.write(self.style.SUCCESS("Done."))
