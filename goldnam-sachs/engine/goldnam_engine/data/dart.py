"""Receipt-addressed OpenDART XBRL. Never backdate today's restated API values."""

import io
import math
import re
import zipfile
from datetime import date, datetime, timedelta
from typing import Any

import requests
from defusedxml import ElementTree as ET

from .contracts import DataResult
from .fundamentals import CONCEPTS, Fact, select_pit
from .resilience import ResilientCache

XBRLI = "{http://www.xbrl.org/2003/instance}"
XBRLDI = "{http://xbrl.org/2006/xbrldi}"


def xml_members(content: bytes) -> list[tuple[str, bytes]]:
    # Read in memory: no ZIP paths are ever extracted to disk.
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        infos = [i for i in archive.infolist() if i.filename.lower().endswith((".xml", ".xbrl"))]
        if sum(i.file_size for i in infos) > 100_000_000:
            raise ValueError("XBRL 압축 해제 크기 제한")
        return [(i.filename, archive.read(i)) for i in infos]


def parse_xbrl(content: bytes, filed: date, accession: str) -> list[Fact]:
    root = ET.fromstring(content)
    if root.tag != XBRLI + "xbrl":
        return []
    contexts: dict[str, tuple[date | None, date, bool]] = {}
    for context in root.findall(XBRLI + "context"):
        members = context.findall(".//" + XBRLDI + "explicitMember")
        if context.findall(".//" + XBRLDI + "typedMember"):
            continue
        consolidated = False
        # Reject product/geographic/segment dimensions instead of summing duplicates.
        if members:
            if len(members) != 1:
                continue
            member = members[0]
            axis = member.attrib.get("dimension", "").split(":")[-1]
            value = (member.text or "").split(":")[-1]
            if (
                axis != "ConsolidatedAndSeparateFinancialStatementsAxis"
                or value != "ConsolidatedMember"
            ):
                continue
            consolidated = True
        period = context.find(XBRLI + "period")
        if period is None:
            continue
        end = period.findtext(XBRLI + "instant") or period.findtext(XBRLI + "endDate")
        start = period.findtext(XBRLI + "startDate")
        try:
            if end:
                contexts[context.attrib["id"]] = (
                    date.fromisoformat(start) if start else None,
                    date.fromisoformat(end),
                    consolidated,
                )
        except (KeyError, ValueError):
            continue
    units: dict[str, str] = {}
    for unit in root.findall(XBRLI + "unit"):
        measures = [m.text or "" for m in unit.iter(XBRLI + "measure")]
        if len(measures) == 1:
            units[unit.attrib.get("id", "")] = measures[0].split(":")[-1]
        elif (
            len(measures) == 2 and measures[0].endswith(":KRW") and measures[1].endswith(":shares")
        ):
            units[unit.attrib.get("id", "")] = "KRW/shares"
    mapping = {name: metric for metric, names in CONCEPTS.items() for name in names}
    has_consolidated = any(c[2] for c in contexts.values())
    facts = []
    for element in root:
        name = element.tag.split("}")[-1]
        metric = mapping.get(name)
        context_value = contexts.get(element.attrib.get("contextRef", ""))
        unit_name = units.get(element.attrib.get("unitRef", ""), "")
        if not metric or not context_value or unit_name not in {"KRW", "KRW/shares", "shares"}:
            continue
        start_date, end_date, consolidated = context_value
        if has_consolidated and not consolidated:
            continue
        try:
            numeric = float(element.text or "")
            if math.isfinite(numeric):
                facts.append(
                    Fact(metric, numeric, end_date, filed, start_date, unit_name, accession)
                )
        except ValueError:
            continue
    return facts


class DartClient:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.cache: ResilientCache[dict[str, Any]] = ResilientCache()
        self.corporations: dict[str, str] = {}
        self.receipts: dict[str, list[Fact]] = {}

    def request(self, endpoint: str, **params: str) -> requests.Response:
        # Never include response URL/body in public errors: the query contains a key.
        response = requests.get(
            f"https://opendart.fss.or.kr/api/{endpoint}",
            params={"crtfc_key": self.api_key, **params},
            timeout=25,
        )
        response.raise_for_status()
        return response

    def corp_code(self, symbol: str) -> str | None:
        if not self.corporations:
            for _, content in xml_members(self.request("corpCode.xml").content):
                root = ET.fromstring(content)
                for item in root.findall("list"):
                    stock = (item.findtext("stock_code") or "").strip()
                    corp = (item.findtext("corp_code") or "").strip()
                    if stock and corp:
                        self.corporations[stock] = corp
        return self.corporations.get(symbol.split(".")[0])

    def filings(self, corp: str, as_of: date) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        page = 1
        while True:
            payload = self.request(
                "list.json",
                corp_code=corp,
                bgn_de=(as_of - timedelta(days=3 * 366)).strftime("%Y%m%d"),
                end_de=as_of.strftime("%Y%m%d"),
                pblntf_ty="A",
                last_reprt_at="N",
                page_no=str(page),
                page_count="100",
            ).json()
            if payload.get("status") == "013":
                return result
            if payload.get("status") != "000":
                raise ValueError("OpenDART 공시 조회 실패")
            result.extend(payload.get("list", []))
            if page >= int(payload.get("total_page", 1)):
                return result
            page += 1
            if page > 50:
                raise ValueError("공시 페이지 제한")

    def fetch(self, symbol: str, as_of: date) -> DataResult[dict[str, Any]]:
        corp = self.corp_code(symbol)
        if corp is None:
            return DataResult(None, "OpenDART", status="failed", message="기업 고유번호 없음")
        facts: list[Fact] = []
        failures = 0
        for filing in self.filings(corp, as_of):
            name = str(filing.get("report_nm", ""))
            match = re.search(r"\((\d{4})\.(\d{2})\)", name)
            code = "11011" if "사업보고서" in name else "11012" if "반기보고서" in name else None
            if code is None and "분기보고서" in name and match:
                code = {"03": "11013", "09": "11014"}.get(match[2])
            if code is None:
                # Non-calendar fiscal quarters need a verified report-code mapping.
                continue
            receipt = str(filing.get("rcept_no", ""))
            filed = datetime.strptime(str(filing["rcept_dt"]), "%Y%m%d").date()
            if filed > as_of:
                continue
            try:
                if receipt not in self.receipts:
                    members = xml_members(
                        self.request("fnlttXbrl.xml", rcept_no=receipt, reprt_code=code).content
                    )
                    instances = [parse_xbrl(data, filed, receipt) for _, data in members]
                    instances = [f for f in instances if f]
                    # Multiple statement instances can mix separate/consolidated scopes.
                    # Fail closed until the scope can be verified for that filing.
                    if len(instances) != 1:
                        raise ValueError("XBRL 연결/별도 범위 확인 필요")
                    self.receipts[receipt] = instances[0]
                facts.extend(self.receipts[receipt])
            except Exception:
                failures += 1
        data = select_pit(facts, as_of)
        if not data["provenance"]:
            return DataResult(
                None,
                "OpenDART",
                as_of=as_of,
                status="failed",
                message="사용 가능한 접수일 기준 XBRL 없음",
            )
        return DataResult(
            data,
            "OpenDART",
            as_of=as_of,
            status="partial" if failures else "ok",
            message=f"읽지 못한 공시 {failures}건" if failures else "",
        )

    def fundamentals(self, symbol: str, as_of: date) -> DataResult[dict[str, Any]]:
        return self.cache.get(
            f"{symbol}:{as_of}",
            [("OpenDART", lambda: self.fetch(symbol, as_of))],
            timedelta(hours=24),
        )
