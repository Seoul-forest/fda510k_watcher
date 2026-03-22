#!/usr/bin/env python3
import os, json, time, re, traceback, logging
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
import smtplib
from logging.handlers import RotatingFileHandler
from pathlib import Path
import requests
from dotenv import load_dotenv

# 로깅 설정
LOG_FILE = Path("fda_510k_watcher.log")
logger = logging.getLogger("fda510k")
logger.setLevel(logging.INFO)
_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
_fh = RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=3, encoding="utf-8")
_fh.setFormatter(_fmt)
_sh = logging.StreamHandler()
_sh.setFormatter(_fmt)
logger.addHandler(_fh)
logger.addHandler(_sh)

STATE_FILE = Path("fda_510k_html_state.json")
OPENFDA_BASE = "https://api.fda.gov/device/510k.json"
DETAIL_BASE = "https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/pmn.cfm"
KST = timezone(timedelta(hours=9))

load_dotenv()

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
MAIL_TO = os.getenv("MAIL_TO", "issue777@gmail.com")

WATCH_PRODUCT_CODES = [s.strip() for s in os.getenv("WATCH_PRODUCT_CODES","").split(",") if s.strip()]
WATCH_APPLICANTS    = [s.strip() for s in os.getenv("WATCH_APPLICANTS","").split(",") if s.strip()]

def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("State file corrupted (%s), backing up and resetting", e)
            backup = STATE_FILE.with_suffix(".json.bak")
            STATE_FILE.rename(backup)
    return {"seen_k_numbers": []}

def save_state(state):
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False))
    tmp.rename(STATE_FILE)

def send_email(subject, html):
    if not (SMTP_HOST and SMTP_USER and SMTP_PASS and MAIL_TO):
        logger.warning("SMTP env not set; skip email")
        return

    msg = MIMEText(html, "html", "utf-8")
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = MAIL_TO

    for attempt in range(3):
        try:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
                s.starttls()
                s.login(SMTP_USER, SMTP_PASS)
                s.sendmail(SMTP_USER, [MAIL_TO], msg.as_string())
                logger.info("Email sent successfully")
                return
        except Exception as e:
            logger.error("Error sending email (attempt %d/3): %s", attempt + 1, e)
            if attempt < 2:
                time.sleep(5 * (attempt + 1))

def iso(dstr):
    # FDA API는 YYYY-MM-DD 형태이나, YYYYMMDD 형태도 보정
    if dstr and re.fullmatch(r"\d{8}", dstr):
        return f"{dstr[0:4]}-{dstr[4:6]}-{dstr[6:8]}"
    return dstr or ""

def query_openfda(product_code=None, applicant=None):
    """openFDA API로 510(k) 데이터를 조회한다."""
    params = {
        "sort": "decision_date:desc",
        "limit": 100,
    }
    if product_code:
        params["search"] = f'product_code:"{product_code}"'
    elif applicant:
        params["search"] = f'applicant:"{applicant}"'
    else:
        return []

    for attempt in range(3):
        try:
            resp = requests.get(OPENFDA_BASE, params=params, timeout=30)
            if resp.status_code == 404:
                # 결과 없음
                logger.info("No results from API (404)")
                return []
            if resp.status_code == 429:
                logger.warning("API rate limit hit, waiting 10s (attempt %d/3)", attempt + 1)
                time.sleep(10)
                continue
            resp.raise_for_status()
            break
        except requests.exceptions.RequestException as e:
            logger.error("API request error (attempt %d/3): %s", attempt + 1, e)
            if attempt < 2:
                time.sleep(5 * (attempt + 1))
            else:
                return []

    data = resp.json()
    results = data.get("results", [])

    items = []
    for r in results:
        k_number = r.get("k_number", "")
        if not k_number:
            continue
        items.append({
            "k_number": k_number,
            "device_name": r.get("device_name", ""),
            "applicant": r.get("applicant", ""),
            "product_code": r.get("product_code", ""),
            "decision_date": r.get("decision_date", ""),
            "detail_url": f"{DETAIL_BASE}?ID={k_number}",
        })

    logger.info("API returned %d results", len(items))
    return items

def main():
    state = load_state()
    seen = set(state.get("seen_k_numbers", []))
    all_new = []

    # 1) Product Code 워치
    for pc in WATCH_PRODUCT_CODES:
        logger.info("Searching for Product Code: %s", pc)
        for r in query_openfda(product_code=pc):
            if r["k_number"] not in seen:
                all_new.append(("Product code = " + pc, r))
                seen.add(r["k_number"])
        time.sleep(0.3)  # API rate limit 고려

    # 2) Applicant 워치
    for ap in WATCH_APPLICANTS:
        logger.info("Searching for Applicant: %s", ap)
        for r in query_openfda(applicant=ap):
            if r["k_number"] not in seen:
                all_new.append((f'Applicant contains "{ap}"', r))
                seen.add(r["k_number"])
        time.sleep(0.3)

    # 알림 및 상태 저장
    logger.info("Total results: %d, New: %d", len(seen), len(all_new))

    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M")

    if all_new:
        # 신규 항목이 있을 때: 신규 감지 테이블 포함
        rows = []
        for title, it in all_new:
            rows.append(
                f"<tr>"
                f"<td>{title}</td>"
                f"<td>{it['k_number']}</td>"
                f"<td>{it['device_name']}</td>"
                f"<td>{it['applicant']}</td>"
                f"<td>{it['product_code']}</td>"
                f"<td>{iso(it['decision_date'])}</td>"
                f"<td><a href='{it['detail_url']}' target='_blank'>detail</a></td>"
                f"</tr>"
            )
        html = (
            f"<h2>FDA 510(k) 신규 감지 ({now} KST)</h2>"
            f"<table border='1' cellpadding='6' cellspacing='0'>"
            f"<tr><th>Rule</th><th>510(k)#</th><th>Device</th><th>Applicant</th>"
            f"<th>Prod. Code</th><th>Decision Date</th><th>Link</th></tr>"
            + "".join(rows) + "</table>"
            f"<p style='color:#666'>출처: openFDA API (api.fda.gov). 데이터 월간 갱신.</p>"
        )
        send_email(f"[510(k)] 신규 {len(all_new)}건 감지", html)
    else:
        # 신규 항목이 없을 때: 일일 모니터링 리포트
        html = (
            f"<h2>FDA 510(k) 일일 모니터링 리포트 ({now} KST)</h2>"
            f"<p><strong>신규 510(k) 승인: 없음</strong></p>"
            f"<p>현재 모니터링 중인 K-number: <strong>{len(seen)}개</strong></p>"
            f"<p>검색 조건:</p>"
            f"<ul>"
            f"<li><strong>Product Codes:</strong> {', '.join(WATCH_PRODUCT_CODES)}</li>"
            f"<li><strong>Applicants:</strong> {', '.join(WATCH_APPLICANTS)}</li>"
            f"</ul>"
            f"<p style='color:#666'>출처: openFDA API (api.fda.gov). 데이터 월간 갱신.</p>"
        )
        send_email(f"[510(k)] 일일 모니터링 리포트 - 신규 항목 없음", html)
        logger.info("No new 510(k) approvals found - daily report sent")

    # seen 업데이트 (최대 규모 제한)
    logger.info("Updating state file with %d seen K-numbers", len(seen))
    state["seen_k_numbers"] = list(seen)[-5000:]
    save_state(state)
    logger.info("State file updated successfully")

if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.error(traceback.format_exc())
