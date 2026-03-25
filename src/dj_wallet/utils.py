from django.utils.module_loading import import_string

from .conf import wallet_settings


def get_wallet_service():
    """
    Returns the configured WalletService class.
    Override via settings: dj_wallet['WALLET_SERVICE_CLASS']
    Example:
        WalletService = get_wallet_service()
        WalletService.deposit(wallet, amount)
    """
    return import_string(wallet_settings.WALLET_SERVICE_CLASS)


def get_transfer_service():
    """
    Returns the configured TransferService class.
    Override via settings: dj_wallet['TRANSFER_SERVICE_CLASS']
    """
    return import_string(wallet_settings.TRANSFER_SERVICE_CLASS)


def get_exchange_service():
    """
    Returns the configured ExchangeService class.
    Override via settings: dj_wallet['EXCHANGE_SERVICE_CLASS']
    """
    return import_string(wallet_settings.EXCHANGE_SERVICE_CLASS)


def get_purchase_service():
    """
    Returns the configured PurchaseService class.
    Override via settings: dj_wallet['PURCHASE_SERVICE_CLASS']
    """
    return import_string(wallet_settings.PURCHASE_SERVICE_CLASS)


def get_wallet_mixin():
    """
    Returns the configured WalletMixin class.
    Override via settings: dj_wallet['WALLET_MIXIN_CLASS']
    """
    return import_string(wallet_settings.WALLET_MIXIN_CLASS)


def get_permission_policy():
    """
    Returns the configured PermissionPolicy class.
    Override via settings: dj_wallet['PERMISSION_POLICY_CLASS']
    """
    return import_string(wallet_settings.PERMISSION_POLICY_CLASS)


def get_signature_service():
    """
    Returns the configured SignatureService class.
    Override via settings: dj_wallet['SIGNATURE_SERVICE_CLASS']
    """
    return import_string(wallet_settings.SIGNATURE_SERVICE_CLASS)


def get_anchor_service():
    """
    Returns the configured AnchorService class.
    Override via settings: dj_wallet['ANCHOR_SERVICE_CLASS']
    """
    return import_string(wallet_settings.ANCHOR_SERVICE_CLASS)


def get_compliance_service():
    """
    Returns the configured ComplianceService class.
    Override via settings: dj_wallet['COMPLIANCE_SERVICE_CLASS']
    """
    return import_string(wallet_settings.COMPLIANCE_SERVICE_CLASS)


def get_fraud_service():
    """
    Returns the configured FraudService class.
    Override via settings: dj_wallet['FRAUD_SERVICE_CLASS']
    """
    return import_string(wallet_settings.FRAUD_SERVICE_CLASS)
