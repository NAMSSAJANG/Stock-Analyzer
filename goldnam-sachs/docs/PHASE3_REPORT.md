# Phase 3 · 타이밍·리스크·청산

2026-11-23. **로컬 구현/회귀 검증 완료**. 기본 청산 방식 선택은 Phase 4 근거를 기다린다.

| 완료 기준 | 결과 |
|---|---|
| 버그 3~6 수정 전 실패 재현 | 4 FAIL 확인. 원본/실행 로그 보관 |
| 실적일 미확인 | 중간 리스크 50·배지; 임박 이벤트 배율 제한 |
| 과열(EXTENDED) 제외 | 우선 방식·가격 합의에서 제외 테스트 통과 |
| 명시적 직전 60일 종가 고점 | 통과. 20일 고점은 초기 돌파만 |
| 실시간 환율/최근값 | 공급자 결과 사용; 없으면 유동성·전체 위험·수량 산출 불가 |
| EMA20 단독 지지 제외·목표 출처 | 통과 |
| 6개 보존 규칙 | 기존 깊이/RSI/거래량 식 비교, 추세 무효화, 지지-0.55ATR, 이벤트 리스크 회귀 통과 |
| A/B/C, 다음 시가, 갭, 동일 봉 손절 우선 | 통과. A 비용 포함 수익률 기존 엔진과 일치 |
| 전체 관측 기간·중복 진입 제외 | 통과. A 20일/B·C 120일 |
| 최대 8종목·업종 2개/30%·히트 6% | 구현, 업종 수와 히트 제한 테스트 통과 |
| 임계값 설정·3단계 실제 국면·독립 4렌즈 | 구현. 새 상태 임계값 strategy.py; 보존 점수식 유지 |
| 전체 로컬 | **107 passed**, live 12 deselected, 12 subtests passed; **91.44%** |
| ruff/format/strict mypy | 통과 (54 source files) |

변경: strategy.py, timing/current.py, risk/current.py, risk/portfolio.py, regime/current.py, scoring/lenses.py, trade/exits.py, test_strategy_v1.py. 원래 모듈은 보존되어 기존 49개 테스트와 AST 보존 테스트도 계속 통과한다.

원문: [수정 전 실패](test-results/phase3-before.txt), [재현 스크립트](regressions/phase3_before.py.txt), [새 전략 테스트](test-results/phase3-strategy.txt), [전체 테스트](test-results/phase3-local.txt).

B는 1차 목표에 절반을 청산하고 본절·추적 손절을 다음 봉부터 적용한다. 당일 고가로 당일 저가의 손절을 소급하지 않는다. 종가의 20일선 이탈은 다음 시가에 청산한다. C도 동일한 추적 원칙이다. 이벤트 스터디의 절반은 1주 기준 가상 수량이며 실제 계좌 정수 수량과 구분한다.

기대값이 없으면 우선 방식은 '비교 근거 없음'. A/B/C 기본값을 좋은 결과가 나오도록 사후 변경하지 않는다. 한국 환율은 결측 시 임의 고정값을 쓰지 않는다. 포트폴리오 입력은 동일 계좌 통화 기준이다.

추가 확인: Phase 2 커밋 7333252의 원격 CI [45054693694](https://github.com/NAMSSAJANG/Stock-Analyzer/actions/runs/45054693694) 성공(웹·Python). Phase 3 원격 결과와 구분한다.
