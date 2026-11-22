# Phase 1 · 데이터 계층

2026-11-23. **구현/오프라인 검증 완료, 라이브 PIT·한국 구성 확인 대기**. ADDENDUM A3 및 사용자의 '나중에 설정할게'에 따라 미설정 소스를 건너뛰고 후속 Phase를 진행한다.

| 완료 기준 | 결과 |
|---|---|
| 5개 공급자 계약과 출처·시각·상태 | 통과 |
| 실패 성공 캐시 금지·폴백·모두 실패·재시도·차단 | 모킹 통과 |
| 수정 OHLCV 검사, 거래소 달력, stale | 통과 |
| Parquet 캐시와 구성 스냅샷 | 통과: 원본 시각 보존, 실패 미저장 |
| SEC·OpenDART 공시일 기준 PIT | 모킹 통과; 인증 호출 대기 |
| 미국 3개·한국 3개 시세 | live **6 passed** |
| 미국 3개·한국 3개 PIT | **6 skipped**, 키 미설정 |
| 미국 유니버스 | 실제 518종목 수집 |
| 한국 유니버스 | 미통과: KRX 빈 응답(KeyError). 임의 구성으로 대체하지 않음 |
| 기존 테스트 보존·전체 로컬 | **85 passed**, live 12 deselected, 12 subtests passed, 커버리지 **90.34%** |
| ruff·format·strict mypy | 통과 (44 source files) |

## 변경 파일

`engine/goldnam_engine/data/`에 contracts, resilience, quality, market_data, fundamentals, dart, parquet_cache, universe 추가. `engine/tests/test_data_v1.py`, `test_data_live.py` 추가. pyproject/uv.lock 고정. 공식 근거는 DATA_SOURCES.md. 원래 v6 로직/테스트는 변경하지 않았다.

## 테스트 원문

- [전체 로컬](test-results/phase1-local.txt)
- [최종 데이터 회귀](test-results/phase1-data-final.txt)
- [실제 시세/PIT](test-results/phase1-live.txt)
- [실제 구성](test-results/phase1-universe-live.txt)

## 남은 문제·결정

키 2개는 나중에 제공한다. 현재 Yahoo 재무는 current-only로 과거 검증에서 제외. 한국 실적일은 미확인. XBRL 연결/별도 범위 모호·확장 태그·비12월 결산사 분기는 보수적으로 제외한다. 실제 원본 확인 후 확장한다.

pykrx가 pkg_resources를 요구하여 setuptools 80.10.2(81 미만 최신 호환판)를 고정했다. upstream 경고를 숨기지 않았다. Nasdaq 구성표가 List_of_NASDAQ-100_companies로 이동한 것을 원문 링크에서 확인해 수정했다.

오래된 공급자 응답을 장애로 차단하던 새 캐시 버그는 실패 테스트를 유지하며 수정했다. 최신 폴백 우선, 모두 오래되면 stale 반환. Phase 1 원격 CI는 아직 미확인이며 Phase 0 원격 성공과 구분한다.
