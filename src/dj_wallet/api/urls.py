from django.urls import path
from dj_wallet.portal import (
    portal_balances_view,
    portal_cash_view,
    portal_anchors_view,
    portal_view,
)

from dj_wallet.api import views

urlpatterns = [
    path("", portal_view, name="portal"),
    path("portal/balances", portal_balances_view, name="portal-balances"),
    path("portal/anchors", portal_anchors_view, name="portal-anchors"),
    path("portal/cash", portal_cash_view, name="portal-cash"),
    path("wallet/balance", views.BalanceView.as_view(), name="wallet-balance"),
    path("wallet/nonce", views.NonceView.as_view(), name="wallet-nonce"),
    path("wallet/deposit", views.DepositView.as_view(), name="wallet-deposit"),
    path("wallet/withdraw", views.WithdrawView.as_view(), name="wallet-withdraw"),
    path("wallet/transfer", views.TransferView.as_view(), name="wallet-transfer"),
    path("wallet/transactions", views.TransactionsView.as_view(), name="wallet-txns"),
    path("wallet/statement", views.StatementView.as_view(), name="wallet-statement"),
    path("wallet/funding-sources", views.FundingSourceView.as_view(), name="funding-sources"),
    path("agents/onboard", views.AgentOnboardView.as_view(), name="agent-onboard"),
    path("auth/register", views.RegisterView.as_view(), name="auth-register"),
    path("cashin/request", views.CashInRequestView.as_view(), name="cashin-request"),
    path("cashout/request", views.CashOutRequestView.as_view(), name="cashout-request"),
    path(
        "cash/approve/<int:request_id>",
        views.CashApproveView.as_view(),
        name="cash-approve",
    ),
    path(
        "cash/reject/<int:request_id>",
        views.CashRejectView.as_view(),
        name="cash-reject",
    ),
]
