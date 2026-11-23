"""Opt in: pytest -m live --force-enable-socket engine/tests/test_data_live.py."""

import os
from datetime import date, timedelta

import pytest
from goldnam_engine.data.fundamentals import DartFundamentals, SecFundamentals
from goldnam_engine.data.market_data import Prices


@pytest.mark.live
@pytest.mark.parametrize("symbol", ["AAPL", "MSFT", "NVDA", "005930.KS", "000660.KS", "035420.KS"])
def test_live_prices(symbol, tmp_path):
    result = Prices(tmp_path).prices(symbol, date.today() - timedelta(days=400), date.today())
    assert result.usable, result.message
    assert len(result.data) >= 200


@pytest.mark.live
@pytest.mark.parametrize("symbol", ["AAPL", "MSFT", "NVDA", "005930.KS", "000660.KS", "035420.KS"])
def test_live_pit(symbol):
    kr = symbol.endswith(".KS")
    key = "OPENDART_API_KEY" if kr else "SEC_USER_AGENT"
    if not os.getenv(key):
        pytest.skip(f"{key} 미설정 · 사용자 나중에 설정 예정")
    provider = DartFundamentals() if kr else SecFundamentals()
    result = provider.fundamentals(symbol, date.today() - timedelta(days=365))
    assert result.usable, result.message
    assert result.data["pit"] is True
    assert result.data["provenance"]
