#!/usr/bin/env python3
import os, json, time, asyncio, re, traceback, random
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

WATCH_PRODUCT_CODES = [s.strip() for s in os.getenv("WATCH_PRODUCT_CODES","").split(",") if s.strip()]
WATCH_APPLICANTS    = [s.strip() for s in os.getenv("WATCH_APPLICANTS","").split(",") if s.strip()]

def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"seen_k_numbers": []}

def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False))

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

def iso(dstr):
    # FDA 상세 페이지에는 YYYYMMDD 형태가 많음 → YYYY-MM-DD 보정
    if dstr and re.fullmatch(r"\d{8}", dstr):
        return f"{dstr[0:4]}-{dstr[4:6]}-{dstr[6:8]}"
    return dstr or ""

async def run_query(page, product_code=None, applicant=None, decision_from=None, decision_to=None, sort="Decision Date (descending)"):
    """고급검색 폼에 값을 채우고 결과표 HTML을 돌려준다(첫 페이지부터 모든 페이지 순회)."""
    
    # 랜덤 지연 추가
    await asyncio.sleep(random.uniform(2, 5))
    
    # 더 자연스러운 User-Agent 사용
    await page.set_extra_http_headers({
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Cache-Control': 'max-age=0'
    })
    
    try:
        await page.goto(BASE, wait_until="domcontentloaded", timeout=120000)
        print(f"Successfully loaded FDA page: {BASE}")
    except Exception as e:
        print(f"Error loading FDA page: {e}")
        # 대체 URL 시도
        try:
            alt_url = "https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/pmn.cfm"
            await page.goto(alt_url, wait_until="domcontentloaded", timeout=120000)
            print(f"Successfully loaded alternative URL: {alt_url}")
        except Exception as e2:
            print(f"Failed to load alternative URL: {e2}")
            return []

    # 페이지 로딩 후 추가 지연
    await asyncio.sleep(random.uniform(1, 3))
    
    # JavaScript 실행 대기
    try:
        await page.wait_for_function("document.readyState === 'complete'", timeout=30000)
    except:
        pass  # 타임아웃 무시하고 계속 진행

    # 페이지 내용 확인을 위한 스크린샷 저장 (디버깅용)
    try:
        await page.screenshot(path="fda_page_debug.png")
        print("Screenshot saved as fda_page_debug.png")
    except:
        pass

    # Product Code 입력
    if product_code:
        try:
            # 다양한 방법으로 Product Code 입력 필드 찾기
            product_code_found = False
            
            # 방법 1: 라벨로 찾기
            try:
                await page.get_by_label(re.compile(r"Product Code", re.I)).fill(product_code)
                product_code_found = True
                print(f"Product Code filled via label: {product_code}")
            except:
                pass
            
            # 방법 2: name 속성으로 찾기
            if not product_code_found:
                try:
                    await page.fill('input[name*="product" i]', product_code)
                    product_code_found = True
                    print(f"Product Code filled via name: {product_code}")
                except:
                    pass
            
            # 방법 3: placeholder로 찾기
            if not product_code_found:
                try:
                    await page.fill('input[placeholder*="product" i]', product_code)
                    product_code_found = True
                    print(f"Product Code filled via placeholder: {product_code}")
                except:
                    pass
            
            if not product_code_found:
                print(f"Could not find Product Code input field for: {product_code}")
            
            await asyncio.sleep(random.uniform(0.5, 1.5))
        except Exception as e:
            print(f"Error filling Product Code: {e}")

    # Applicant 입력
    if applicant:
        try:
            applicant_found = False
            
            # 방법 1: 라벨로 찾기
            try:
                await page.get_by_label(re.compile(r"Applicant Name", re.I)).fill(applicant)
                applicant_found = True
                print(f"Applicant filled via label: {applicant}")
            except:
                pass
            
            # 방법 2: name 속성으로 찾기
            if not applicant_found:
                try:
                    await page.fill('input[name*="applicant" i]', applicant)
                    applicant_found = True
                    print(f"Applicant filled via name: {applicant}")
                except:
                    pass
            
            # 방법 3: placeholder로 찾기
            if not applicant_found:
                try:
                    await page.fill('input[placeholder*="applicant" i]', applicant)
                    applicant_found = True
                    print(f"Applicant filled via placeholder: {applicant}")
                except:
                    pass
            
            if not applicant_found:
                print(f"Could not find Applicant input field for: {applicant}")
            
            await asyncio.sleep(random.uniform(0.5, 1.5))
        except Exception as e:
            print(f"Error filling Applicant: {e}")

    # 정렬(기본값이 Decision Date desc)
    try:
        await page.get_by_label(re.compile(r"Sort by", re.I)).select_option(label=sort)
        await asyncio.sleep(random.uniform(0.5, 1.5))
    except Exception:
        pass  # 셀렉터가 바뀐 경우에도 기본 정렬이면 무시

    # 검색 실행 버튼 (보통 'Search Database' 또는 이미지 버튼)
    # 버튼 텍스트/alt를 포괄적으로 시도
    try:
        search_button_found = False
        
        # 방법 1: get_by_role 사용 (Playwright 최신 버전)
        try:
            if hasattr(page, 'get_by_role'):
                if await page.get_by_role("button", name=re.compile(r"Search", re.I)).count():
                    await page.get_by_role("button", name=re.compile(r"Search", re.I)).click()
                    search_button_found = True
                    print("Search button clicked via get_by_role")
        except:
            pass
        
        # 방법 2: 일반적인 CSS 선택자
        if not search_button_found:
            try:
                await page.click('input[type="submit"]')
                search_button_found = True
                print("Search button clicked via CSS selector")
            except:
                pass
        
        # 방법 3: 텍스트로 찾기
        if not search_button_found:
            try:
                await page.click('button:has-text("Search")')
                search_button_found = True
                print("Search button clicked via text")
            except:
                pass
        
        # 방법 4: 이미지 버튼
        if not search_button_found:
            try:
                await page.click('input[type="image"]')
                search_button_found = True
                print("Search button clicked via image input")
            except:
                pass
        
        if not search_button_found:
            print("Could not find search button")
            return []
        
        print("Search button clicked successfully")
        await asyncio.sleep(random.uniform(2, 4))
    except Exception as e:
        print(f"Error clicking search button: {e}")
        return []

    await page.wait_for_load_state("domcontentloaded", timeout=60000)

    html_pages = []
    while True:
        html = await page.content()
        html_pages.append(html)

        # 다음 페이지가 있으면 클릭 (FDA 페이징은 'Next' 링크 또는 페이지 번호 링크)
        try:
            next_link = page.get_by_role("link", name=re.compile(r"Next|>", re.I))
            if hasattr(next_link, 'count') and await next_link.count():
                try:
                    await next_link.click()
                    await asyncio.sleep(random.uniform(1, 3))  # 페이지 전환 후 지연
                    await page.wait_for_load_state("domcontentloaded", timeout=60000)
                    continue
                except Exception:
                    break
        except:
            # 대안 방법: CSS 선택자로 다음 페이지 찾기
            try:
                next_links = await page.query_selector_all('a:has-text("Next"), a:has-text(">")')
                if next_links:
                    await next_links[0].click()
                    await asyncio.sleep(random.uniform(1, 3))
                    await page.wait_for_load_state("domcontentloaded", timeout=60000)
                    continue
            except:
                break
        
        # 없으면 종료
        break
    return html_pages

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

        rows.append({
            "k_number": knum,
            "device_name": dev_name,
            "applicant": applicant,
            "product_code": product_code,
            "decision_date": decision_date,
            "detail_url": detail_url
        })
    # 빈 로우 제거
    rows = [r for r in rows if r["k_number"]]
    return rows

async def main():
    state = load_state()
    seen = set(state.get("seen_k_numbers", []))
    all_new = []

    async with async_playwright() as p:
        # 더 강력한 우회 옵션 추가
        browser = await p.chromium.launch(
            headless=False,  # 헤드리스 모드 비활성화로 더 자연스럽게
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-web-security",
                "--disable-features=VizDisplayCompositor",
                "--disable-ipc-flooding-protection",
                "--disable-background-timer-throttling",
                "--disable-backgrounding-occluded-windows",
                "--disable-renderer-backgrounding",
                "--disable-features=TranslateUI",
                "--disable-ipc-flooding-protection",
                "--disable-hang-monitor",
                "--disable-prompt-on-repost",
                "--disable-client-side-phishing-detection",
                "--disable-component-extensions-with-background-pages",
                "--disable-default-apps",
                "--disable-sync",
                "--disable-translate",
                "--hide-scrollbars",
                "--mute-audio",
                "--no-first-run",
                "--safebrowsing-disable-auto-update",
                "--disable-extensions",
                "--disable-plugins",
                "--disable-images",
                "--disable-javascript",
                "--disable-css",
                "--disable-gpu",
                "--disable-software-rasterizer",
                "--disable-background-networking",
                "--disable-default-apps",
                "--disable-sync",
                "--disable-translate",
                "--metrics-recording-only",
                "--no-report-upload",
                "--disable-background-timer-throttling",
                "--disable-backgrounding-occluded-windows",
                "--disable-renderer-backgrounding",
                "--disable-features=TranslateUI",
                "--disable-ipc-flooding-protection",
                "--disable-hang-monitor",
                "--disable-prompt-on-repost",
                "--disable-client-side-phishing-detection",
                "--disable-component-extensions-with-background-pages",
                "--disable-default-apps",
                "--disable-sync",
                "--disable-translate",
                "--hide-scrollbars",
                "--mute-audio",
                "--no-first-run",
                "--safebrowsing-disable-auto-update"
            ]
        )
        
        # 더 자연스러운 브라우저 컨텍스트 설정
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='en-US',
            timezone_id='America/New_York',
            permissions=['geolocation'],
            extra_http_headers={
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache',
                'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                'Sec-Ch-Ua-Mobile': '?0',
                'Sec-Ch-Ua-Platform': '"macOS"',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Upgrade-Insecure-Requests': '1'
            }
        )
        
        # JavaScript 실행으로 자동화 감지 우회
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
            });
            window.chrome = {
                runtime: {},
            };
        """)
        
        page = await context.new_page()
        
        # 페이지 로드 전 추가 설정
        await page.set_extra_http_headers({
            'Referer': 'https://www.google.com/',
            'Origin': 'https://www.accessdata.fda.gov'
        })

        # 1) Product Code 워치
        for pc in WATCH_PRODUCT_CODES:
            print(f"Searching for Product Code: {pc}")
            html_pages = await run_query(page, product_code=pc)
            for html in html_pages:
                for r in parse_results(html):
                    if r["k_number"] not in seen:
                        all_new.append(("Product code = " + pc, r))
                        seen.add(r["k_number"])

        # 2) Applicant 워치 (부분일치; FDA는 대개 대소문자 구분 없음)
        for ap in WATCH_APPLICANTS:
            print(f"Searching for Applicant: {ap}")
            html_pages = await run_query(page, applicant=ap)
            for html in html_pages:
                for r in parse_results(html):
                    if r["k_number"] not in seen:
                        all_new.append((f'Applicant contains "{ap}"', r))
                        seen.add(r["k_number"])

        await browser.close()

    # 알림 및 상태 저장
    print(f"=== DEBUG INFO ===")
    print(f"Total results found: {len(seen)}")
    print(f"New results found: {len(all_new)}")
    print(f"All new items: {all_new}")
    
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
            f"<p style='color:#666'>출처: FDA 510(k) 웹 데이터베이스. (웹 DB 주간 갱신, 다운로드 월간 갱신)</p>"
        )
        send_email(f"[510(k) HTML] 신규 {len(all_new)}건 감지", html)
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
            f"<p style='color:#666'>출처: FDA 510(k) 웹 데이터베이스. (웹 DB 주간 갱신, 다운로드 월간 갱신)</p>"
        )
        send_email(f"[510(k) HTML] 일일 모니터링 리포트 - 신규 항목 없음", html)
        print("No new 510(k) approvals found - Daily report email sent")

    # seen 업데이트 (최대 규모 제한)
    print(f"Updating state file with {len(seen)} seen K-numbers")
    state["seen_k_numbers"] = list(seen)[-5000:]
    save_state(state)
    print(f"State file updated successfully")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        print(traceback.format_exc())