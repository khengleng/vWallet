from rest_framework import serializers

from dj_wallet.conf import wallet_settings


class AmountSerializer(serializers.Serializer):
    amount = serializers.DecimalField(
        max_digits=64, decimal_places=wallet_settings.WALLET_MATH_SCALE
    )
    meta = serializers.JSONField(required=False)
    nonce = serializers.CharField(required=False)
    signature = serializers.CharField(required=False)
    key_id = serializers.CharField(required=False)
    pin = serializers.CharField(required=False, allow_blank=True)
    mfa_token = serializers.CharField(required=False, allow_blank=True)


class TransferSerializer(serializers.Serializer):
    to_user_id = serializers.IntegerField(required=False)
    to_username = serializers.CharField(required=False, allow_blank=True)
    amount = serializers.DecimalField(
        max_digits=64, decimal_places=wallet_settings.WALLET_MATH_SCALE
    )
    meta = serializers.JSONField(required=False)
    nonce = serializers.CharField(required=False)
    signature = serializers.CharField(required=False)
    key_id = serializers.CharField(required=False)
    note = serializers.CharField(required=False, allow_blank=True, max_length=255)
    memo = serializers.CharField(required=False, allow_blank=True, max_length=255)
    pin = serializers.CharField(required=False, allow_blank=True)
    mfa_token = serializers.CharField(required=False, allow_blank=True)


class PurchaseSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    amount = serializers.DecimalField(
        max_digits=64, decimal_places=wallet_settings.WALLET_MATH_SCALE
    )
    meta = serializers.JSONField(required=False)


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(min_length=8, write_only=True)


class CashRequestSerializer(serializers.Serializer):
    agent_code = serializers.CharField()
    amount = serializers.DecimalField(
        max_digits=64, decimal_places=wallet_settings.WALLET_MATH_SCALE
    )
    meta = serializers.JSONField(required=False)
    pin = serializers.CharField(required=False, allow_blank=True)
    mfa_token = serializers.CharField(required=False, allow_blank=True)


class StatementQuerySerializer(serializers.Serializer):
    from_date = serializers.DateField(required=False)
    to_date = serializers.DateField(required=False)


class FundingSourceSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=["bank", "aba", "mobile"])
    label = serializers.CharField(max_length=120)
    account_ref = serializers.CharField(max_length=128)
    meta = serializers.JSONField(required=False)


class AgentOnboardSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=64)
