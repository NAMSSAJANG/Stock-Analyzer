# Windows에서 먼저 사용하기

Render/OpenAI API 없이 PC에서 실행합니다. 시세 조회와 최초 설치에는 인터넷이 필요합니다. 아직 미설정인 OpenDART/SEC 데이터는 결측으로 표시됩니다. 최초 DB는 비어 있으므로 일일 배치 전 순위/시장 화면에 데이터가 없을 수 있습니다. 종목 검색과 개별 분석부터 확인하세요.

## 준비

1. Windows용 Docker Desktop을 설치하고 WSL 2 기반 **Linux containers**로 실행합니다. 설치가 재부팅을 요청하면 재부팅하세요. 개인 사용의 Docker Desktop 라이선스 조건을 확인하세요.
2. [개발 브랜치 ZIP](https://github.com/NAMSSAJANG/Stock-Analyzer/archive/refs/heads/goldnam/v0.0.0-a.1.zip)을 다운로드해 압축을 풉니다. 저장소가 비공개라면 GitHub 로그인이 필요합니다.
3. 압축 안의 `goldnam-sachs` 폴더 내용 전체를 `D:\##Goldnam`에 복사합니다. `D:\##Goldnam\01-Setup.cmd`가 보이면 맞습니다. 업데이트 시 기존 `.env`를 삭제하거나 덮어쓰지 마세요.

## 처음 한 번

`01-Setup.cmd`를 더블클릭합니다. 첫 빌드는 인터넷 속도에 따라 수 분 이상 걸리며 여러 GB의 디스크 공간을 사용합니다. 완료 후 12자 이상 앱 비밀번호를 두 번 입력합니다. 입력 중 문자가 보이지 않는 것이 정상입니다. 비밀번호 원문은 저장하지 않습니다.

이어서 앱과 DB가 시작되고 브라우저가 열립니다. **Chrome 또는 Edge**에서 `http://localhost:10000`을 열고 정한 비밀번호로 로그인하세요. 브라우저가 자동으로 열리지 않으면 주소를 직접 입력합니다. 처음에는 검색에서 AAPL 등 종목을 조회하고, Trade Lab/설정/기록 저장을 확인하세요.

## 다음 실행과 종료

- 실행: Docker Desktop을 켠 뒤 `02-Start.cmd` 더블클릭.
- 종료: `03-Stop.cmd` 더블클릭. DB는 삭제하지 않습니다.
- 앱 주소: `http://localhost:10000` — 이 PC에서만 접속 가능합니다.
- 비밀번호 해시/세션 키: `.env` 파일. 공유·커밋하지 마세요.
- 거래 기록/설정: Docker의 `goldnam-local_pgdata` 볼륨. Docker 초기화, 볼륨 삭제, `docker compose down -v`는 데이터를 지우므로 사용하지 마세요. 앱 설정에서 JSON 백업을 내려받을 수 있습니다.

localhost를 신뢰하는 Chromium 정책으로 Secure 쿠키를 유지합니다. 일반 LAN IP의 HTTP나 다른 브라우저까지 보장하지 않습니다. 현재 단계에서는 폰 접속을 열지 않습니다. 폰 로그인·홈 화면 설치 검증은 이후 HTTPS 구성을 추가해 진행합니다.

## 배치 데이터가 필요한 경우

PowerShell에서 다음을 실행하면 같은 로컬 DB에 미국 일일 배치를 저장합니다. 무료 외부 공급자 상태에 따라 실패할 수 있으며 오래 걸릴 수 있습니다. 날짜는 완료된 미국 거래일로 바꾸세요. 재무 미설정 시 종합 점수는 생기지 않습니다.

```powershell
Set-Location -LiteralPath 'D:\##Goldnam'
docker compose -p goldnam-local exec app goldnam daily --market us --as-of 2026-11-20
```

위 예시 날짜는 실제 사용 시 완료된 미국 거래일로 변경하세요. 옵션 도움말은 `goldnam daily --help`입니다. 자동 스케줄은 로컬 설치에서 등록하지 않습니다.

## 문제가 생기면

실행 창의 오류를 확인하세요. Docker 연결 오류는 Docker Desktop 시작 여부를, 포트 충돌은 다른 앱의 10000번 사용 여부를 확인합니다. 진단 명령:

```powershell
Set-Location -LiteralPath 'D:\##Goldnam'
docker compose -p goldnam-local ps
docker compose -p goldnam-local logs --tail 50 app
```

`.env` 내용을 채팅에 붙여넣지 마세요. PowerShell 실행 정책은 시작 파일의 해당 프로세스에만 적용되며 PC 전체 설정을 바꾸지 않습니다.

## 검증 범위

클라우드 Linux의 실제 앱 Docker 이미지와 Chromium으로 HTTP localhost 로그인·Secure/HttpOnly 쿠키·인증 후 설정 조회가 통과했습니다. 설정 생성/해시 검증/기존 파일 보존/잘못된 입력 거부 자동 테스트를 실행했습니다. Windows 자체의 더블클릭·Docker Desktop 설치는 이 환경에서 실행할 수 없으므로 사용자 PC 첫 실행에서 확인해야 합니다. Render 리소스는 생성하지 않습니다.
