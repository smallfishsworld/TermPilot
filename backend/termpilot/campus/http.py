"""HTTP plumbing shared by the campus adapters."""

from __future__ import annotations

from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from termpilot.errors import CampusSessionExpired, UpstreamFailure
from termpilot.settings import Settings


class CampusHttp:
    """A ``requests`` session preconfigured for one campus service.

    Requests retry idempotent failures, honour the TLS setting and convert
    network errors into :class:`UpstreamFailure`. A response that lands on the
    single sign-on page means the stored cookies expired.
    """

    def __init__(self, settings: Settings, cookies: dict[str, str] | None = None) -> None:
        self.settings = settings
        self.session = requests.Session()
        self.session.headers["User-Agent"] = settings.campus_user_agent
        retry = Retry(
            total=2,
            backoff_factor=0.4,
            status_forcelist=(502, 503, 504),
            allowed_methods=frozenset({"GET", "POST"}),
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retry))
        self.session.mount("http://", HTTPAdapter(max_retries=retry))
        if cookies:
            self.session.cookies.update(cookies)

    def request(self, method: str, url: str, *, what: str, **kwargs: Any) -> requests.Response:
        kwargs.setdefault("timeout", self.settings.campus_timeout_seconds)
        kwargs.setdefault("verify", self.settings.campus_verify_tls)
        try:
            response = self.session.request(method, url, **kwargs)
        except requests.RequestException as exc:
            raise UpstreamFailure(f"Could not reach the campus service while loading {what}.") from exc
        if self._landed_on_sign_in(response):
            raise CampusSessionExpired("The campus session has expired. Sign in again to refresh it.")
        if response.status_code in (401, 403):
            raise CampusSessionExpired("The campus service rejected the stored session.")
        if response.status_code >= 400:
            raise UpstreamFailure(f"The campus service answered {response.status_code} while loading {what}.")
        return response

    def get(self, url: str, *, what: str, **kwargs: Any) -> requests.Response:
        return self.request("GET", url, what=what, **kwargs)

    def post(self, url: str, *, what: str, **kwargs: Any) -> requests.Response:
        return self.request("POST", url, what=what, **kwargs)

    def json(self, response: requests.Response, *, what: str) -> Any:
        try:
            return response.json()
        except ValueError as exc:
            raise UpstreamFailure(f"The campus service returned an unreadable {what}.") from exc

    def _landed_on_sign_in(self, response: requests.Response) -> bool:
        sso_host = self.settings.campus_sso_url.split("/")[2]
        return sso_host in response.url and "login" in response.url.lower()
