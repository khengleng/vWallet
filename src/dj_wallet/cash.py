from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from .models import CashAgent, CashRequest, Wallet
from .services import WalletService


class CashService:
    """
    Cash-in / Cash-out flow with approval.
    """

    @staticmethod
    def get_agent(holder):
        ct = ContentType.objects.get_for_model(holder)
        return CashAgent.objects.filter(holder_type=ct, holder_id=holder.pk).first()

    @classmethod
    def request_cashin(cls, holder, agent, amount, meta=None):
        return CashRequest.objects.create(
            holder_type=ContentType.objects.get_for_model(holder),
            holder_id=holder.pk,
            agent=agent,
            amount=amount,
            type=CashRequest.TYPE_CASHIN,
            status=CashRequest.STATUS_PENDING,
            meta=meta or {},
        )

    @classmethod
    def request_cashout(cls, holder, agent, amount, meta=None):
        return CashRequest.objects.create(
            holder_type=ContentType.objects.get_for_model(holder),
            holder_id=holder.pk,
            agent=agent,
            amount=amount,
            type=CashRequest.TYPE_CASHOUT,
            status=CashRequest.STATUS_PENDING,
            meta=meta or {},
        )

    @classmethod
    def approve(cls, cash_request):
        if cash_request.status != CashRequest.STATUS_PENDING:
            return cash_request

        holder = cash_request.holder
        ct = ContentType.objects.get_for_model(holder)
        wallet, _ = Wallet.objects.get_or_create(
            holder_type=ct, holder_id=holder.pk, slug="default"
        )
        if cash_request.type == CashRequest.TYPE_CASHIN:
            WalletService.deposit(wallet, cash_request.amount, meta={"cash": True})
        else:
            WalletService.withdraw(
                wallet, cash_request.amount, meta={"cash": True}, actor=holder
            )

        cash_request.status = CashRequest.STATUS_APPROVED
        cash_request.approved_at = timezone.now()
        cash_request.save(update_fields=["status", "approved_at"])
        return cash_request

    @classmethod
    def reject(cls, cash_request, reason=""):
        if cash_request.status != CashRequest.STATUS_PENDING:
            return cash_request
        cash_request.status = CashRequest.STATUS_REJECTED
        cash_request.rejected_at = timezone.now()
        if reason:
            cash_request.meta = cash_request.meta or {}
            cash_request.meta["reason"] = reason
        cash_request.save(update_fields=["status", "rejected_at", "meta"])
        return cash_request
