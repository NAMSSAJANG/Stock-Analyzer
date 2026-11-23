# Phase 7 · Trade Lab과 기록

2026-11-23. 기존 Decimal 엔진을 보존하면서 사용자 비용·보유 한도·기록을 연결했다.

| 기준 | 결과 |
|---|---|
| 기존 Trade Lab·체결·분석 회귀 | 4종 모두 통과, 원문 링크 아래 |
| 동일 시드 100회×10,000 재현 | 단위 테스트 통과, 전승/전패 경계 포함 |
| 기대값·손익분기·연속 손실·낙폭 | 구현, 검증 결과가 있으면 선택한 Setup/청산의 측정치를 기본 입력으로 사용 |
| 측정값 없는 경우 | 50%/2R은 예시 가정이라고 명시, 성과로 표시하지 않음 |
| 청산 A/B/C·무작위 진입 비교 | API/화면, 기대값·손익비 먼저 표시 |
| 비용 설정 | plan/simulate/execution 모두 저장한 비용 사용, 명시 입력은 우선 |
| 포트폴리오·갭 | 보유 입력·히트·업종·종목 한도, 제한 수량에 따른 모든 현금/손실 수치 재계산 회귀 통과 |
| 거래 일지 | CRUD, 날짜만 있으므로 엄격히 이전 거래일의 계획만 저장해 당일 종가 lookahead 방지 |
| 분석 이력·관심종목 변화 | 조회 스냅샷 저장, 배치 순위/상태 표시 |
| v6 SQLite/JSON | 원본 읽기 전용, 검증 후 별도 kind/v6 버전, 중복 가져오기·원본 해시 불변 테스트 통과 |
| 백업/CSV | 개인 JSON 병합 백업(v6 포함), 계산 결과 CSV 다운로드 |

## 실제 테스트

- [전체 Python 원문](test-results/phase7-python.txt): **133 passed, 13 deselected**, 통합 engine/api/jobs 커버리지 **86.14%**. 후속 배포 문서/CLI 보호 추가 후 [최종 검사](test-results/final-python.txt)는 별도 기록한다.
- [기존 회귀 원문](test-results/phase7-legacy.txt): V6 offline smoke, Trade Lab UI, Execution UI, Analysis sizing/calibration 모두 passed.
- [브라우저 최종 원문](test-results/phase7-browser-final.txt): 모바일 비용 적용·고정 시드·거래 일지·v6 가져오기와 3종 화면 흐름. **4 passed, 2 skipped (28.2s)**. 중복 데이터 흐름 2개만 다른 브라우저에서 생략했고 주요 탐색 흐름은 세 브라우저 모두 실행했다. 중간 실패 원문도 보존했다.

버그 수정: API 브라우저 fixture가 단일 메모리 SQLite 연결을 여러 스레드에서 공유해 간헐적으로 SQLite InterfaceError가 났다. 테스트도 별도 연결을 사용하는 임시 파일 DB로 바꿨다. 운영은 PostgreSQL이다. 포트폴리오 한도가 기본 수량을 낮출 때 현금/손실이 옛 수량을 쓰던 래퍼 문제는 원본 엔진을 건드리지 않고 수정했다.

변경: web/components/{trade-lab,history,result-view,pages}, api 계약·기록·비용, jobs/import_v6_history.py, risk/portfolio.py, 회귀/브라우저 테스트. 가격·재무 키가 없는 경우의 실제 체결 검증과 한국 전체 검증의 한계는 Phase 4와 동일하다.
