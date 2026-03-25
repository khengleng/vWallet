import secrets

from .models import TransferReceipt


class ReceiptService:
    @staticmethod
    def create_for_transfer(transfer, note=""):
        reference = secrets.token_hex(8)
        return TransferReceipt.objects.create(
            transfer=transfer, reference=reference, note=note
        )
