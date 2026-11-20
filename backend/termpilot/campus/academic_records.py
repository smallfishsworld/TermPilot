"""Client for the academic records system: profile, timetable, GPA, credits, photo.

The records system answers with terse pinyin abbreviations (``xm`` for name,
``kbxx`` for a timetable cell). Each ``parse_*`` function converts one payload
into plain records and is pure, so it can be tested with captured samples.
"""

from __future__ import annotations

import logging
import re
from datetime import date
from typing import Any

from termpilot.campus import codebook
from termpilot.campus.http import CampusHttp
from termpilot.campus.periods import parse_period_range, parse_weeks, period_times
from termpilot.campus.records import ClassMeeting, CreditRecord, GpaRecord, Photo, ProfileRecord
from termpilot.campus.terms import Term
from termpilot.settings import Settings

logger = logging.getLogger(__name__)

_BRACKETED = re.compile(r"\[([^\]]*)\]")
_WEEKDAY_KEY = re.compile(r"xq(\d)")


def _text(raw: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = raw.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _gender(code: str | None) -> str | None:
    if code in {"1", "男"}:
        return "male"
    if code in {"2", "女"}:
        return "female"
    return code


def _birth_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def parse_profile(payload: Any) -> ProfileRecord:
    raw = payload[0] if isinstance(payload, list) and payload else payload
    if not isinstance(raw, dict):
        return ProfileRecord()
    college_code = _text(raw, "sssym", "xy")
    department_code = _text(raw, "yxm", "yxh")
    class_code = _text(raw, "bjm")
    return ProfileRecord(
        name=_text(raw, "xm"),
        english_name=_text(raw, "xm_en"),
        pinyin_name=_text(raw, "xmpy"),
        gender=_gender(_text(raw, "xbm", "xb")),
        birth_date=_birth_date(_text(raw, "csrq")),
        email=_text(raw, "dzyx", "email"),
        phone=_text(raw, "lxdh", "sjh"),
        college=codebook.lookup("colleges", college_code) or college_code,
        department=(
            _text(raw, "yxmc_en", "zymc_en")
            or codebook.lookup("departments", department_code)
            or _text(raw, "zymc", "yxmc")
            or department_code
        ),
        class_name=codebook.lookup("classes", class_code) or _text(raw, "bj"),
        dormitory=_text(raw, "ssh"),
        internal_id=_text(raw, "id"),
    )


def parse_timetable_cell(cell: str, key: str) -> ClassMeeting | None:
    """Turn one timetable cell into a meeting; ``None`` when it cannot be placed.

    A cell reads, line by line: course title, ``[instructor]`` and a final line
    of bracketed fields such as ``[1-16周][Lecture Hall 1][3-4节]``.
    """
    lines = [line.strip() for line in cell.splitlines() if line.strip()]
    weekday_match = _WEEKDAY_KEY.search(key or "")
    if not lines or not weekday_match:
        return None
    weekday = int(weekday_match.group(1))
    if not 1 <= weekday <= 7:
        return None
    instructor = None
    if len(lines) > 2:
        named = _BRACKETED.search(lines[1])
        instructor = (named.group(1) if named else lines[1]).strip() or None
    fields = _BRACKETED.findall(lines[-1])
    week_text = next((item for item in fields if "周" in item), None)
    period_text = next((item for item in fields if "节" in item), None)
    location = next((item for item in fields if item not in (week_text, period_text) and item), None)
    periods = parse_period_range(period_text)
    if periods is None:
        return None
    starts_at, ends_at = period_times(*periods)
    return ClassMeeting(
        title=lines[0],
        weekday=weekday,
        starts_at=starts_at,
        ends_at=ends_at,
        first_period=periods[0],
        last_period=periods[1],
        weeks=parse_weeks(week_text),
        week_label=week_text,
        location=location,
        instructor=instructor,
    )


def parse_timetable(payload: Any) -> tuple[list[ClassMeeting], int]:
    """Meetings plus the number of cells that had no usable weekday or period."""
    rows = payload.get("content") if isinstance(payload, dict) else payload
    meetings: list[ClassMeeting] = []
    skipped = 0
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict) or not row.get("kbxx"):
            continue
        meeting = parse_timetable_cell(str(row["kbxx"]), str(row.get("key") or ""))
        if meeting is None:
            skipped += 1
        else:
            meetings.append(meeting)
    return meetings, skipped


def parse_gpa(payload: Any) -> GpaRecord:
    block = payload.get("xfjandpm") if isinstance(payload, dict) else None
    if not isinstance(block, dict):
        return GpaRecord(gpa=None, rank=None)
    try:
        gpa = float(block.get("PJXFJ")) if block.get("PJXFJ") not in (None, "") else None
    except (TypeError, ValueError):
        gpa = None
    rank = block.get("PM")
    return GpaRecord(gpa=gpa, rank=str(rank) if rank not in (None, "") else None)


def parse_credit_page(payload: Any) -> list[dict[str, Any]]:
    content = payload.get("content") if isinstance(payload, dict) else None
    rows = content.get("list") if isinstance(content, dict) else None
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def summarise_credits(rows: list[dict[str, Any]]) -> CreditRecord:
    by_category: dict[str, float] = {}
    for row in rows:
        try:
            credit = float(row.get("xf") or 0)
        except (TypeError, ValueError):
            continue
        category = str(row.get("kclb") or "Other").strip() or "Other"
        by_category[category] = round(by_category.get(category, 0.0) + credit, 2)
    return CreditRecord(total=round(sum(by_category.values()), 2), by_category=by_category)


class AcademicRecordsClient:
    def __init__(self, settings: Settings, cookies: dict[str, str]) -> None:
        self.base = settings.campus_records_url
        self.http = CampusHttp(settings, cookies)
        self.http.session.headers.update({"Referer": f"{self.base}/", "Origin": self.base})

    def profile(self) -> ProfileRecord:
        response = self.http.post(
            f"{self.base}/xjgl/fxzygl/getxjxx",
            json={"page": 1, "limit": 100, "sort": "id", "order": "desc"},
            what="the student profile",
        )
        return parse_profile(self.http.json(response, what="profile"))

    def timetable(self, term: Term) -> tuple[list[ClassMeeting], int]:
        response = self.http.post(
            f"{self.base}/Xskbcx/queryXskbcxList",
            data={"bs": "2", "xn": term.academic_year, "xq": term.records_code},
            headers={"X-Requested-With": "XMLHttpRequest", "Referer": f"{self.base}/webroot/decision/"},
            what="the timetable",
        )
        return parse_timetable(self.http.json(response, what="timetable"))

    def gpa(self) -> GpaRecord:
        response = self.http.post(
            f"{self.base}/cjgl/xscjgl/xsgrcjcx/queryXnAndXqXfj",
            headers={"X-Requested-With": "XMLHttpRequest"},
            what="the GPA summary",
        )
        return parse_gpa(self.http.json(response, what="GPA summary"))

    def credits(self, page_size: int = 100, max_pages: int = 10) -> CreditRecord:
        rows: list[dict[str, Any]] = []
        for page in range(1, max_pages + 1):
            response = self.http.post(
                f"{self.base}/cjgl/grcjcx/grcjcx",
                json={
                    "xn": None,
                    "xq": None,
                    "kcmc": None,
                    "cxbj": "-1",
                    "pylx": "1",
                    "current": page,
                    "pageSize": page_size,
                    "sffx": None,
                },
                headers={
                    "X-Requested-With": "XMLHttpRequest",
                    "Rolecode": "01",
                    "Referer": f"{self.base}/cjgl/grcjcx/go/1",
                },
                what="the course results",
            )
            batch = parse_credit_page(self.http.json(response, what="course results"))
            rows.extend(batch)
            if len(batch) < page_size:
                break
        return summarise_credits(rows)

    def photo(self, internal_id: str) -> Photo | None:
        response = self.http.post(
            f"{self.base}/xjgl/xjxxgl/xsxxdate/initxszp", json={"id": internal_id}, what="the photo"
        )
        path = self.http.json(response, what="photo record").get("rxzp")
        if not isinstance(path, str) or not path.strip():
            return None
        image = self.http.get(f"{self.base}{path}" if path.startswith("/") else path, what="the photo")
        media_type = image.headers.get("Content-Type", "image/jpeg").split(";")[0].strip()
        return Photo(content=image.content, media_type=media_type or "image/jpeg")
