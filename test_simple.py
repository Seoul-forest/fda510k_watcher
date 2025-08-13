#!/usr/bin/env python3
import os, json, asyncio, re
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
import smtplib
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from pathlib import Path
from playwright.async_api import async_playwright

STATE_FILE = Path("fda_510k_html_state.json")
BASE = "https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/pmn.cfm"
KST = timezone(timedelta(hours=9))

load_dotenv()

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
MAIL_TO = os.getenv("MAIL_TO", "issue777@gmail.com")

# 테스트용으로 하나만 설정
WATCH_PRODUCT_CODES = ["QDA"]  # 하나만 테스트
WATCH_APPLICANTS = ["alivecor"]  # 하나만 테스트

def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"seen_k_numbers": []}

def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False))
    print(f"State saved to {STATE_FILE}")

def send_email(subject, html):
    if not (SMTP_HOST and SMTP_USER and SMTP_PASS and MAIL_TO):
        print("WARN: SMTP env not set; skip email")
        return
    
    try:
        msg = MIMEText(html, "html", "utf-8")
        msg["Subject"] = subject
        msg["From"] = SMTP_USER
        msg["To"] = MAIL_TO
        
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.starttls()
            s.login(SMTP_USER, SMTP_PASS)
            s.sendmail(SMTP_USER, [MAIL_TO], msg.as_string())
            print("Email sent successfully via Gmail!")
    except Exception as e:
        print(f"Error sending email: {e}")

def parse_results(html):
    """결과 표에서 레코드를 추출. (K번호, Device Name, Applicant, Product Code, Decision Date, 상세URL)"""
    soup = BeautifulSoup(html, "lxml")

    # 결과 표는 보통 <table>로 구성되며 헤더에 '510(k) Number', 'Device Name' 등이 있다.
    table = None
    for t in soup.find_all("table"):
        head = t.find("tr")
        if not head: 
            continue
        headers = " ".join(th.get_text(strip=True) for th in head.find_all(["th","td"]))
        if re.search(r"510\(k\)\s*Number", headers, re.I) and re.search(r"Device\s*Name", headers, re.I):
            table = t; break
    if table is None:
        print("No results table found")
        return []

    rows = []
    for tr in table.find_all("tr")[1:]:
        tds = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
        links = tr.find_all("a")
        detail_url = ""
        for a in links:
            href = a.get("href","")
            if "cfpmn/pmn.cfm?ID=" in href:
                detail_url = href if href.startswith("http") else "https://www.accessdata.fda.gov" + href
                break

        # 컬럼 수는 페이지마다 조금 다를 수 있음 → 가장 중요한 값들만 정규 추출
        knum = next((s for s in tds if re.fullmatch(r"K\d{6}", s, re.I)), "")
        # 흔한 컬럼 배치: [K#, Device Name, Applicant, Product Code, Date Received, Decision Date, Decision, ...]
        dev_name = tds[1] if len(tds) > 1 else ""
        applicant = tds[2] if len(tds) > 2 else ""
        product_code = tds[3] if len(tds) > 3 else ""
        decision_date = ""
        # 뒤쪽 2칸 중 하나가 결정일인 경우가 많음 → YYYYMMDD 형태 pick
        for cell in tds:
            if re.fullmatch(r"\d{8}", cell):
                decision_date = cell

        if knum:  # K번호가 있는 경우만 추가
            rows.append({
                "k_number": knum,
                "device_name": dev_name,
                "applicant": applicant,
                "product_code": product_code,
                "decision_date": decision_date,
                "detail_url": detail_url
            })
            print(f"Found K-number: {knum} - {dev_name}")
    
    print(f"Total rows parsed: {len(rows)}")
    return rows

def parse_results_new(html):
    """새로운 HTML 파싱 로직 - FDA 실제 구조에 맞춤"""
    soup = BeautifulSoup(html, "lxml")
    
    # K번호들을 직접 찾기
    k_numbers = []
    k_links = soup.find_all("a", href=re.compile(r"cfpmn/pmn.cfm\?ID=K\d{6}"))
    
    print(f"Found {len(k_links)} K-number links")
    
    for link in k_links:
        href = link.get("href", "")
        k_match = re.search(r"ID=(K\d{6})", href)
        if k_match:
            k_number = k_match.group(1)
            
            # 해당 K번호의 상세 정보 찾기
            # 부모 테이블에서 정보 추출
            parent_td = link.find_parent("td")
            if parent_td:
                # Device Name 찾기
                device_name = ""
                device_link = parent_td.find("a", title=re.compile(r"Details about"))
                if device_link:
                    device_name = device_link.get_text(strip=True)
                
                # Applicant 찾기 (다음 td에서)
                applicant = ""
                applicant_td = parent_td.find_next_sibling("td")
                if applicant_td:
                    applicant = applicant_td.get_text(strip=True)
                
                # Product Code 찾기 (다음 td에서)
                product_code = ""
                product_td = applicant_td.find_next_sibling("td") if applicant_td else None
                if product_td:
                    product_code = product_td.get_text(strip=True)
                
                # Decision Date 찾기 (다음 td에서)
                decision_date = ""
                date_td = product_td.find_next_sibling("td") if product_td else None
                if date_td:
                    decision_date = date_td.get_text(strip=True)
                
                # 중복 제거
                if k_number not in [k["k_number"] for k in k_numbers]:
                    k_numbers.append({
                        "k_number": k_number,
                        "device_name": device_name,
                        "applicant": applicant,
                        "product_code": product_code,
                        "decision_date": decision_date,
                        "detail_url": f"https://www.accessdata.fda.gov{href}"
                    })
                    print(f"Parsed: {k_number} - {device_name} - {applicant}")
    
    print(f"Total unique K-numbers parsed: {len(k_numbers)}")
    return k_numbers

async def run_query(page, product_code=None, applicant=None):
    """간단한 검색 실행"""
    print(f"Running query - Product Code: {product_code}, Applicant: {applicant}")
    
    try:
        await page.goto(BASE, wait_until="domcontentloaded", timeout=60000)
        print(f"Successfully loaded FDA page")
        
        # Product Code 입력
        if product_code:
            try:
                await page.fill('input[name*="product" i]', product_code)
                print(f"Product Code filled: {product_code}")
            except Exception as e:
                print(f"Error filling Product Code: {e}")

        # Applicant 입력
        if applicant:
            try:
                await page.get_by_label(re.compile(r"Applicant Name", re.I)).fill(applicant)
                print(f"Applicant filled: {applicant}")
            except Exception as e:
                print(f"Error filling Applicant: {e}")

        # 검색 실행
        try:
            await page.click('input[type="submit"]')
            print("Search button clicked")
            await asyncio.sleep(3)  # 결과 로딩 대기
        except Exception as e:
            print(f"Error clicking search: {e}")
            return []

        # 결과 페이지 HTML 가져오기
        html = await page.content()
        
        # 디버깅용 HTML 저장
        with open("debug_page.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("HTML saved to debug_page.html")
        
        return [html]  # 한 페이지만 반환
        
    except Exception as e:
        print(f"Error in run_query: {e}")
        return []

async def main():
    print("=== SIMPLE TEST VERSION ===")
    
    # 현재 상태 로드
    state = load_state()
    seen = set(state.get("seen_k_numbers", []))
    all_new = []
    
    print(f"Current seen K-numbers: {len(seen)}")
    print(f"Current seen list: {list(seen)[:5]}...")  # 처음 5개만 표시
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        # Product Code 하나만 테스트
        for pc in WATCH_PRODUCT_CODES:
            print(f"\n--- Testing Product Code: {pc} ---")
            html_pages = await run_query(page, product_code=pc)
            
            for html in html_pages:
                results = parse_results_new(html)
                print(f"Parsed {len(results)} results from HTML")
                
                for r in results:
                    print(f"Checking K-number: {r['k_number']}")
                    if r["k_number"] not in seen:
                        print(f"NEW! Adding to all_new: {r['k_number']}")
                        all_new.append((f"Product code = {pc}", r))
                        seen.add(r["k_number"])
                    else:
                        print(f"Already seen: {r['k_number']}")

        await browser.close()

    # 결과 출력
    print(f"\n=== FINAL RESULTS ===")
    print(f"Total seen K-numbers: {len(seen)}")
    print(f"New K-numbers found: {len(all_new)}")
    print(f"All new items: {all_new}")
    
    # 상태 저장
    print(f"\nSaving state...")
    state["seen_k_numbers"] = list(seen)
    save_state(state)
    
    # 상태 파일 확인
    print(f"\nVerifying saved state...")
    if STATE_FILE.exists():
        saved_state = json.loads(STATE_FILE.read_text())
        print(f"Saved state has {len(saved_state.get('seen_k_numbers', []))} K-numbers")
        print(f"First few saved K-numbers: {saved_state.get('seen_k_numbers', [])[:5]}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
