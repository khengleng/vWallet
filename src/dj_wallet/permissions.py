from decimal import Decimal

from django.contrib.contenttypes.models import ContentType

from .compliance import ComplianceService
from .fraud import FraudService
from .models import WalletRoleAssignment
from .conf import wallet_settings


class PermissionDenied(Exception):
    pass


class PermissionPolicy:
    """
    Base permission policy interface.
    """

    def check(self, holder, wallet, action, amount, meta=None):
        raise NotImplementedError


class DefaultPermissionPolicy(PermissionPolicy):
    """
    Enforces role-based and balance-based rules + compliance/fraud checks.
    """

    def check(self, holder, wallet, action, amount, meta=None):
        meta = meta or {}
        amount = Decimal(str(amount))

        # Compliance gating
        profile = ComplianceService.get_profile(holder)
        if profile.is_suspended:
            raise PermissionDenied("account_suspended")

        if profile.status == profile.STATUS_REJECTED:
            raise PermissionDenied("kyc_rejected")

        if action in wallet_settings.COMPLIANCE_REQUIRE_KYC:
            if profile.status != profile.STATUS_VERIFIED:
                raise PermissionDenied("kyc_required")

        # Fraud heuristics
        allowed, reason = FraudService.evaluate(holder, action, amount, meta)
        if not allowed:
            raise PermissionDenied(reason)

        # Role-based limits (restrictive aggregation)
        ct = ContentType.objects.get_for_model(holder)
        roles = WalletRoleAssignment.objects.filter(
            holder_type=ct, holder_id=holder.pk
        ).select_related("role")

        max_withdraw = None
        max_transfer = None
        min_balance_required = Decimal("0")
        daily_limit = None
        monthly_limit = None

        for assignment in roles:
            role = assignment.role
            if role.max_withdraw_amount is not None:
                max_withdraw = (
                    role.max_withdraw_amount
                    if max_withdraw is None
                    else min(max_withdraw, role.max_withdraw_amount)
                )
            if role.max_transfer_amount is not None:
                max_transfer = (
                    role.max_transfer_amount
                    if max_transfer is None
                    else min(max_transfer, role.max_transfer_amount)
                )
            min_balance_required = max(min_balance_required, role.min_balance_required)
            if role.daily_outflow_limit is not None:
                daily_limit = (
                    role.daily_outflow_limit
                    if daily_limit is None
                    else min(daily_limit, role.daily_outflow_limit)
                )
            if role.monthly_outflow_limit is not None:
                monthly_limit = (
                    role.monthly_outflow_limit
                    if monthly_limit is None
                    else min(monthly_limit, role.monthly_outflow_limit)
                )

        # Balance-based checks
        if wallet.balance - amount < min_balance_required:
            raise PermissionDenied("min_balance_required")

        if action == "withdraw" and max_withdraw is not None and amount > max_withdraw:
            raise PermissionDenied("withdraw_role_limit")
        if action in {"transfer", "purchase"} and max_transfer is not None:
            if amount > max_transfer:
                raise PermissionDenied("transfer_role_limit")

        # Compliance limits
        if profile.daily_limit is not None:
            used = ComplianceService.daily_outflow(holder)
            if used + amount > profile.daily_limit:
                raise PermissionDenied("daily_limit_exceeded")
        if profile.monthly_limit is not None:
            used = ComplianceService.monthly_outflow(holder)
            if used + amount > profile.monthly_limit:
                raise PermissionDenied("monthly_limit_exceeded")

        if daily_limit is not None:
            used = ComplianceService.daily_outflow(holder)
            if used + amount > daily_limit:
                raise PermissionDenied("role_daily_limit_exceeded")
        if monthly_limit is not None:
            used = ComplianceService.monthly_outflow(holder)
            if used + amount > monthly_limit:
                raise PermissionDenied("role_monthly_limit_exceeded")

        return True
