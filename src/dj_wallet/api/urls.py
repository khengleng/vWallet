from django.urls import path

from dj_wallet.api import views

urlpatterns = [
    path("wallet/balance", views.BalanceView.as_view(), name="wallet-balance"),
    path("wallet/deposit", views.DepositView.as_view(), name="wallet-deposit"),
    path("wallet/withdraw", views.WithdrawView.as_view(), name="wallet-withdraw"),
    path("wallet/transfer", views.TransferView.as_view(), name="wallet-transfer"),
    path("wallet/transactions", views.TransactionsView.as_view(), name="wallet-txns"),
]
