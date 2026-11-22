# Phase 2 · 팩터와 점수

2026-11-23. **로컬 완료**. 실제 재무 수집은 Phase 1과 동일하게 키 설정 대기다.

| 완료 기준 | 결과 |
|---|---|
| 12-1/6-1 모멘텀과 추세 벡터 계산 | 통과: 최근 1개월 제외, 미래봉 추가 불변, 252일 미달 결측 |
| 품질·가치·성장, 음수 분모/적자 가드 | 통과 |
| winsor 1/99, 업종→상위 업종→시장, 시장 분리 | 통과 |
| 절반 지표·최소 3팩터 조건·동일 가중 | 통과; 2팩터면 종합 null |
| 정수 표시와 메타데이터·유니버스 밖 | 통과; 내부 raw_value만 소수 |
| 일일 배치와 SQL 저장 | 구현, SQLite 경계/업서트 테스트 통과. 배포는 Postgres만 허용 |
| 실제 미국 하루 계산 시간 | **518/518 시세**, 49.935초(수집 포함), 순위 계산 10.684초 |
| 실제 종합 점수 | **0/518 산출**: SEC 키 미설정으로 2개 가격 팩터만 있음. 결측을 가짜 점수로 채우지 않음 |
| 전체 로컬 테스트 | **90 passed**, 12 live deselected, 12 subtests passed; **90.88%** |
| ruff/format/mypy | 통과 (47 source files) |

변경: factors/cross_section.py, scoring/cross_section.py, data/store.py, jobs/daily_scores.py, engine/tests/test_scores_v1.py. 기존 엔진은 그대로 보존했다.

원문: [전체 테스트](test-results/phase2-local.txt), [실제 배치](test-results/phase2-us-batch.txt).

실측 명령: `python -m jobs.daily_scores --market us --as-of 2026-11-20 --no-db --output .data/us-daily.json`. 구성은 2026-11-23에 관측한 518종목이며 과거 구성으로 주장하지 않는다. 원시 Parquet/전체 점수는 .data의 삭제 가능한 로컬 산출물. 순위 일괄 계산은 가격만으로 종합 점수를 생성하지 않는다.

실제 Postgres 통합·API 저장소 검증은 Phase 5에서 수행한다. 한국 유니버스 응답과 PIT 키 대기 사항은 남아 있다. 원격 CI는 후속 커밋 push 때 별도 확인한다.
