"""Client for the learning management platform: courses, calendar, grades, files."""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import unquote, urljoin, urlparse
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from termpilot.campus.http import CampusHttp
from termpilot.campus.records import LmsCourse, LmsEvent, LmsGradeItem, LmsMaterial
from termpilot.clock import as_utc
from termpilot.errors import UpstreamFailure
from termpilot.settings import Settings

logger = logging.getLogger(__name__)

_COURSE_ID = (
    re.compile(r"[?&]course_id=(_\d+_\d+)"),
    re.compile(r"[?&]id=(_\d+_\d+)"),
    re.compile(r"/ultra/courses?/(_\d+_\d+)"),
)
_FILE_SUFFIXES = (
    ".pdf",
    ".ppt",
    ".pptx",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".zip",
    ".rar",
    ".7z",
    ".txt",
    ".md",
    ".png",
    ".jpg",
    ".jpeg",
    ".mp4",
    ".ipynb",
    ".py",
    ".c",
    ".java",
)
_DATE_WORDS = re.compile(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2},\s+20\d{2}\b", re.I)
_CLOCK = re.compile(r"\b\d{1,2}:\d{2}\s*(am|pm)?\b", re.I)
_STATUS_WORDS = re.compile(r"\b(graded|submitted|needs grading|upcoming|in progress)\b", re.I)
_FRACTION = re.compile(r"(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)")
_YEAR = re.compile(r"\b20[0-9][0-9]\b")
_LETTER_GRADE = re.compile(r"[A-DF][+-]?", re.I)
_NUMBER = re.compile(r"[0-9]+(?:\.[0-9]+)?")
# Blackboard puts dates, times and status words in the same cell as the item name.
_NAME_NOISE = (_DATE_WORDS, _CLOCK, _STATUS_WORDS, _FRACTION)


def course_ref_from_url(url: str) -> str | None:
    decoded = unquote(url)
    for pattern in _COURSE_ID:
        match = pattern.search(decoded)
        if match:
            return match.group(1)
    return None


def parse_course_module(body: str, base_url: str) -> list[LmsCourse]:
    """Read the portal's "My Courses" module, which arrives as HTML inside XML."""
    embedded = re.search(r"<contents[^>]*>([\s\S]*?)</contents>", body, re.I)
    html = embedded.group(1) if embedded else body
    html = html.strip()
    if html.startswith("<![CDATA[") and html.endswith("]]>"):
        html = html[9:-3]
    courses: dict[str, LmsCourse] = {}
    for anchor in BeautifulSoup(html, "html.parser").find_all("a", href=True):
        title = anchor.get_text(" ", strip=True)
        url = urljoin(base_url, anchor["href"].strip())
        ref = course_ref_from_url(url)
        if ref and title and ref not in courses:
            courses[ref] = LmsCourse(ref=ref, title=title, url=url)
    return list(courses.values())


def in_term(course: LmsCourse, labels: tuple[str, ...]) -> bool:
    return any(label in course.title for label in labels)


def _parse_local_time(value: Any, tz: ZoneInfo) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return as_utc(parsed, assume=tz)


def parse_calendar(payload: Any, tz: ZoneInfo) -> list[LmsEvent]:
    events: list[LmsEvent] = []
    for raw in payload if isinstance(payload, list) else []:
        if not isinstance(raw, dict) or not raw.get("title"):
            continue
        due_at = _parse_local_time(raw.get("end"), tz) or _parse_local_time(raw.get("start"), tz)
        if due_at is None:
            continue
        title = str(raw["title"]).strip()
        ref = str(raw.get("id") or raw.get("itemSourceId") or "").strip()
        if not ref:
            ref = hashlib.sha1(f"{title}|{due_at.isoformat()}".encode()).hexdigest()[:20]
        events.append(
            LmsEvent(
                ref=ref,
                title=title,
                due_at=due_at,
                course=(str(raw.get("calendarName") or "").strip() or None),
                category=(str(raw.get("eventType") or "").strip() or None),
                color=(str(raw.get("color") or "").strip() or None),
            )
        )
    return events


def normalise_score(raw: str) -> str | None:
    """Return a display score, or ``None`` when the cell holds a date or a status."""
    text = " ".join(raw.split())
    if text in {"", "-", "–", "—"} or _DATE_WORDS.search(text) or _CLOCK.search(text):
        return None
    if _YEAR.search(text):
        return None
    if fraction := _FRACTION.search(text):
        earned, total = (float(part) for part in fraction.groups())
        return f"{earned:g}/{total:g}"
    if _LETTER_GRADE.fullmatch(text):
        return text.upper()
    if _NUMBER.fullmatch(text):
        return f"{float(text):g}"
    return None


def _grade_item_title(cell: str) -> str:
    for pattern in _NAME_NOISE:
        cell = pattern.sub("", cell)
    return " ".join(cell.split())


def parse_grade_page(html: bytes | str, course: LmsCourse) -> list[LmsGradeItem]:
    soup = BeautifulSoup(html, "html.parser")
    rows = [row for block in soup.select("div.gradeTableNew") for row in block.find_all(["div", "tr"])]
    if not rows:
        rows = [row for table in soup.find_all("table") for row in table.find_all("tr")]
    items: dict[str, LmsGradeItem] = {}
    for row in rows:
        cells = [cell.get_text(" ", strip=True) for cell in row.find_all(["div", "td", "th"], recursive=False)]
        if len(cells) < 2:
            cells = [cell.get_text(" ", strip=True) for cell in row.find_all(["div", "td", "th"])]
        if len(cells) < 2:
            continue
        name = _grade_item_title(cells[0])
        if not name or name in items:
            continue
        score = next((value for value in map(normalise_score, cells[1:]) if value), None)
        if score:
            items[name] = LmsGradeItem(course.ref, course.title, name, score)
    return list(items.values())


def _looks_like_file(url: str) -> bool:
    parsed = urlparse(url)
    path = parsed.path.lower()
    return path.endswith(_FILE_SUFFIXES) or "bbcswebdav" in path or "download" in parsed.query.lower()


def _material_title(url: str, text: str) -> str:
    title = re.sub(r"[<>:\"/\\|?*]", "_", " ".join(text.split())).strip(". ")
    suffix = "." + urlparse(url).path.rsplit(".", 1)[-1].lower() if "." in urlparse(url).path.rsplit("/", 1)[-1] else ""
    if title:
        return title if not suffix or title.lower().endswith(suffix) else f"{title}{suffix}"
    return unquote(urlparse(url).path.rsplit("/", 1)[-1]) or "file"


class LearningPlatformClient:
    def __init__(self, settings: Settings, cookies: dict[str, str]) -> None:
        self.settings = settings
        self.base = settings.campus_lms_url
        self.http = CampusHttp(settings, cookies)

    def courses(self) -> list[LmsCourse]:
        response = self.http.post(
            f"{self.base}/webapps/portal/execute/tabs/tabAction",
            data={"action": "refreshAjaxModule", "modId": "_3_1", "tabId": "_1_1"},
            headers={"X-Requested-With": "XMLHttpRequest"},
            what="the course list",
        )
        return parse_course_module(response.text, f"{self.base}/")

    def calendar(self, around: datetime, days: int = 60) -> list[LmsEvent]:
        start = around - timedelta(days=days // 2)
        end = around + timedelta(days=days)
        response = self.http.get(
            f"{self.base}/webapps/calendar/calendarData/selectedCalendarEvents",
            params={
                "start": int(start.timestamp() * 1000),
                "end": int(end.timestamp() * 1000),
                "course_id": "",
                "mode": "personal",
            },
            headers={"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"},
            what="the calendar",
        )
        return parse_calendar(self.http.json(response, what="calendar"), self.settings.tz)

    def grades(self, courses: list[LmsCourse]) -> list[LmsGradeItem]:
        items: list[LmsGradeItem] = []
        for course in courses:
            try:
                page = self.http.get(
                    f"{self.base}/webapps/bb-mygrades-BBLEARN/myGrades",
                    params={"course_id": course.ref, "stream_name": "mygrades"},
                    what=f"grades of {course.title}",
                )
            except UpstreamFailure as exc:
                logger.info("Skipping grades for %s: %s", course.title, exc.message)
                continue
            items.extend(parse_grade_page(page.content, course))
        return items

    def materials(self, courses: list[LmsCourse], pages_per_course: int = 15) -> list[LmsMaterial]:
        found: dict[str, LmsMaterial] = {}
        for course in courses:
            try:
                landing = self.http.get(course.url, what=f"the page of {course.title}")
            except UpstreamFailure as exc:
                logger.info("Skipping materials for %s: %s", course.title, exc.message)
                continue
            soup = BeautifulSoup(landing.text, "html.parser")
            sections: dict[str, str] = {}
            for anchor in soup.find_all("a", href=True):
                href = anchor["href"]
                if any(token in href.lower() for token in ("listcontent", "coursecontent")):
                    sections.setdefault(urljoin(landing.url, href), anchor.get_text(" ", strip=True) or "Content")
            for section_url, section_name in list(sections.items())[:pages_per_course]:
                try:
                    page = self.http.get(section_url, what=f"{section_name} in {course.title}")
                except UpstreamFailure:
                    continue
                for anchor in BeautifulSoup(page.text, "html.parser").find_all("a", href=True):
                    url = urljoin(page.url, anchor["href"].strip())
                    if url in found or not _looks_like_file(url):
                        continue
                    found[url] = LmsMaterial(
                        course_title=course.title,
                        section=section_name,
                        title=_material_title(url, anchor.get_text(" ", strip=True)),
                        url=url,
                    )
        return list(found.values())
