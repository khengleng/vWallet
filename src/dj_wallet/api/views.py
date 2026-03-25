from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.utils.timezone import now
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from dj_wallet.api.serializers import (
    AmountSerializer,
    AgentOnboardSerializer,
    CashRequestSerializer,
    FundingSourceSerializer,
    RegisterSerializer,
    StatementQuerySerializer,
    TransferSerializer,
)
from dj_wallet.api.throttles import BurstRateThrottle, SustainedRateThrottle
from dj_wallet.cash import CashService
from dj_wallet.funding import FundingService
from dj_wallet.models import (
    CashAgent,
    CashRequest,
    ComplianceProfile,
    Transaction,
    TransferReceipt,
    WalletRole,
    WalletRoleAssignment,
)
from dj_wallet.user_signing import UserSigningService


def _request_meta(request):
    return {
        "ip": request.META.get("REMOTE_ADDR", ""),
        "user_agent": request.META.get("HTTP_USER_AGENT", ""),
        "device_id": request.META.get("HTTP_X_DEVICE_ID", ""),
        "app_version": request.META.get("HTTP_X_APP_VERSION", ""),
        "platform": request.META.get("HTTP_X_PLATFORM", ""),
        "ts": now().isoformat(),
    }


class BalanceView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [BurstRateThrottle, SustainedRateThrottle]

    def get(self, request):
        return Response({"balance": str(request.user.balance)})


class DepositView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [BurstRateThrottle, SustainedRateThrottle]

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
    throttle_classes = [BurstRateThrottle, SustainedRateThrottle]

    def post(self, request):
        serializer = AmountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        meta = data.get("meta") or {}
        meta.update(_request_meta(request))

        # User signature required
        nonce = data.get("nonce")
        signature = data.get("signature")
        key_id = data.get("key_id")
        if not (nonce and signature and key_id):
            return Response(
                {"detail": "signature_required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        ok, reason = UserSigningService.verify(
            request.user, "withdraw", data["amount"], nonce, signature, key_id
        )
        if not ok:
            return Response({"detail": reason}, status=status.HTTP_400_BAD_REQUEST)

        txn = request.user.withdraw(data["amount"], meta=meta, confirmed=True)
        UserSigningService.attach_signature(
            txn, signature=signature, key_id=key_id, signer=request.user
        )
        return Response(
            {"transaction_id": str(txn.uuid), "balance": str(request.user.balance)},
            status=status.HTTP_201_CREATED,
        )


class TransferView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [BurstRateThrottle, SustainedRateThrottle]

    def post(self, request):
        serializer = TransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        meta = data.get("meta") or {}
        meta.update(_request_meta(request))

        # User signature required
        nonce = data.get("nonce")
        signature = data.get("signature")
        key_id = data.get("key_id")
        if not (nonce and signature and key_id):
            return Response(
                {"detail": "signature_required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        ok, reason = UserSigningService.verify(
            request.user, "transfer", data["amount"], nonce, signature, key_id
        )
        if not ok:
            return Response({"detail": reason}, status=status.HTTP_400_BAD_REQUEST)

        User = get_user_model()
        to_user = User.objects.get(pk=data["to_user_id"])

        transfer = request.user.transfer(to_user, data["amount"], meta=meta)
        # Attach signature to the withdraw txn
        UserSigningService.attach_signature(
            transfer.withdraw, signature=signature, key_id=key_id, signer=request.user
        )
        # Attach note to receipt if provided
        if data.get("note"):
            receipt = TransferReceipt.objects.filter(transfer=transfer).first()
            if receipt:
                receipt.note = data["note"]
                receipt.save(update_fields=["note"])
        return Response(
            {
                "transfer_id": str(transfer.uuid),
                "balance": str(request.user.balance),
                "receipt": getattr(transfer, "transferreceipt", None)
                and transfer.transferreceipt.reference,
            },
            status=status.HTTP_201_CREATED,
        )


class TransactionsView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [BurstRateThrottle, SustainedRateThrottle]

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


class StatementView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [BurstRateThrottle, SustainedRateThrottle]

    def get(self, request):
        serializer = StatementQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        qs = Transaction.objects.filter(wallet=request.user.wallet)
        if data.get("from_date"):
            qs = qs.filter(created_at__date__gte=data["from_date"])
        if data.get("to_date"):
            qs = qs.filter(created_at__date__lte=data["to_date"])

        qs = qs.order_by("-created_at")[:500]
        return Response(
            {
                "transactions": list(
                    qs.values(
                        "uuid",
                        "type",
                        "amount",
                        "status",
                        "created_at",
                        "tx_hash",
                        "prev_tx_hash",
                        "meta",
                    )
                )
            }
        )


class FundingSourceView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [BurstRateThrottle, SustainedRateThrottle]

    def get(self, request):
        sources = FundingService.list_sources(request.user)
        return Response(
            {
                "sources": list(
                    sources.values("id", "type", "label", "account_ref", "meta")
                )
            }
        )

    def post(self, request):
        serializer = FundingSourceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        src = FundingService.create_source(
            request.user,
            data["type"],
            data["label"],
            data["account_ref"],
            meta=data.get("meta"),
        )
        return Response({"id": src.id}, status=status.HTTP_201_CREATED)


class AgentOnboardView(APIView):
    permission_classes = [permissions.IsAdminUser]
    throttle_classes = [BurstRateThrottle, SustainedRateThrottle]

    def post(self, request):
        serializer = AgentOnboardSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        User = get_user_model()
        user_id = request.data.get("user_id")
        if not user_id:
            return Response({"detail": "user_id_required"}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.filter(pk=user_id).first()
        if not user:
            return Response({"detail": "user_not_found"}, status=status.HTTP_404_NOT_FOUND)

        ct = ContentType.objects.get_for_model(user)
        agent, _ = CashAgent.objects.get_or_create(
            holder_type=ct, holder_id=user.pk, defaults={"code": data["code"]}
        )
        if agent.code != data["code"]:
            return Response({"detail": "agent_exists"}, status=status.HTTP_400_BAD_REQUEST)

        # Assign agent role
        role = WalletRole.objects.filter(slug="agent").first()
        if role:
            WalletRoleAssignment.objects.get_or_create(
                holder_type=ct, holder_id=user.pk, role=role
            )

        return Response({"agent_id": agent.id}, status=status.HTTP_201_CREATED)


class NonceView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [BurstRateThrottle, SustainedRateThrottle]

    def post(self, request):
        nonce = UserSigningService.issue_nonce(request.user)
        return Response({"nonce": nonce})


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [BurstRateThrottle, SustainedRateThrottle]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        User = get_user_model()
        user = User.objects.create_user(
            username=data["username"], email=data["email"], password=data["password"]
        )

        # Create compliance profile (pending by default)
        ComplianceProfile.objects.update_or_create(
            holder_type=ContentType.objects.get_for_model(user),
            holder_id=user.pk,
            defaults={"status": ComplianceProfile.STATUS_PENDING},
        )

        # Assign default role if exists
        role = WalletRole.objects.filter(slug="basic").first()
        if role:
            WalletRoleAssignment.objects.get_or_create(
                holder_type=ContentType.objects.get_for_model(user),
                holder_id=user.pk,
                role=role,
            )

        return Response({"user_id": user.pk}, status=status.HTTP_201_CREATED)


class CashInRequestView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [BurstRateThrottle, SustainedRateThrottle]

    def post(self, request):
        serializer = CashRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        agent = CashAgent.objects.filter(code=data["agent_code"], is_active=True).first()
        if not agent:
            return Response({"detail": "agent_not_found"}, status=status.HTTP_400_BAD_REQUEST)

        cash_req = CashService.request_cashin(
            request.user, agent, data["amount"], meta=data.get("meta")
        )
        return Response({"request_id": cash_req.id}, status=status.HTTP_201_CREATED)


class CashOutRequestView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [BurstRateThrottle, SustainedRateThrottle]

    def post(self, request):
        serializer = CashRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        agent = CashAgent.objects.filter(code=data["agent_code"], is_active=True).first()
        if not agent:
            return Response({"detail": "agent_not_found"}, status=status.HTTP_400_BAD_REQUEST)

        cash_req = CashService.request_cashout(
            request.user, agent, data["amount"], meta=data.get("meta")
        )
        return Response({"request_id": cash_req.id}, status=status.HTTP_201_CREATED)


class CashApproveView(APIView):
    permission_classes = [permissions.IsAdminUser]
    throttle_classes = [BurstRateThrottle, SustainedRateThrottle]

    def post(self, request, request_id):
        cash_req = CashRequest.objects.filter(pk=request_id).first()
        if not cash_req:
            return Response({"detail": "not_found"}, status=status.HTTP_404_NOT_FOUND)
        CashService.approve(cash_req)
        if request.accepted_renderer.format == "html":
            from django.shortcuts import redirect

            return redirect("/api/")
        return Response({"status": "approved"})


class CashRejectView(APIView):
    permission_classes = [permissions.IsAdminUser]
    throttle_classes = [BurstRateThrottle, SustainedRateThrottle]

    def post(self, request, request_id):
        cash_req = CashRequest.objects.filter(pk=request_id).first()
        if not cash_req:
            return Response({"detail": "not_found"}, status=status.HTTP_404_NOT_FOUND)
        CashService.reject(cash_req, reason=request.data.get("reason", ""))
        if request.accepted_renderer.format == "html":
            from django.shortcuts import redirect

            return redirect("/api/")
        return Response({"status": "rejected"})
