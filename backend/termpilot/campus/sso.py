"""Central Authentication Service (CAS) sign-in.

The flow mirrors a browser: load the sign-in form to obtain its ``execution``
token, post the credentials, then trade the ticket-granting cookie for a
service ticket per campus service and follow it so the service sets its own
session cookies. Only those service cookies are kept; the password never
leaves this module.
"""

from __future__ import annotations

import logging
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests

from termpilot.campus.records import CampusCookies
from termpilot.errors import NotAuthenticated, UpstreamFailure
from termpilot.settings import Settings

logger = logging.getLogger(__name__)

_EXECUTION = re.compile(r'name="execution"\s+value="([^"]+)"')


class InvalidCampusCredentials(NotAuthenticated):
    code = "invalid_credentials"


def service_entry_points(settings: Settings) -> dict[str, str]:
    return {
        "lms": f"{settings.campus_lms_url}/webapps/bb-sso-BBLEARN/index.jsp",
        "records": f"{settings.campus_records_url}/cas",
    }


def _with_ticket(url: str, ticket: str) -> str:
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["ticket"] = ticket
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


class CampusSignIn:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _session(self) -> requests.Session:
        session = requests.Session()
        session.headers["User-Agent"] = self.settings.campus_user_agent
        return session

    def _call(self, session: requests.Session, method: str, url: str, **kwargs) -> requests.Response:
        kwargs.setdefault("timeout", self.settings.campus_timeout_seconds)
        kwargs.setdefault("verify", self.settings.campus_verify_tls)
        try:
            return session.request(method, url, **kwargs)
        except requests.RequestException as exc:
            raise UpstreamFailure("The campus sign-in service could not be reached.") from exc

    def sign_in(self, username: str, password: str) -> CampusCookies:
        """Authenticate and collect cookies for every reachable service.

        Raises :class:`InvalidCampusCredentials` when the account is rejected
        and :class:`UpstreamFailure` when no service accepted the ticket.
        """
        entry_points = service_entry_points(self.settings)
        sso = self._session()
        form = self._call(sso, "GET", self.settings.campus_sso_url, params={"service": entry_points["lms"]})
        if form.status_code != 200:
            raise UpstreamFailure("The campus sign-in page is unavailable right now.")
        match = _EXECUTION.search(form.text)
        submitted = self._call(
            sso,
            "POST",
            self.settings.campus_sso_url,
            data={
                "username": username,
                "password": password,
                "execution": match.group(1) if match else "",
                "_eventId": "submit",
                "geolocation": "",
            },
            allow_redirects=False,
        )
        if submitted.status_code != 302 or "Location" not in submitted.headers:
            raise InvalidCampusCredentials("The campus account or password is incorrect.")

        cookies = CampusCookies()
        for name, entry in entry_points.items():
            try:
                cookies.services[name] = self._open_service(sso, entry)
            except UpstreamFailure as exc:
                logger.warning("Campus service %s did not accept the ticket: %s", name, exc.message)
        if not any(cookies.services.values()):
            raise UpstreamFailure("Signed in, but no campus service accepted the session.")
        return cookies

    def _open_service(self, sso: requests.Session, entry: str) -> dict[str, str]:
        redirect = self._call(
            sso, "GET", self.settings.campus_sso_url, params={"service": entry}, allow_redirects=False
        )
        location = redirect.headers.get("Location", "")
        ticket = dict(parse_qsl(urlsplit(location).query)).get("ticket")
        if redirect.status_code != 302 or not ticket:
            raise UpstreamFailure("No service ticket was issued.")
        service = self._session()
        landing = self._call(service, "GET", _with_ticket(entry, ticket), allow_redirects=True)
        if landing.status_code != 200:
            raise UpstreamFailure(f"The service answered {landing.status_code}.")
        host = urlsplit(entry).netloc.lower()
        return {
            cookie.name: cookie.value
            for cookie in service.cookies
            if cookie.value and (host.endswith(cookie.domain.lstrip(".").lower()) or not cookie.domain)
        }
