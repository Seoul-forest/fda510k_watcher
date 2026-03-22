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

OPENFDA_API_KEY = os.getenv("OPENFDA_API_KEY")

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
    if OPENFDA_API_KEY:
        params["api_key"] = OPENFDA_API_KEY
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
        rows = []
        for i, (title, it) in enumerate(all_new):
            bg = "#ffffff" if i % 2 == 0 else "#f8f9fa"
            rows.append(
                f"<tr style='background:{bg}'>"
                f"<td style='padding:10px 14px;border-bottom:1px solid #e9ecef;color:#6c757d;font-size:12px'>{title}</td>"
                f"<td style='padding:10px 14px;border-bottom:1px solid #e9ecef;font-weight:600'>"
                f"<a href='{it['detail_url']}' target='_blank' style='color:#0d6efd;text-decoration:none'>{it['k_number']}</a></td>"
                f"<td style='padding:10px 14px;border-bottom:1px solid #e9ecef'>{it['device_name']}</td>"
                f"<td style='padding:10px 14px;border-bottom:1px solid #e9ecef'>{it['applicant']}</td>"
                f"<td style='padding:10px 14px;border-bottom:1px solid #e9ecef;text-align:center'>"
                f"<span style='background:#e7f1ff;color:#0d6efd;padding:2px 8px;border-radius:4px;font-size:12px;font-weight:600'>{it['product_code']}</span></td>"
                f"<td style='padding:10px 14px;border-bottom:1px solid #e9ecef;white-space:nowrap'>{iso(it['decision_date'])}</td>"
                f"</tr>"
            )
        html = f"""
        <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:900px;margin:0 auto;color:#212529">
          <div style="background:linear-gradient(135deg,#0d6efd,#6610f2);padding:28px 32px;border-radius:12px 12px 0 0">
            <h1 style="margin:0;color:#fff;font-size:22px;font-weight:700">FDA 510(k) Alert</h1>
            <p style="margin:6px 0 0;color:rgba(255,255,255,0.85);font-size:14px">{now} KST</p>
          </div>
          <div style="background:#fff;padding:24px 32px;border:1px solid #e9ecef;border-top:none">
            <div style="display:flex;gap:16px;margin-bottom:24px">
              <div style="background:#e7f1ff;border-radius:10px;padding:16px 24px;flex:1;text-align:center">
                <div style="font-size:28px;font-weight:700;color:#0d6efd">{len(all_new)}</div>
                <div style="font-size:12px;color:#6c757d;margin-top:2px">New Clearances</div>
              </div>
              <div style="background:#f0fdf4;border-radius:10px;padding:16px 24px;flex:1;text-align:center">
                <div style="font-size:28px;font-weight:700;color:#198754">{len(seen)}</div>
                <div style="font-size:12px;color:#6c757d;margin-top:2px">Total Tracked</div>
              </div>
            </div>
            <table style="width:100%;border-collapse:collapse;font-size:13px">
              <thead>
                <tr style="background:#f8f9fa">
                  <th style="padding:10px 14px;text-align:left;font-weight:600;color:#6c757d;font-size:11px;text-transform:uppercase;letter-spacing:0.5px;border-bottom:2px solid #dee2e6">Rule</th>
                  <th style="padding:10px 14px;text-align:left;font-weight:600;color:#6c757d;font-size:11px;text-transform:uppercase;letter-spacing:0.5px;border-bottom:2px solid #dee2e6">510(k)#</th>
                  <th style="padding:10px 14px;text-align:left;font-weight:600;color:#6c757d;font-size:11px;text-transform:uppercase;letter-spacing:0.5px;border-bottom:2px solid #dee2e6">Device</th>
                  <th style="padding:10px 14px;text-align:left;font-weight:600;color:#6c757d;font-size:11px;text-transform:uppercase;letter-spacing:0.5px;border-bottom:2px solid #dee2e6">Applicant</th>
                  <th style="padding:10px 14px;text-align:center;font-weight:600;color:#6c757d;font-size:11px;text-transform:uppercase;letter-spacing:0.5px;border-bottom:2px solid #dee2e6">Code</th>
                  <th style="padding:10px 14px;text-align:left;font-weight:600;color:#6c757d;font-size:11px;text-transform:uppercase;letter-spacing:0.5px;border-bottom:2px solid #dee2e6">Decision Date</th>
                </tr>
              </thead>
              <tbody>{"".join(rows)}</tbody>
            </table>
          </div>
          <div style="background:#f8f9fa;padding:16px 32px;border-radius:0 0 12px 12px;border:1px solid #e9ecef;border-top:none">
            <p style="margin:0;font-size:11px;color:#adb5bd">Source: openFDA API (api.fda.gov) | Updated monthly</p>
          </div>
        </div>"""
        send_email(f"[510(k)] {len(all_new)}건 신규 감지", html)
    else:
        pc_tags = " ".join(
            f"<span style='background:#e7f1ff;color:#0d6efd;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600;display:inline-block;margin:2px'>{pc}</span>"
            for pc in WATCH_PRODUCT_CODES
        )
        ap_tags = " ".join(
            f"<span style='background:#fff3cd;color:#997404;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600;display:inline-block;margin:2px'>{ap}</span>"
            for ap in WATCH_APPLICANTS
        )
        html = f"""
        <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:600px;margin:0 auto;color:#212529">
          <div style="background:linear-gradient(135deg,#6c757d,#495057);padding:28px 32px;border-radius:12px 12px 0 0">
            <h1 style="margin:0;color:#fff;font-size:22px;font-weight:700">FDA 510(k) Daily Report</h1>
            <p style="margin:6px 0 0;color:rgba(255,255,255,0.85);font-size:14px">{now} KST</p>
          </div>
          <div style="background:#fff;padding:28px 32px;border:1px solid #e9ecef;border-top:none">
            <div style="background:#f8f9fa;border-radius:10px;padding:20px;text-align:center;margin-bottom:24px">
              <p style="margin:0;font-size:15px;color:#6c757d">No new 510(k) clearances detected</p>
              <p style="margin:8px 0 0;font-size:13px;color:#adb5bd">Tracking <strong style="color:#212529">{len(seen)}</strong> K-numbers</p>
            </div>
            <div style="margin-bottom:16px">
              <p style="font-size:12px;font-weight:600;color:#6c757d;margin:0 0 8px;text-transform:uppercase;letter-spacing:0.5px">Product Codes</p>
              <div>{pc_tags}</div>
            </div>
            <div>
              <p style="font-size:12px;font-weight:600;color:#6c757d;margin:0 0 8px;text-transform:uppercase;letter-spacing:0.5px">Applicants</p>
              <div>{ap_tags}</div>
            </div>
          </div>
          <div style="background:#f8f9fa;padding:16px 32px;border-radius:0 0 12px 12px;border:1px solid #e9ecef;border-top:none">
            <p style="margin:0;font-size:11px;color:#adb5bd">Source: openFDA API (api.fda.gov) | Updated monthly</p>
          </div>
        </div>"""
        send_email(f"[510(k)] Daily Report - No New Items", html)
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
