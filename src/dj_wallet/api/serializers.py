from rest_framework import serializers

from dj_wallet.conf import wallet_settings


class AmountSerializer(serializers.Serializer):
    amount = serializers.DecimalField(
        max_digits=64, decimal_places=wallet_settings.WALLET_MATH_SCALE
    )
    meta = serializers.JSONField(required=False)


class TransferSerializer(serializers.Serializer):
    to_user_id = serializers.IntegerField()
    amount = serializers.DecimalField(
        max_digits=64, decimal_places=wallet_settings.WALLET_MATH_SCALE
    )
    meta = serializers.JSONField(required=False)


class PurchaseSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    amount = serializers.DecimalField(
        max_digits=64, decimal_places=wallet_settings.WALLET_MATH_SCALE
    )
    meta = serializers.JSONField(required=False)
