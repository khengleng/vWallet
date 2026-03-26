import hashlib
import json
import secrets
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import Group
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.contenttypes.models import ContentType
from django.utils.timezone import now
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from rest_framework import permissions, status
from rest_framework.authtoken.models import Token
from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.views import ObtainAuthToken
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
    MobileSecurityProfile,
    MfaChallenge,
)
from dj_wallet.user_signing import UserSigningService
from dj_wallet.conf import wallet_settings
from django.utils import timezone


def _is_mobile_request(request):
    return request.META.get("HTTP_X_PLATFORM", "").lower() == "pwa"


def _require_customer(request):
    if not _is_mobile_request(request):
        return None
    ct = ContentType.objects.get_for_model(request.user)
    has_role = WalletRoleAssignment.objects.filter(
        holder_type=ct, holder_id=request.user.pk, role__slug="customer"
    ).exists()
    has_group = request.user.groups.filter(name="Customer").exists()
    if not (has_role or has_group):
        return Response({"detail": "customer_only"}, status=status.HTTP_403_FORBIDDEN)
    return None


def _get_mobile_profile(user):
    profile, _ = MobileSecurityProfile.objects.get_or_create(user=user)
    return profile


def _validate_pin(pin):
    if not pin:
        return False
    if not pin.isdigit():
        return False
    return 4 <= len(pin) <= 8


def _require_pin(request):
    if not _is_mobile_request(request):
        return None
    pin = request.data.get("pin", "")
    if not pin:
        return Response({"detail": "pin_required"}, status=status.HTTP_400_BAD_REQUEST)
    profile = _get_mobile_profile(request.user)
    ok, resp = _check_pin_profile(profile, pin)
    if not ok:
        return resp
    return None


def _check_pin_profile(profile, pin):
    if profile.pin_locked_until and profile.pin_locked_until > timezone.now():
        return False, Response({"detail": "pin_locked"}, status=status.HTTP_429_TOO_MANY_REQUESTS)
    if not profile.pin_hash:
        return False, Response({"detail": "pin_not_set"}, status=status.HTTP_400_BAD_REQUEST)
    if not check_password(pin, profile.pin_hash):
        profile.pin_failed_count += 1
        if profile.pin_failed_count >= 5:
            profile.pin_locked_until = timezone.now() + timedelta(minutes=15)
        profile.save(update_fields=["pin_failed_count", "pin_locked_until", "updated_at"])
        return False, Response({"detail": "pin_invalid"}, status=status.HTTP_400_BAD_REQUEST)
    if profile.pin_failed_count:
        profile.pin_failed_count = 0
        profile.pin_locked_until = None
        profile.save(update_fields=["pin_failed_count", "pin_locked_until", "updated_at"])
    return True, None


def _high_value_threshold(action):
    withdraw_threshold = wallet_settings.APPROVAL_WITHDRAW_THRESHOLD
    transfer_threshold = wallet_settings.APPROVAL_TRANSFER_THRESHOLD
    if withdraw_threshold is None and transfer_threshold is None:
        return None
    if action in {"withdraw", "cashout"}:
        return withdraw_threshold
    if action in {"transfer"}:
        return transfer_threshold
    return max(
        t for t in [withdraw_threshold, transfer_threshold] if t is not None
    )


def _require_mfa(request, action, amount):
    if not _is_mobile_request(request):
        return None
    threshold = _high_value_threshold(action)
    if threshold is None:
        return None
    try:
        amount_val = Decimal(str(amount))
    except Exception:
        return None
    if amount_val < Decimal(str(threshold)):
        return None
    token = request.data.get("mfa_token", "")
    if not token:
        return Response({"detail": "mfa_required"}, status=status.HTTP_400_BAD_REQUEST)
    now_ts = timezone.now()
    challenge = MfaChallenge.objects.filter(
        user=request.user,
        mfa_token=token,
        verified_at__isnull=False,
        mfa_expires_at__gt=now_ts,
    ).first()
    if not challenge:
        return Response({"detail": "mfa_invalid"}, status=status.HTTP_400_BAD_REQUEST)
    return None


def _mobile_custodial_enabled():
    return getattr(settings, "DJ_WALLET_MOBILE_CUSTODIAL", False)


@method_decorator(csrf_exempt, name="dispatch")
class MobileAuthTokenView(ObtainAuthToken):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key})


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
    authentication_classes = [TokenAuthentication]
    throttle_classes = [BurstRateThrottle, SustainedRateThrottle]

    def get(self, request):
        mobile_block = _require_customer(request)
        if mobile_block:
            return mobile_block
        return Response({"balance": str(request.user.balance)})


class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [TokenAuthentication]
    throttle_classes = [BurstRateThrottle, SustainedRateThrottle]

    def get(self, request):
        ct = ContentType.objects.get_for_model(request.user)
        roles = list(
            WalletRoleAssignment.objects.filter(holder_type=ct, holder_id=request.user.pk)
            .select_related("role")
            .values_list("role__slug", flat=True)
        )
        groups = list(request.user.groups.values_list("name", flat=True))
        return Response(
            {
                "username": request.user.username,
                "email": request.user.email,
                "roles": roles,
                "groups": groups,
            }
        )


class PinSetView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [TokenAuthentication]
    throttle_classes = [BurstRateThrottle, SustainedRateThrottle]

    def post(self, request):
        if not _is_mobile_request(request):
            return Response({"detail": "mobile_only"}, status=status.HTTP_400_BAD_REQUEST)
        pin = request.data.get("pin", "")
        if not _validate_pin(pin):
            return Response({"detail": "pin_invalid_format"}, status=status.HTTP_400_BAD_REQUEST)
        profile = _get_mobile_profile(request.user)
        profile.pin_hash = make_password(pin)
        profile.pin_set_at = timezone.now()
        profile.save(update_fields=["pin_hash", "pin_set_at", "updated_at"])
        return Response({"status": "ok"})


class MfaChallengeView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [TokenAuthentication]
    throttle_classes = [BurstRateThrottle, SustainedRateThrottle]

    def post(self, request):
        if not _is_mobile_request(request):
            return Response({"detail": "mobile_only"}, status=status.HTTP_400_BAD_REQUEST)
        action = request.data.get("action", "")
        amount = request.data.get("amount", "")
        if action == "pin_reset":
            amount = "0"
            threshold = Decimal("0")
        else:
            threshold = _high_value_threshold(action)
        if threshold is None:
            return Response({"mfa_required": False})
        try:
            amount_val = Decimal(str(amount))
        except Exception:
            return Response({"detail": "amount_invalid"}, status=status.HTTP_400_BAD_REQUEST)
        if amount_val < Decimal(str(threshold)):
            return Response({"mfa_required": False})

        code = f"{secrets.randbelow(1000000):06d}"
        expires_at = timezone.now() + timedelta(minutes=5)
        challenge = MfaChallenge.objects.create(
            user=request.user,
            action=action,
            amount=amount_val,
            code_hash=make_password(code),
            expires_at=expires_at,
        )
        payload = {"challenge_id": str(challenge.id), "expires_at": expires_at.isoformat()}
        if settings.DEBUG:
            payload["code"] = code
        return Response(payload)


class MfaVerifyView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [TokenAuthentication]
    throttle_classes = [BurstRateThrottle, SustainedRateThrottle]

    def post(self, request):
        if not _is_mobile_request(request):
            return Response({"detail": "mobile_only"}, status=status.HTTP_400_BAD_REQUEST)
        challenge_id = request.data.get("challenge_id", "")
        code = request.data.get("code", "")
        if not challenge_id or not code:
            return Response({"detail": "missing_fields"}, status=status.HTTP_400_BAD_REQUEST)
        challenge = MfaChallenge.objects.filter(
            id=challenge_id, user=request.user
        ).first()
        if not challenge:
            return Response({"detail": "challenge_not_found"}, status=status.HTTP_404_NOT_FOUND)
        if challenge.locked_until and challenge.locked_until > timezone.now():
            return Response({"detail": "mfa_locked"}, status=status.HTTP_429_TOO_MANY_REQUESTS)
        if challenge.expires_at < timezone.now():
            return Response({"detail": "challenge_expired"}, status=status.HTTP_400_BAD_REQUEST)
        if challenge.verified_at is not None:
            return Response({"detail": "challenge_used"}, status=status.HTTP_400_BAD_REQUEST)
        if not check_password(code, challenge.code_hash):
            challenge.failed_attempts += 1
            if challenge.failed_attempts >= 5:
                challenge.locked_until = timezone.now() + timedelta(minutes=15)
            challenge.save(update_fields=["failed_attempts", "locked_until"])
            return Response({"detail": "code_invalid"}, status=status.HTTP_400_BAD_REQUEST)

        token = secrets.token_hex(16)
        challenge.verified_at = timezone.now()
        challenge.mfa_token = token
        challenge.mfa_expires_at = timezone.now() + timedelta(minutes=5)
        challenge.save(update_fields=["verified_at", "mfa_token", "mfa_expires_at"])
        return Response({"mfa_token": token, "expires_at": challenge.mfa_expires_at.isoformat()})


class PinResetView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [TokenAuthentication]
    throttle_classes = [BurstRateThrottle, SustainedRateThrottle]

    def post(self, request):
        if not _is_mobile_request(request):
            return Response({"detail": "mobile_only"}, status=status.HTTP_400_BAD_REQUEST)
        token = request.data.get("mfa_token", "")
        if not token:
            return Response({"detail": "mfa_required"}, status=status.HTTP_400_BAD_REQUEST)
        now_ts = timezone.now()
        challenge = MfaChallenge.objects.filter(
            user=request.user,
            mfa_token=token,
            verified_at__isnull=False,
            mfa_expires_at__gt=now_ts,
        ).first()
        if not challenge:
            return Response({"detail": "mfa_invalid"}, status=status.HTTP_400_BAD_REQUEST)
        profile = _get_mobile_profile(request.user)
        profile.pin_hash = ""
        profile.pin_set_at = None
        profile.save(update_fields=["pin_hash", "pin_set_at", "updated_at"])
        return Response({"status": "pin_reset"})


class PasswordResetRequestView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_classes = [BurstRateThrottle, SustainedRateThrottle]

    def post(self, request):
        email = request.data.get("email", "")
        if not email:
            return Response({"detail": "email_required"}, status=status.HTTP_400_BAD_REQUEST)
        form = PasswordResetForm(data={"email": email})
        if not form.is_valid():
            return Response({"detail": "email_invalid"}, status=status.HTTP_400_BAD_REQUEST)
        form.save(
            request=request,
            use_https=request.is_secure(),
            subject_template_name="registration/password_reset_subject.txt",
            email_template_name="registration/password_reset_email.txt",
        )
        return Response({"status": "sent"})


class PinLoginView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_classes = [BurstRateThrottle, SustainedRateThrottle]

    def post(self, request):
        if not _is_mobile_request(request):
            return Response({"detail": "mobile_only"}, status=status.HTTP_400_BAD_REQUEST)
        username = request.data.get("username", "")
        email = request.data.get("email", "")
        pin = request.data.get("pin", "")
        if not pin:
            return Response({"detail": "pin_required"}, status=status.HTTP_400_BAD_REQUEST)
        User = get_user_model()
        user = None
        if username:
            user = User.objects.filter(username=username).first()
        elif email:
            user = User.objects.filter(email=email).first()
        if not user:
            return Response({"detail": "user_not_found"}, status=status.HTTP_404_NOT_FOUND)
        profile = _get_mobile_profile(user)
        ok, resp = _check_pin_profile(profile, pin)
        if not ok:
            return resp
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key})


class DepositView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [TokenAuthentication]
    throttle_classes = [BurstRateThrottle, SustainedRateThrottle]

    def post(self, request):
        mobile_block = _require_customer(request)
        if mobile_block:
            return mobile_block
        serializer = AmountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        pin_block = _require_pin(request)
        if pin_block:
            return pin_block
        mfa_block = _require_mfa(request, "deposit", data["amount"])
        if mfa_block:
            return mfa_block

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
    authentication_classes = [TokenAuthentication]
    throttle_classes = [BurstRateThrottle, SustainedRateThrottle]

    def post(self, request):
        mobile_block = _require_customer(request)
        if mobile_block:
            return mobile_block
        serializer = AmountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        pin_block = _require_pin(request)
        if pin_block:
            return pin_block
        mfa_block = _require_mfa(request, "withdraw", data["amount"])
        if mfa_block:
            return mfa_block

        meta = data.get("meta") or {}
        meta.update(_request_meta(request))

        # User signature required (unless mobile custodial mode)
        nonce = data.get("nonce")
        signature = data.get("signature")
        key_id = data.get("key_id")
        if not (nonce and signature and key_id):
            if not (_is_mobile_request(request) and _mobile_custodial_enabled()):
                return Response(
                    {"detail": "signature_required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        if nonce and signature and key_id:
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
        if signature and key_id:
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
    authentication_classes = [TokenAuthentication]
    throttle_classes = [BurstRateThrottle, SustainedRateThrottle]

    def post(self, request):
        mobile_block = _require_customer(request)
        if mobile_block:
            return mobile_block
        serializer = TransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        pin_block = _require_pin(request)
        if pin_block:
            return pin_block
        mfa_block = _require_mfa(request, "transfer", data["amount"])
        if mfa_block:
            return mfa_block

        meta = data.get("meta") or {}
        meta.update(_request_meta(request))

        # User signature required (unless mobile custodial mode)
        nonce = data.get("nonce")
        signature = data.get("signature")
        key_id = data.get("key_id")
        if not (nonce and signature and key_id):
            if not (_is_mobile_request(request) and _mobile_custodial_enabled()):
                return Response(
                    {"detail": "signature_required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        if nonce and signature and key_id:
            ok, reason = UserSigningService.verify(
                request.user, "transfer", data["amount"], nonce, signature, key_id
            )
            if not ok:
                return Response({"detail": reason}, status=status.HTTP_400_BAD_REQUEST)

        User = get_user_model()
        to_user = None
        if data.get("to_user_id"):
            to_user = User.objects.get(pk=data["to_user_id"])
        elif data.get("to_username"):
            to_user = User.objects.get(username=data["to_username"])
        else:
            return Response({"detail": "to_user_required"}, status=status.HTTP_400_BAD_REQUEST)

        idem_resp, idem_record = _idempotency_get_or_respond(
            request,
            "transfer",
            {
                "to_user_id": to_user.pk,
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
                    "to_user_id": to_user.pk,
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
        if signature and key_id:
            UserSigningService.attach_signature(
                transfer.withdraw, signature=signature, key_id=key_id, signer=request.user
            )
        # Attach note to receipt if provided
        note_value = data.get("note") or data.get("memo")
        if note_value:
            receipt = TransferReceipt.objects.filter(transfer=transfer).first()
            if receipt:
                receipt.note = note_value
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
    authentication_classes = [TokenAuthentication]
    throttle_classes = [BurstRateThrottle, SustainedRateThrottle]

    def get(self, request):
        mobile_block = _require_customer(request)
        if mobile_block:
            return mobile_block
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
    authentication_classes = [TokenAuthentication]
    throttle_classes = [BurstRateThrottle, SustainedRateThrottle]

    def get(self, request):
        mobile_block = _require_customer(request)
        if mobile_block:
            return mobile_block
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
    authentication_classes = [TokenAuthentication]
    throttle_classes = [BurstRateThrottle, SustainedRateThrottle]

    def get(self, request):
        mobile_block = _require_customer(request)
        if mobile_block:
            return mobile_block
        sources = FundingService.list_sources(request.user)
        return Response(
            {
                "sources": list(
                    sources.values("id", "type", "label", "account_ref", "meta")
                )
            }
        )

    def post(self, request):
        mobile_block = _require_customer(request)
        if mobile_block:
            return mobile_block
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
    authentication_classes = [TokenAuthentication]
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

        # Assign customer role (create if missing)
        role, _ = WalletRole.objects.get_or_create(
            slug="customer", defaults={"name": "Customer"}
        )
        WalletRoleAssignment.objects.get_or_create(
            holder_type=ContentType.objects.get_for_model(user),
            holder_id=user.pk,
            role=role,
        )

        # Add to Django auth group for admin visibility
        group, _ = Group.objects.get_or_create(name="Customer")
        user.groups.add(group)

        return Response({"user_id": user.pk}, status=status.HTTP_201_CREATED)


class CashInRequestView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [TokenAuthentication]
    throttle_classes = [BurstRateThrottle, SustainedRateThrottle]

    def post(self, request):
        mobile_block = _require_customer(request)
        if mobile_block:
            return mobile_block
        serializer = CashRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        pin_block = _require_pin(request)
        if pin_block:
            return pin_block
        mfa_block = _require_mfa(request, "cashin", data["amount"])
        if mfa_block:
            return mfa_block

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
    authentication_classes = [TokenAuthentication]
    throttle_classes = [BurstRateThrottle, SustainedRateThrottle]

    def post(self, request):
        mobile_block = _require_customer(request)
        if mobile_block:
            return mobile_block
        serializer = CashRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        pin_block = _require_pin(request)
        if pin_block:
            return pin_block
        mfa_block = _require_mfa(request, "cashout", data["amount"])
        if mfa_block:
            return mfa_block

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
            if approval.resolved_by is None:
                approval.resolved_by = request.user
                approval.resolved_at = timezone.now()
                approval.save(update_fields=["resolved_by", "resolved_at", "updated_at"])
                return Response({"status": "pending_second_approval"})
            if approval.resolved_by == request.user:
                return Response({"detail": "second_approver_required"}, status=status.HTTP_400_BAD_REQUEST)
            approval.second_approved_by = request.user
            approval.second_approved_at = timezone.now()
            txn = holder.withdraw(approval.amount, meta={"approval_id": approval.id}, confirmed=True)
            UserSigningService.attach_signature(
                txn, signature=signature, key_id=key_id, signer=holder
            )
            approval.status = ApprovalRequest.STATUS_APPROVED
            approval.meta = {**meta, "transaction_id": str(txn.uuid)}
            approval.save(
                update_fields=[
                    "status",
                    "second_approved_by",
                    "second_approved_at",
                    "meta",
                    "updated_at",
                ]
            )
            return Response({"status": "approved", "transaction_id": str(txn.uuid)})

        if approval.action == "transfer":
            ok, reason = UserSigningService.verify(
                holder, "transfer", approval.amount, nonce, signature, key_id
            )
            if not ok:
                return Response({"detail": reason}, status=status.HTTP_400_BAD_REQUEST)
            User = get_user_model()
            to_user = User.objects.get(pk=meta.get("to_user_id"))
            if approval.resolved_by is None:
                approval.resolved_by = request.user
                approval.resolved_at = timezone.now()
                approval.save(update_fields=["resolved_by", "resolved_at", "updated_at"])
                return Response({"status": "pending_second_approval"})
            if approval.resolved_by == request.user:
                return Response({"detail": "second_approver_required"}, status=status.HTTP_400_BAD_REQUEST)
            approval.second_approved_by = request.user
            approval.second_approved_at = timezone.now()
            transfer = holder.transfer(
                to_user, approval.amount, meta={"approval_id": approval.id}
            )
            UserSigningService.attach_signature(
                transfer.withdraw, signature=signature, key_id=key_id, signer=holder
            )
            approval.status = ApprovalRequest.STATUS_APPROVED
            approval.meta = {**meta, "transfer_id": str(transfer.uuid)}
            approval.save(
                update_fields=[
                    "status",
                    "second_approved_by",
                    "second_approved_at",
                    "meta",
                    "updated_at",
                ]
            )
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
