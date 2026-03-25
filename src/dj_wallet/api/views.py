from django.contrib.auth import get_user_model
from django.utils.timezone import now
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from dj_wallet.api.serializers import AmountSerializer, TransferSerializer
from dj_wallet.models import Transaction


def _request_meta(request):
    return {
        "ip": request.META.get("REMOTE_ADDR", ""),
        "user_agent": request.META.get("HTTP_USER_AGENT", ""),
        "ts": now().isoformat(),
    }


class BalanceView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response({"balance": str(request.user.balance)})


class DepositView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = AmountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        meta = data.get("meta") or {}
        meta.update(_request_meta(request))

        txn = request.user.deposit(data["amount"], meta=meta, confirmed=True)
        return Response(
            {"transaction_id": str(txn.uuid), "balance": str(request.user.balance)},
            status=status.HTTP_201_CREATED,
        )


class WithdrawView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = AmountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        meta = data.get("meta") or {}
        meta.update(_request_meta(request))

        txn = request.user.withdraw(data["amount"], meta=meta, confirmed=True)
        return Response(
            {"transaction_id": str(txn.uuid), "balance": str(request.user.balance)},
            status=status.HTTP_201_CREATED,
        )


class TransferView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = TransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        meta = data.get("meta") or {}
        meta.update(_request_meta(request))

        User = get_user_model()
        to_user = User.objects.get(pk=data["to_user_id"])

        transfer = request.user.transfer(to_user, data["amount"], meta=meta)
        return Response(
            {"transfer_id": str(transfer.uuid), "balance": str(request.user.balance)},
            status=status.HTTP_201_CREATED,
        )


class TransactionsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        txns = (
            Transaction.objects.filter(wallet=request.user.wallet)
            .order_by("-created_at")[:100]
            .values(
                "uuid",
                "type",
                "amount",
                "status",
                "created_at",
                "tx_hash",
                "prev_tx_hash",
            )
        )
        return Response({"transactions": list(txns)})
