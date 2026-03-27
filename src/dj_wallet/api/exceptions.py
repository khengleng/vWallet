from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

from dj_wallet.permissions import PermissionDenied as WalletPermissionDenied


def wallet_exception_handler(exc, context):
    if isinstance(exc, WalletPermissionDenied):
        detail = str(exc) or "permission_denied"
        return Response({"detail": detail}, status=status.HTTP_403_FORBIDDEN)
    return exception_handler(exc, context)
