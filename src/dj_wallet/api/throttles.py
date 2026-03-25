from rest_framework.throttling import UserRateThrottle


class BurstRateThrottle(UserRateThrottle):
    scope = "wallet_burst"


class SustainedRateThrottle(UserRateThrottle):
    scope = "wallet_sustained"
