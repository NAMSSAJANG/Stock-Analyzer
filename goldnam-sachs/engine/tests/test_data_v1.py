from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from unittest.mock import Mock
from zipfile import ZipFile

import numpy as np
import pandas as pd
import pytest
from goldnam_engine.data.contracts import DataResult
from goldnam_engine.data.dart import DartClient, parse_xbrl, xml_members
from goldnam_engine.data.fundamentals import (
    DartFundamentals,
    Fact,
    SecFundamentals,
    parse_sec_facts,
    select_pit,
)
from goldnam_engine.data.market_data import (
    CurrentFundamentals,
    FdrPrices,
    Fx,
    Prices,
    YahooCalendar,
    YahooPrices,
)
from goldnam_engine.data.parquet_cache import ParquetCache
from goldnam_engine.data.quality import calendar, market_for, price_ttl, validate_prices
from goldnam_engine.data.resilience import ResilientCache
from goldnam_engine.data.universe import Universes, serialize

UTC = timezone.utc
NOW = datetime(2026, 1, 8, 22, tzinfo=UTC)


def frame():
    dates = calendar("us").sessions_in_range("2026-01-02", "2026-01-08")
    return pd.DataFrame(
        {"Open": 100.0, "High": 102.0, "Low": 98.0, "Close": 101.0, "Volume": 1000.0}, index=dates
    )


def test_failure_negative_cache_and_fallback_expiry():
    clock = [NOW]
    cache = ResilientCache(clock=lambda: clock[0], wait=lambda _: None)
    first = Mock(return_value=DataResult(None, "a", status="failed"))
    second = Mock(return_value=DataResult(42, "b"))
    assert cache.get("x", [("a", first), ("b", second)], timedelta(seconds=1)).data == 42
    assert first.call_count == 3 and second.call_count == 1
    assert cache.get("x", [("a", first)], timedelta(seconds=1)).data == 42
    clock[0] += timedelta(seconds=2)
    second.return_value = DataResult(None, "b", status="failed")
    result = cache.get("x", [("a", first), ("b", second)], timedelta(seconds=1))
    assert result.status == "stale" and result.data == 42
    assert first.call_count == 3  # open circuit
    assert cache.get("missing", [("b", second)], timedelta(hours=1)).status == "failed"
    assert "missing" not in cache.success
    count = second.call_count
    cache.get("missing", [("b", second)], timedelta(hours=1))
    assert second.call_count == count
    clock[0] += timedelta(minutes=6)
    second.return_value = DataResult(43, "b")
    assert cache.get("missing", [("b", second)], timedelta(hours=1)).data == 43


def test_stale_tries_fresh_provider_and_exception_redaction():
    cache = ResilientCache(wait=lambda _: None)

    def stale():
        return DataResult(1, "a", status="stale")

    def good():
        return DataResult(2, "b")

    assert cache.get("x", [("a", stale), ("b", good)], timedelta(hours=1)).data == 2
    bad = Mock(side_effect=RuntimeError("secret-token-in-url"))
    result = cache.get("y", [("c", bad)], timedelta(hours=1))
    assert result.status == "failed" and "secret-token" not in result.message
    assert cache.get("z", [("a", stale)], timedelta(hours=1)).status == "stale"
    assert "z" not in cache.success


def test_quality_exchange_sessions_and_stale():
    d = frame()
    assert validate_prices(d, "fixture", "us", date(2026, 1, 8)).status == "ok"
    assert validate_prices(d, "fixture", "us", date(2026, 1, 20)).status == "stale"
    assert validate_prices(d.iloc[[0, -1]], "f", "us", date(2026, 1, 8)).status == "partial"
    assert validate_prices(d.iloc[::-1], "f", "us", date(2026, 1, 8)).status == "failed"
    assert validate_prices(pd.concat([d, d]), "f", "us", date(2026, 1, 8)).status == "failed"
    for column, value in [("Close", np.nan), ("Open", 0), ("High", 90), ("Low", 110)]:
        bad = d.copy()
        bad.iloc[0, bad.columns.get_loc(column)] = value
        assert validate_prices(bad, "f", "us", date(2026, 1, 8)).data is None
    d.iloc[-1, :4] *= 2
    d.iloc[0, 4] = 0
    result = validate_prices(d, "f", "us", date(2026, 1, 8))
    assert "급변" in result.message and "거래량" in result.message
    assert validate_prices(pd.DataFrame(), "f", "us", date.today()).status == "failed"
    assert market_for("005930.KS") == "kr" and market_for("005930") == "kr"
    assert market_for("AAPL") == "us"
    assert price_ttl("us", NOW) > timedelta(hours=20)
    assert date(2026, 1, 1) not in calendar("kr").sessions_in_range("2026-01-01", "2026-01-05").date
    with pytest.raises(ValueError):
        calendar("bad")


def test_parquet_preserves_timestamps_and_never_stores_failure(tmp_path):
    cache = ParquetCache(tmp_path)
    result = DataResult(frame(), "f", NOW, date(2026, 1, 8), "partial", "volume")
    cache.write("../../symbol", NOW, result)
    expires, loaded = cache.read("../../symbol")
    assert expires == NOW and loaded.fetched_at == NOW and loaded.status == "partial"
    pd.testing.assert_frame_equal(loaded.data, result.data, check_freq=False)
    cache.write("bad", NOW, DataResult(None, "f", status="failed"))
    assert cache.read("bad") is None
    cache.path("broken").write_bytes(b"broken")
    assert cache.read("broken") is None


def test_price_adapters_contracts_and_disk_restart(tmp_path, monkeypatch):
    import FinanceDataReader as fdr
    import yfinance as yf

    yfcall = Mock(return_value=frame())
    fdrcall = Mock(return_value=frame())
    monkeypatch.setattr(yf, "download", yfcall)
    monkeypatch.setattr(fdr, "DataReader", fdrcall)
    start, end = date(2026, 1, 2), date(2026, 1, 8)
    assert YahooPrices().prices("AAPL", start, end).usable
    assert yfcall.call_args.kwargs["end"] == "2026-01-09"
    assert yfcall.call_args.kwargs["auto_adjust"] is True
    assert FdrPrices().prices("005930.KS", start, end).usable
    assert fdrcall.call_args.args[0] == "005930"
    provider = Prices(tmp_path)
    assert provider.prices("AAPL", start, end).usable
    count = yfcall.call_count
    assert Prices(tmp_path).prices("AAPL", start, end).usable
    assert yfcall.call_count == count
    yfcall.return_value = None
    assert YahooPrices().prices("AAPL", start, end).status == "failed"


def test_calendar_fx_current_fundamentals(monkeypatch):
    import FinanceDataReader as fdr
    import yfinance as yf

    ticker = Mock(
        calendar={"Earnings Date": [date.today() + timedelta(days=1)]}, info={"marketCap": 100}
    )
    monkeypatch.setattr(yf, "Ticker", Mock(return_value=ticker))
    assert YahooCalendar().earnings("AAPL").usable
    assert YahooCalendar().earnings("005930.KS").status == "failed"
    ticker.calendar = {}
    assert not YahooCalendar().earnings("AAPL").usable
    monkeypatch.setattr(yf, "Ticker", Mock(side_effect=ValueError("bad")))
    assert not YahooCalendar().earnings("AAPL").usable
    monkeypatch.setattr(yf, "Ticker", Mock(return_value=ticker))
    current = CurrentFundamentals().get("AAPL")
    assert current.status == "partial" and "과거" in current.message
    ticker.info = {}
    provider = CurrentFundamentals()
    provider.cache.wait = lambda _: None
    assert provider.get("AAPL").status == "failed"
    monkeypatch.setattr(YahooPrices, "prices", Mock(return_value=DataResult(frame(), "yf")))
    assert Fx().usd_krw().data == 101
    monkeypatch.setattr(
        YahooPrices, "prices", Mock(return_value=DataResult(None, "yf", status="failed"))
    )
    rates = pd.DataFrame({"Close": [1400.0]}, index=pd.to_datetime([date.today()]))
    monkeypatch.setattr(fdr, "DataReader", Mock(return_value=rates))
    fx = Fx()
    fx.cache.wait = lambda _: None
    assert fx.usd_krw().data == 1400
    rates.index = pd.to_datetime(["2020-01-01"])
    assert Fx()._fetch("FinanceDataReader").status == "stale"
    rates.iloc[0, 0] = -1
    assert Fx()._fetch("FinanceDataReader").status == "failed"
    monkeypatch.setattr(fdr, "DataReader", Mock(return_value=pd.DataFrame()))
    assert Fx()._fetch("FinanceDataReader").status == "failed"


def test_pit_never_uses_later_revision_or_current_snapshot():
    f = Fact("assets", 100, date(2024, 12, 31), date(2025, 2, 1), None, "USD", "original")
    revision = Fact("assets", 900, f.end, date(2025, 8, 1), None, "USD", "revision")
    assert "assets" not in select_pit([f, revision], date(2025, 1, 31))
    assert select_pit([f, revision], date(2025, 4, 1))["assets"] == 100
    assert select_pit([f, revision], date(2025, 9, 1))["assets"] == 900
    flows = [
        Fact("revenue", 40, date(2025, 3, 31), date(2025, 5, 1), date(2025, 1, 1), "USD", "q"),
        Fact("revenue", 20, date(2024, 3, 31), date(2024, 5, 1), date(2024, 1, 1), "USD", "p"),
    ]
    assert select_pit(flows, date(2025, 6, 1))["revenue_growth"] == 1
    assert "revenue" not in select_pit(flows, date(2025, 6, 1))  # not quarter/year mixing
    payload = {
        "facts": {
            "us-gaap": {
                "Assets": {
                    "units": {
                        "USD": [
                            {"val": 100, "end": "2024-12-31", "filed": "2025-02-01", "accn": "a"},
                            {"bad": True},
                        ],
                        "EUR": [],
                    }
                }
            }
        }
    }
    assert len(parse_sec_facts(payload)) == 1


def test_sec_requests_and_missing_credentials(monkeypatch):
    assert SecFundamentals("").fundamentals("AAPL", date.today()).status == "failed"
    assert DartFundamentals("").fundamentals("005930", date.today()).status == "failed"
    client = SecFundamentals("test test@example.com")
    response = Mock()
    response.json.side_effect = [
        {"0": {"ticker": "AAPL", "cik_str": 320193}},
        {
            "facts": {
                "us-gaap": {
                    "Assets": {
                        "units": {"USD": [{"val": 100, "end": "2024-12-31", "filed": "2025-02-01"}]}
                    }
                }
            }
        },
    ]
    call = Mock(return_value=response)
    monkeypatch.setattr("requests.get", call)
    assert client.fundamentals("AAPL", date(2025, 1, 1)).status == "failed"
    assert client.fundamentals("AAPL", date(2025, 3, 1)).data["assets"] == 100
    assert call.call_count == 2
    assert "CIK0000320193.json" in call.call_args.args[0]
    assert "@" in call.call_args.kwargs["headers"]["User-Agent"]
    client.cache.wait = lambda _: None
    assert client.raw("missing").status == "failed"


XBRL = b"""<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:ifrs="http://xbrl.ifrs.org/taxonomy" xmlns:iso4217="http://www.xbrl.org/2003/iso4217">
<xbrli:context id="c"><xbrli:entity/><xbrli:period><xbrli:instant>2024-12-31</xbrli:instant></xbrli:period></xbrli:context>
<xbrli:unit id="krw"><xbrli:measure>iso4217:KRW</xbrli:measure></xbrli:unit>
<ifrs:Assets contextRef="c" unitRef="krw">100</ifrs:Assets></xbrli:xbrl>"""


def zipped(name, content):
    out = BytesIO()
    with ZipFile(out, "w") as archive:
        archive.writestr(name, content)
    return out.getvalue()


def test_dart_receipt_pit_and_xml_security(monkeypatch):
    facts = parse_xbrl(XBRL, date(2025, 3, 1), "receipt")
    assert facts[0].value == 100 and facts[0].filed == date(2025, 3, 1)
    assert not parse_xbrl(b"<root/>", date.today(), "x")
    assert xml_members(zipped("../../data.xbrl", XBRL))[0][1] == XBRL
    from defusedxml.common import DefusedXmlException

    with pytest.raises(DefusedXmlException):
        parse_xbrl(
            b'<!DOCTYPE x [<!ENTITY x SYSTEM "file:///etc/passwd">]><x>&x;</x>', date.today(), "x"
        )
    client = DartClient("test-only")
    corp = b"<result><list><corp_code>00001234</corp_code><stock_code>005930</stock_code></list></result>"
    filings = {
        "status": "000",
        "total_page": 1,
        "list": [
            {
                "report_nm": "사업보고서 (2024.12)",
                "rcept_no": "20250301000001",
                "rcept_dt": "20250301",
            }
        ],
    }

    def request(endpoint, **kwargs):
        if endpoint == "corpCode.xml":
            return Mock(content=zipped("CORPCODE.xml", corp))
        if endpoint == "list.json":
            assert kwargs["last_reprt_at"] == "N"
            return Mock(json=lambda: filings)
        assert endpoint == "fnlttXbrl.xml" and kwargs["rcept_no"] == "20250301000001"
        return Mock(content=zipped("report.xbrl", XBRL))

    monkeypatch.setattr(client, "request", request)
    assert client.fetch("005930.KS", date(2025, 2, 1)).status == "failed"
    assert client.fundamentals("005930.KS", date(2025, 4, 1)).data["assets"] == 100
    assert client.fetch("bad", date.today()).status == "failed"
    filings["status"] = "013"
    assert client.filings("corp", date.today()) == []
    filings["status"] = "020"
    with pytest.raises(ValueError):
        client.filings("corp", date.today())


def test_universe_snapshot_fallback_and_json_null(tmp_path, monkeypatch):
    provider = Universes(tmp_path)
    monkeypatch.setattr(
        provider, "_fetch", lambda _: pd.DataFrame({"symbol": ["AAPL"], "name": ["Apple"]})
    )
    result = provider.constituents("us", date.today())
    assert result.data.iloc[0].membership_as_of == date.today().isoformat()
    assert "생존 편향" in result.message
    monkeypatch.setattr(provider, "_fetch", Mock(side_effect=RuntimeError("bad")))
    assert provider.constituents("us", date.today()).status == "ok"
    assert provider.constituents("us", date(2015, 1, 1)).status == "stale"
    assert provider.constituents("kr", date.today()).status == "failed"
    with pytest.raises(ValueError):
        provider.constituents("other", date.today())
    assert serialize({"missing": np.nan, "number": np.int64(3), "date": date(2025, 1, 1)}) == {
        "missing": None,
        "number": 3,
        "date": "2025-01-01",
    }
    assert serialize(DataResult([1, 2], "fixture"))["data"] == [1, 2]
