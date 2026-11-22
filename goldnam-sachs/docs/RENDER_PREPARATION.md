# Render 준비 검증 · 2026-11-23

실제 유료 리소스/Blueprint 생성·sync·배포는 수행하지 않았다. 연결된 Hobby workspace와 기존 서비스는 변경하지 않았다.

공식 Markdown 문서를 직접 내려받아 관련 필드를 확인:

- https://render.com/docs/blueprint-spec.md — docker/rootDir/region/plan/fromDatabase/generateValue/sync:false/IP/DB 저장 용량
- https://render.com/docs/compute-plans.md — Starter→0.5c-512mb, Basic-256mb→0.1c-256mb
- https://render.com/pricing.md — Hobby $0, 앱 $7, DB $6, 저장 $0.30/GB
- https://render.com/docs/postgresql-creating-connecting.md — 1GB 또는 5GB 배수, 내부/외부 URL 및 TLS
- https://render.com/docs/configure-environment-variables.md — 생성/사용자 시크릿
- https://render.com/docs/environment-variables.md — PORT, RENDER_EXTERNAL_URL
- https://render.com/docs/private-network.md — 같은 지역/워크스페이스 내부 연결
- https://render.com/docs/web-services.md — 0.0.0.0/PORT, 플랫폼 TLS 종료

현재 공식 JSON Schema를 `docs/render-schema.json`에 보관하고 `scripts/validate_blueprint.py`로 통과했다. 플랫폼 계정별 리소스 생성 검증이나 실제 Render CLI/API validate는 수행하지 않았으므로 로컬 schema 검증과 혼동하지 않는다. Blueprint 제출 미리보기는 사용자가 최종 확인한다.

앱의 실행 계정 UID 10001, 한 worker, 실제 PORT 바인딩. 운영 Docker에서 API/정적 화면/Argon2/PostgreSQL 쓰기와 재시작 유지 확인: [원문](test-results/phase8-container.txt). Docker 빌드 중 발견한 읽기 권한 문제는 COPY mode 지정으로 수정했다. 임시 빌드 캐시 부족은 사용하지 않는 빌드 캐시 정리 후 해결했다.

로컬 HTTPS 배포 점검 스크립트 결과: [원문](test-results/post-deploy-local.txt). 이는 모킹 시세를 가진 로컬 서버이며 실제 Render URL 점검이 아니다.

DB 외부 접근은 GitHub 러너의 동적 IP 때문에 TLS·인증을 요구하는 전체 CIDR 허용으로 작성했다. 고정 러너 사용 시 범위를 줄이거나 `[]`로 외부 접속을 끄는 절차를 README에 명시했다. 저장 자동 확장은 꺼져 있다.
