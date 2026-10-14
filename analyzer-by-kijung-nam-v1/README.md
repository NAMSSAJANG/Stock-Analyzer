# 분석기 by Kijung Nam V1

iPhone Safari와 데스크톱에서 사용할 수 있는 반응형 주식 분석 웹앱입니다. 원/달러 환율, 금, 비트코인, 이더리움과 미국·한국 주식 분석을 한 화면에 표시합니다.

## 로컬 실행

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

같은 Wi-Fi의 iPhone에서 열려면 다음처럼 실행하고, PC 방화벽이 허용하는 경우 `http://PC의-내부-IP:8501`로 접속합니다.

```powershell
streamlit run app.py --server.address 0.0.0.0
```

## Streamlit Community Cloud 배포

1. 이 폴더를 GitHub 저장소에 올립니다.
2. https://share.streamlit.io 에 GitHub 계정으로 로그인합니다.
3. **Create app**에서 저장소, 브랜치 `main`, 파일 `app.py`를 선택합니다.
4. **Deploy**를 누르면 공개 HTTPS 주소가 생성됩니다.

별도 API 키는 필요하지 않습니다. 데이터는 Yahoo Finance를 통해 가져오므로 지연, 누락 또는 호출 제한이 있을 수 있습니다.
