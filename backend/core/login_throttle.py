"""In-memory throttling of failed authentication attempts.

Only *failed* attempts count, so legitimate logins are never blocked. Failures
are tracked per (client IP, username) to slow down guessing one account and
per client IP to slow down spraying many usernames, without letting a remote
attacker lock a user out from every other address.
"""

import time
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class FailureThrottle:
    max_failures_per_account: int
    max_failures_per_ip: int
    window_seconds: float
    max_tracked_keys: int = 10_000
    _failures: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))

    @staticmethod
    def _account_key(client_ip: str, username: str) -> str:
        return f"acct:{client_ip}:{username.strip().lower()}"

    @staticmethod
    def _ip_key(client_ip: str) -> str:
        return f"ip:{client_ip}"

    def _recent(self, key: str, now: float) -> list[float]:
        recent = [t for t in self._failures.get(key, []) if now - t < self.window_seconds]
        if recent:
            self._failures[key] = recent
        else:
            self._failures.pop(key, None)
        return recent

    def _prune(self, now: float) -> None:
        if len(self._failures) <= self.max_tracked_keys:
            return
        for key in list(self._failures):
            self._recent(key, now)

    def is_blocked(self, client_ip: str, username: str) -> bool:
        now = time.monotonic()
        account_failures = self._recent(self._account_key(client_ip, username), now)
        ip_failures = self._recent(self._ip_key(client_ip), now)
        return (
            len(account_failures) >= self.max_failures_per_account
            or len(ip_failures) >= self.max_failures_per_ip
        )

    def record_failure(self, client_ip: str, username: str) -> None:
        now = time.monotonic()
        self._prune(now)
        self._failures[self._account_key(client_ip, username)].append(now)
        self._failures[self._ip_key(client_ip)].append(now)

    def reset(self, client_ip: str, username: str) -> None:
        self._failures.pop(self._account_key(client_ip, username), None)

    def clear(self) -> None:
        self._failures.clear()


login_throttle = FailureThrottle(
    max_failures_per_account=5, max_failures_per_ip=20, window_seconds=60
)
# Recovery codes and reset tokens are long-lived secrets: throttle much harder.
recovery_throttle = FailureThrottle(
    max_failures_per_account=5, max_failures_per_ip=10, window_seconds=900
)
