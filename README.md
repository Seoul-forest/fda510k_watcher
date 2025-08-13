# FDA 510(k) HTML Watcher

FDA 510(k) 의료기기 승인 데이터베이스를 모니터링하여 새로운 승인 정보를 자동으로 감지하고 이메일로 알림을 보내는 Python 프로그램입니다.

## 🎯 주요 기능

- **자동 모니터링**: FDA 웹사이트에서 새로운 510(k) 승인 정보 자동 감지
- **다중 조건 검색**: Product Code와 Applicant Name 기반 검색
- **이메일 알림**: 새로운 정보 감지 시 HTML 테이블 형태로 이메일 발송
- **중복 방지**: 이미 본 K번호는 저장하여 중복 알림 방지
- **웹 스크래핑**: Playwright를 사용한 안정적인 웹 데이터 수집

## 🚀 설치 및 설정

### 1. 저장소 클론
```bash
git clone <repository-url>
cd fda510k_watcher
```

### 2. Python 환경 설정
```bash
# conda 환경 사용 (권장)
conda create -n py311 python=3.11
conda activate py311

# 또는 venv 사용
python -m venv venv
source venv/bin/activate  # macOS/Linux
```

### 3. 패키지 설치
```bash
pip install -r requirements.txt
playwright install chromium
```

### 4. 환경 변수 설정
`.env` 파일을 생성하고 다음 내용을 입력하세요:

```env
# SMTP 이메일 설정
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASS=your_app_password
MAIL_TO=recipient@example.com

# 모니터링할 제품 코드들 (쉼표로 구분)
WATCH_PRODUCT_CODES=JAK,IZI,LLZ

# 모니터링할 신청자(회사)들 (쉼표로 구분)
WATCH_APPLICANTS=Medtronic,Johnson & Johnson,Stryker
```

**Gmail 사용 시 주의사항:**
- 2단계 인증을 활성화해야 합니다
- 앱 비밀번호를 생성하여 `SMTP_PASS`에 입력해야 합니다

## 📊 사용법

### 기본 실행
```bash
python fda_510k_html_watch.py
```

### 모니터링 조건 설정
- **Product Code**: 특정 의료기기 분류 코드로 검색
- **Applicant**: 특정 회사명으로 검색 (부분 일치)

### 결과 확인
- 새로운 510(k) 승인이 감지되면 이메일로 알림
- `fda_510k_html_state.json` 파일에 처리된 K번호들이 저장됨

## 🔧 주요 구성 요소

- **`fda_510k_html_watch.py`**: 메인 프로그램
- **`.env`**: 환경 변수 설정 (Git에 포함되지 않음)
- **`requirements.txt`**: 필요한 Python 패키지 목록
- **`.gitignore`**: Git에서 제외할 파일들

## 📁 파일 구조
```
fda510k_watcher/
├── fda_510k_html_watch.py    # 메인 프로그램
├── .env                      # 환경 변수 (로컬만)
├── .gitignore               # Git 제외 파일 목록
├── requirements.txt          # Python 패키지 목록
└── README.md                # 프로젝트 설명서
```

## ⚠️ 주의사항

- `.env` 파일은 민감한 정보를 포함하므로 Git에 커밋하지 마세요
- FDA 웹사이트의 구조가 변경될 수 있으므로 정기적으로 확인이 필요합니다
- 웹 스크래핑 시 적절한 간격을 두고 실행하는 것을 권장합니다

## 📝 라이선스

이 프로젝트는 교육 및 연구 목적으로 제작되었습니다.

## 🤝 기여

버그 리포트나 기능 제안은 이슈로 등록해 주세요.
