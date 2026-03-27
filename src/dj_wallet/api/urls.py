from django.urls import path
from dj_wallet.portal import (
    portal_balances_view,
    portal_cash_view,
    portal_docs_view,
    portal_anchors_view,
    portal_view,
    portal_approvals_view,
)

from dj_wallet.api import views

urlpatterns = [
    path("", portal_view, name="portal"),
    path("portal/balances", portal_balances_view, name="portal-balances"),
    path("portal/anchors", portal_anchors_view, name="portal-anchors"),
    path("portal/cash", portal_cash_view, name="portal-cash"),
    path("portal/approvals", portal_approvals_view, name="portal-approvals"),
    path("portal/docs", portal_docs_view, name="portal-docs"),
    path("wallet/balance", views.BalanceView.as_view(), name="wallet-balance"),
    path("auth/me", views.MeView.as_view(), name="auth-me"),
    path("auth/pin/set", views.PinSetView.as_view(), name="auth-pin-set"),
    path("auth/pin/reset", views.PinResetView.as_view(), name="auth-pin-reset"),
    path("auth/mfa/challenge", views.MfaChallengeView.as_view(), name="auth-mfa-challenge"),
    path("auth/mfa/verify", views.MfaVerifyView.as_view(), name="auth-mfa-verify"),
    path("auth/password-reset", views.PasswordResetRequestView.as_view(), name="auth-password-reset"),
    path("auth/pin/login", views.PinLoginView.as_view(), name="auth-pin-login"),
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
    path(
        "approvals/approve/<int:approval_id>",
        views.ApprovalApproveView.as_view(),
        name="approval-approve",
    ),
    path(
        "approvals/reject/<int:approval_id>",
        views.ApprovalRejectView.as_view(),
        name="approval-reject",
    ),
    path("approvals/list", views.ApprovalListView.as_view(), name="approval-list"),
]
