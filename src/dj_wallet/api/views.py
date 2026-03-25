import hashlib
import json

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
    IdempotencyKey,
    ApprovalRequest,
    Transaction,
    TransferReceipt,
    WalletRole,
    WalletRoleAssignment,
)
from dj_wallet.user_signing import UserSigningService
from dj_wallet.conf import wallet_settings
from django.utils import timezone


def _request_meta(request):
    return {
        "ip": request.META.get("REMOTE_ADDR", ""),
        "user_agent": request.META.get("HTTP_USER_AGENT", ""),
        "device_id": request.META.get("HTTP_X_DEVICE_ID", ""),
        "app_version": request.META.get("HTTP_X_APP_VERSION", ""),
        "platform": request.META.get("HTTP_X_PLATFORM", ""),
        "ts": now().isoformat(),
    }


def _idempotency_key(request):
    return request.META.get("HTTP_IDEMPOTENCY_KEY", "").strip()


def _idempotency_hash(payload):
    data = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _idempotency_get_or_respond(request, scope, payload):
    key = _idempotency_key(request)
    if not key:
        return None, None

    req_hash = _idempotency_hash(payload)
    record = IdempotencyKey.objects.filter(key=key).first()
    if record:
        if record.request_hash and record.request_hash != req_hash:
            return Response({"detail": "idempotency_conflict"}, status=409), None
        if record.response_status is not None:
            return Response(record.response_body or {}, status=record.response_status), None
        return None, record

    record = IdempotencyKey.objects.create(
        key=key, scope=scope, request_hash=req_hash
    )
    return None, record


def _idempotency_store(record, response):
    if record is None:
        return response
    record.response_status = response.status_code
    if isinstance(response.data, dict):
        record.response_body = response.data
    record.save(update_fields=["response_status", "response_body", "updated_at"])
    return response


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

        idem_resp, idem_record = _idempotency_get_or_respond(
            request, "deposit", {"amount": str(data["amount"]), "meta": meta}
        )
        if idem_resp:
            return idem_resp

        txn = request.user.deposit(data["amount"], meta=meta, confirmed=True)
        resp = Response(
            {"transaction_id": str(txn.uuid), "balance": str(request.user.balance)},
            status=status.HTTP_201_CREATED,
        )
        return _idempotency_store(idem_record, resp)


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

        idem_resp, idem_record = _idempotency_get_or_respond(
            request,
            "withdraw",
            {
                "amount": str(data["amount"]),
                "meta": meta,
                "nonce": nonce,
                "signature": signature,
                "key_id": key_id,
            },
        )
        if idem_resp:
            return idem_resp

        approval_threshold = wallet_settings.APPROVAL_WITHDRAW_THRESHOLD
        if approval_threshold is not None and data["amount"] >= approval_threshold:
            approval = ApprovalRequest.objects.create(
                action="withdraw",
                holder_type=ContentType.objects.get_for_model(request.user),
                holder_id=request.user.pk,
                wallet=request.user.wallet,
                amount=data["amount"],
                meta={
                    "nonce": nonce,
                    "signature": signature,
                    "key_id": key_id,
                },
                created_by=request.user,
            )
            resp = Response(
                {"status": "pending_approval", "approval_id": approval.id},
                status=status.HTTP_202_ACCEPTED,
            )
            return _idempotency_store(idem_record, resp)

        txn = request.user.withdraw(data["amount"], meta=meta, confirmed=True)
        UserSigningService.attach_signature(
            txn, signature=signature, key_id=key_id, signer=request.user
        )
        resp = Response(
            {"transaction_id": str(txn.uuid), "balance": str(request.user.balance)},
            status=status.HTTP_201_CREATED,
        )
        return _idempotency_store(idem_record, resp)


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

        idem_resp, idem_record = _idempotency_get_or_respond(
            request,
            "transfer",
            {
                "to_user_id": data["to_user_id"],
                "amount": str(data["amount"]),
                "meta": meta,
                "nonce": nonce,
                "signature": signature,
                "key_id": key_id,
            },
        )
        if idem_resp:
            return idem_resp

        approval_threshold = wallet_settings.APPROVAL_TRANSFER_THRESHOLD
        if approval_threshold is not None and data["amount"] >= approval_threshold:
            approval = ApprovalRequest.objects.create(
                action="transfer",
                holder_type=ContentType.objects.get_for_model(request.user),
                holder_id=request.user.pk,
                wallet=request.user.wallet,
                amount=data["amount"],
                meta={
                    "to_user_id": data["to_user_id"],
                    "nonce": nonce,
                    "signature": signature,
                    "key_id": key_id,
                },
                created_by=request.user,
            )
            resp = Response(
                {"status": "pending_approval", "approval_id": approval.id},
                status=status.HTTP_202_ACCEPTED,
            )
            return _idempotency_store(idem_record, resp)

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
        resp = Response(
            {
                "transfer_id": str(transfer.uuid),
                "balance": str(request.user.balance),
                "receipt": getattr(transfer, "transferreceipt", None)
                and transfer.transferreceipt.reference,
            },
            status=status.HTTP_201_CREATED,
        )
        return _idempotency_store(idem_record, resp)


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

        idem_resp, idem_record = _idempotency_get_or_respond(
            request,
            "cashin_request",
            {"agent_code": data["agent_code"], "amount": str(data["amount"])},
        )
        if idem_resp:
            return idem_resp

        cash_req = CashService.request_cashin(
            request.user, agent, data["amount"], meta=data.get("meta")
        )
        resp = Response({"request_id": cash_req.id}, status=status.HTTP_201_CREATED)
        return _idempotency_store(idem_record, resp)


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

        idem_resp, idem_record = _idempotency_get_or_respond(
            request,
            "cashout_request",
            {"agent_code": data["agent_code"], "amount": str(data["amount"])},
        )
        if idem_resp:
            return idem_resp

        cash_req = CashService.request_cashout(
            request.user, agent, data["amount"], meta=data.get("meta")
        )
        resp = Response({"request_id": cash_req.id}, status=status.HTTP_201_CREATED)
        return _idempotency_store(idem_record, resp)


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


class ApprovalApproveView(APIView):
    permission_classes = [permissions.IsAdminUser]
    throttle_classes = [BurstRateThrottle, SustainedRateThrottle]

    def post(self, request, approval_id):
        approval = ApprovalRequest.objects.filter(pk=approval_id).first()
        if not approval:
            return Response({"detail": "not_found"}, status=status.HTTP_404_NOT_FOUND)
        if approval.status != ApprovalRequest.STATUS_PENDING:
            return Response({"status": approval.status})

        holder = approval.holder
        meta = approval.meta or {}
        nonce = meta.get("nonce")
        signature = meta.get("signature")
        key_id = meta.get("key_id")

        if approval.action == "withdraw":
            ok, reason = UserSigningService.verify(
                holder, "withdraw", approval.amount, nonce, signature, key_id
            )
            if not ok:
                return Response({"detail": reason}, status=status.HTTP_400_BAD_REQUEST)
            txn = holder.withdraw(approval.amount, meta={"approval_id": approval.id}, confirmed=True)
            UserSigningService.attach_signature(
                txn, signature=signature, key_id=key_id, signer=holder
            )
            approval.status = ApprovalRequest.STATUS_APPROVED
            approval.resolved_by = request.user
            approval.resolved_at = timezone.now()
            approval.meta = {**meta, "transaction_id": str(txn.uuid)}
            approval.save(update_fields=["status", "resolved_by", "resolved_at", "meta", "updated_at"])
            return Response({"status": "approved", "transaction_id": str(txn.uuid)})

        if approval.action == "transfer":
            ok, reason = UserSigningService.verify(
                holder, "transfer", approval.amount, nonce, signature, key_id
            )
            if not ok:
                return Response({"detail": reason}, status=status.HTTP_400_BAD_REQUEST)
            User = get_user_model()
            to_user = User.objects.get(pk=meta.get("to_user_id"))
            transfer = holder.transfer(to_user, approval.amount, meta={"approval_id": approval.id})
            UserSigningService.attach_signature(
                transfer.withdraw, signature=signature, key_id=key_id, signer=holder
            )
            approval.status = ApprovalRequest.STATUS_APPROVED
            approval.resolved_by = request.user
            approval.resolved_at = timezone.now()
            approval.meta = {**meta, "transfer_id": str(transfer.uuid)}
            approval.save(update_fields=["status", "resolved_by", "resolved_at", "meta", "updated_at"])
            return Response({"status": "approved", "transfer_id": str(transfer.uuid)})

        return Response({"detail": "unsupported_action"}, status=status.HTTP_400_BAD_REQUEST)


class ApprovalRejectView(APIView):
    permission_classes = [permissions.IsAdminUser]
    throttle_classes = [BurstRateThrottle, SustainedRateThrottle]

    def post(self, request, approval_id):
        approval = ApprovalRequest.objects.filter(pk=approval_id).first()
        if not approval:
            return Response({"detail": "not_found"}, status=status.HTTP_404_NOT_FOUND)
        if approval.status != ApprovalRequest.STATUS_PENDING:
            return Response({"status": approval.status})

        approval.status = ApprovalRequest.STATUS_REJECTED
        approval.reason = request.data.get("reason", "")
        approval.resolved_by = request.user
        approval.resolved_at = timezone.now()
        approval.save(update_fields=["status", "reason", "resolved_by", "resolved_at", "updated_at"])
        return Response({"status": "rejected"})
