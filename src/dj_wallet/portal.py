from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.db.models import Count, Sum
from django.shortcuts import render

from .models import CashAgent, CashRequest, ChainAnchor, Transaction, Wallet


@login_required
def portal_view(request):
    context = {
        "balance": None,
        "tx_count": 0,
        "cash_pending": 0,
        "anchors_pending": 0,
        "recent_cash": [],
    }

    if request.user.is_authenticated:
        ct = ContentType.objects.get_for_model(request.user)
        wallet = Wallet.objects.filter(
            holder_type=ct, holder_id=request.user.pk, slug="default"
        ).first()
        if wallet:
            context["balance"] = wallet.balance
            context["tx_count"] = (
                Transaction.objects.filter(wallet=wallet).count()
            )

        context["cash_pending"] = CashRequest.objects.filter(
            holder_type=ct,
            holder_id=request.user.pk,
            status=CashRequest.STATUS_PENDING,
        ).count()

        context["anchors_pending"] = ChainAnchor.objects.filter(
            status=ChainAnchor.STATUS_PENDING
        ).count()

        context["recent_cash"] = list(
            CashRequest.objects.filter(holder_type=ct, holder_id=request.user.pk)
            .order_by("-created_at")[:5]
            .values("type", "status", "amount", "created_at")
        )

        user_roles = []
        from .models import WalletRoleAssignment

        for assignment in WalletRoleAssignment.objects.filter(
            holder_type=ct, holder_id=request.user.pk
        ).select_related("role"):
            user_roles.append(assignment.role.slug)
        context["user_roles"] = user_roles

        if "ops" in user_roles:
            context["ops_cash_pending"] = CashRequest.objects.filter(
                status=CashRequest.STATUS_PENDING
            ).count()
            context["ops_pending_list"] = list(
                CashRequest.objects.filter(status=CashRequest.STATUS_PENDING)
                .order_by("-created_at")[:10]
                .values("id", "type", "amount", "holder_id", "created_at")
            )
        if "agent" in user_roles:
            agent = CashAgent.objects.filter(holder_type=ct, holder_id=request.user.pk).first()
            if agent:
                context["agent_cash_pending"] = CashRequest.objects.filter(
                    agent=agent, status=CashRequest.STATUS_PENDING
                ).count()
                context["agent_pending_list"] = list(
                    CashRequest.objects.filter(agent=agent, status=CashRequest.STATUS_PENDING)
                    .order_by("-created_at")[:10]
                    .values("id", "type", "amount", "holder_id", "created_at")
                )
    else:
        # Show global stats for unauthenticated users (minimal)
        context["anchors_pending"] = ChainAnchor.objects.filter(
            status=ChainAnchor.STATUS_PENDING
        ).count()

    return render(request, "dj_wallet/portal.html", context)
