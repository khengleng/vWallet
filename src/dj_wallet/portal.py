from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.shortcuts import render

from .models import CashAgent, CashRequest, ChainAnchor, Transaction, Wallet


def _base_context(request):
    context = {
        "balance": None,
        "tx_count": 0,
        "cash_pending": 0,
        "anchors_pending": 0,
        "recent_cash": [],
        "recent_transactions": [],
        "anchors_recent": [],
        "wallet_uuid": None,
        "user_roles": [],
    }

    if not request.user.is_authenticated:
        context["anchors_pending"] = ChainAnchor.objects.filter(
            status=ChainAnchor.STATUS_PENDING
        ).count()
        return context

    ct = ContentType.objects.get_for_model(request.user)
    wallet = Wallet.objects.filter(
        holder_type=ct, holder_id=request.user.pk, slug="default"
    ).first()
    if wallet:
        context["balance"] = wallet.balance
        context["wallet_uuid"] = str(wallet.uuid)
        context["tx_count"] = Transaction.objects.filter(wallet=wallet).count()
        context["recent_transactions"] = list(
            Transaction.objects.filter(wallet=wallet)
            .order_by("-created_at")[:10]
            .values("uuid", "type", "amount", "status", "created_at", "tx_hash")
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
        .order_by("-created_at")[:10]
        .values("id", "type", "status", "amount", "created_at")
    )

    context["anchors_recent"] = list(
        ChainAnchor.objects.select_related("transaction")
        .order_by("-created_at")[:10]
        .values(
            "id",
            "status",
            "onchain_tx_hash",
            "created_at",
            "transaction__uuid",
            "transaction__amount",
        )
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
        agent = CashAgent.objects.filter(
            holder_type=ct, holder_id=request.user.pk
        ).first()
        if agent:
            context["agent_cash_pending"] = CashRequest.objects.filter(
                agent=agent, status=CashRequest.STATUS_PENDING
            ).count()
            context["agent_pending_list"] = list(
                CashRequest.objects.filter(agent=agent, status=CashRequest.STATUS_PENDING)
                .order_by("-created_at")[:10]
                .values("id", "type", "amount", "holder_id", "created_at")
            )

    return context


@login_required
def portal_view(request):
    return render(request, "dj_wallet/portal.html", _base_context(request))


@login_required
def portal_balances_view(request):
    return render(
        request,
        "dj_wallet/portal_balances.html",
        _base_context(request),
    )


@login_required
def portal_anchors_view(request):
    return render(
        request,
        "dj_wallet/portal_anchors.html",
        _base_context(request),
    )


@login_required
def portal_cash_view(request):
    return render(
        request,
        "dj_wallet/portal_cash.html",
        _base_context(request),
    )


@login_required
def portal_docs_view(request):
    return render(
        request,
        "dj_wallet/portal_docs.html",
        _base_context(request),
    )
