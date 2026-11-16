import os
import json
import time
import urllib.request
import urllib.parse
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))
now_dt = datetime.now(KST)
now_str = now_dt.strftime("%Y년 %m월 %d일 %H:%M 기준")
today_date = now_dt.strftime("%Y년 %m월 %d일")

def get_yahoo_price(symbol, name, is_krw=False):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=2d"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as res:
            data = json.loads(res.read().decode())
            meta = data['chart']['result'][0]['meta']
            price = meta['regularMarketPrice']
            prev = meta['chartPreviousClose']
            diff_pct = ((price - prev) / prev) * 100
            sign = "+" if diff_pct >= 0 else ""
            price_fmt = f"{price:,.0f}원" if is_krw else f"{price:,.2f}"
            return {"name": name, "price": price_fmt, "change": f"{sign}{diff_pct:.2f}%"}
    except Exception:
        return {"name": name, "price": "조회 실패", "change": "0.00%"}

markets = [
    # 주요 지수 및 코인/환율/원자재
    get_yahoo_price("^GSPC", "미국 S&P 500"),
    get_yahoo_price("^IXIC", "미국 나스닥"),
    get_yahoo_price("BTC-USD", "비트코인 (USD)"),
    get_yahoo_price("ETH-USD", "이더리움 (USD)"),
    get_yahoo_price("KRW=X", "원/달러 환율", is_krw=True),
    get_yahoo_price("^KS11", "코스피 (KOSPI)"),
    get_yahoo_price("GC=F", "국제 금 시세"),

    # 국내 주요 종목
    get_yahoo_price("005930.KS", "삼성전자", is_krw=True),
    get_yahoo_price("000660.KS", "SK하이닉스", is_krw=True),

    # 미국 주요 종목
    get_yahoo_price("NVDA", "엔비디아"),
    get_yahoo_price("MSFT", "마이크로소프트"),
    get_yahoo_price("GOOGL", "구글 (알파벳)"),
    get_yahoo_price("AMZN", "아마존"),
    get_yahoo_price("META", "메타"),
    get_yahoo_price("TSLA", "테슬라"),
    get_yahoo_price("V", "비자 (Visa)"),
    get_yahoo_price("ZTS", "조에티스 (ZTS)"),
    get_yahoo_price("DIS", "디즈니 (DIS)"),
    get_yahoo_price("FERG", "퍼거슨 (FERG)"),
    get_yahoo_price("RIG", "트랜스오션 (RIG)")
]

def fetch_rss_titles(query, hl="ko", gl="KR", ceid="KR:ko", limit=12):
    titles = []
    try:
        encoded_query = urllib.parse.quote(query)
        url = f"https://news.google.com/rss/search?q={encoded_query}&hl={hl}&gl={gl}&ceid={ceid}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as res:
            root = ET.fromstring(res.read())
            for item in root.findall('.//item')[:limit]:
                title_el = item.find('title')
                if title_el is not None and title_el.text:
                    titles.append(title_el.text)
    except Exception:
        pass
    return list(dict.fromkeys(titles))

# 1) 한국어 거시·증시 뉴스
kr_market_news = fetch_rss_titles(
    "미국증시 OR 나스닥 OR 연준 OR FOMC OR 국채금리 OR 환율",
    hl="ko", gl="KR", ceid="KR:ko", limit=12
)

# 2) 한국어 주요 종목·반도체·AI 뉴스
kr_stock_news = fetch_rss_titles(
    "엔비디아 OR 테슬라 OR 마이크로소프트 OR 삼성전자 OR SK하이닉스 OR 빅테크",
    hl="ko", gl="KR", ceid="KR:ko", limit=10
)

# 3) 한국어 암호화폐 뉴스
kr_crypto_news = fetch_rss_titles(
    "비트코인 OR 이더리움 OR 암호화폐 OR 가상자산 OR 현물 ETF",
    hl="ko", gl="KR", ceid="KR:ko", limit=10
)

# 4) 미국 현지 영문 금융·코인 헤드라인 (더 빠르고 깊은 디테일 보강용)
us_en_news = fetch_rss_titles(
    "Stock market OR Fed OR Nvidia OR Bitcoin ETF OR Crypto",
    hl="en-US", gl="US", ceid="US:en", limit=12
)

api_key = os.environ.get("GEMINI_API_KEY", "").strip()

quote = "오늘도 냉철한 판단과 흔들림 없는 원칙으로 시장을 이기는 하루를 시작하세요!"
summary = ""

def get_available_models(key):
    valid_models = []
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
        req = urllib.request.Request(url, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as res:
            data = json.loads(res.read().decode())
            for m in data.get("models", []):
                name = m.get("name", "")
                methods = m.get("supportedGenerationMethods", [])
                if "generateContent" in methods and "gemini" in name:
                    if not any(x in name for x in ["embedding", "imagen", "veo", "aqa", "tts"]):
                        valid_models.append(name.replace("models/", ""))
    except Exception:
        pass

    valid_models.sort(key=lambda x: (
        0 if "flash" in x and "lite" not in x else (1 if "flash" in x else 2),
        x
    ))
    return valid_models if valid_models else ["gemini-3.8-flash"]

def call_gemini_smart(prompt, key):
    models = get_available_models(key)
    last_error = ""
    for model in models:
        for attempt in range(3):
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
                payload = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode("utf-8")
                req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=60) as res:
                    result = json.loads(res.read().decode())
                    return result["candidates"][0]["content"]["parts"][0]["text"], None
            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8", errors="ignore")
                last_error = f"AI API 호출 오류 ({model} / {e.code}): {err_body}"
                if e.code in (429, 500, 502, 503, 504):
                    time.sleep(6)
                    continue
                else:
                    break
            except Exception as e:
                last_error = f"AI 요약 오류 ({model}): {str(e)}"
                time.sleep(3)
    return None, f"시도한 모델 목록: {models}\n마지막 오류: {last_error}"

if not api_key:
    summary = "오류: GitHub Secrets에 GEMINI_API_KEY가 등록되지 않았거나 비어 있습니다."
elif not (kr_market_news or kr_stock_news or kr_crypto_news or us_en_news):
    summary = "오류: 구글 뉴스 헤드라인을 수집하지 못했습니다."
else:
    market_summary_str = "\n".join(f"- {m['name']}: {m['price']} ({m['change']})" for m in markets)
    kr_m_text = "\n".join(f"- {t}" for t in kr_market_news)
    kr_s_text = "\n".join(f"- {t}" for t in kr_stock_news)
    kr_c_text = "\n".join(f"- {t}" for t in kr_crypto_news)
    us_e_text = "\n".join(f"- {t}" for t in us_en_news)

    prompt = (
        f"오늘은 {today_date}입니다. 당신은 월스트리트 최고 투자전략가(CIO)이자 암호화폐 리서치 센터장입니다. "
        "아래 수집된 실시간 주요 자산 시세와 국내외 증시·빅테크·코인 헤드라인을 종합하여, "
        "투자자가 아침 9시 30분에 이 리포트 하나만 읽어도 시장의 전체 맥락과 디테일을 완벽히 꿰뚫을 수 있도록 "
        "매우 깊고 풍부한 프리미엄 모닝 브리핑을 작성해 주세요.\n\n"
        "[출력 형식 - 반드시 아래 구분선 '===SPLIT==='을 기준으로 두 부분을 나누어 출력하세요]\n"
        "첫 번째 부분: 아침에 앱을 켠 투자자의 정신이 번쩍 들고, 하루를 시작할 힘이 나게 만드는 강렬하고 묵직한 모닝 마인드셋/동기부여 문구 (오늘의 시세 및 시장 분위기를 반영하되, 1~2문장으로 짧고 굵게 작성. 따옴표나 부가 설명 없이 문장만 출력)\n"
        "===SPLIT===\n"
        "두 번째 부분: 심층 모닝 마켓 리포트\n"
        "[작성 원칙]\n"
        "1. 피상적인 요약이나 겉핥기식 나열을 절대 금지합니다. 각 사건이 발생한 '근본 원인 -> 시장 참여자들의 해석과 자금 이동 -> 향후 연쇄 파급효과'의 3단계 논리 흐름으로 풍부하게 풀어쓰세요.\n"
        "2. 제공된 실시간 시세 등락률과 영문/국문 헤드라인 속 구체적 키워드, 인물, 수치, 기관명을 적극 인용하여 현장감과 전문성을 극대화하세요.\n"
        "3. 각 섹션당 최소 8~10문장 이상으로 충분히 길고 밀도 있게 작성하고, 가독성을 위해 섹션 내부에서 문단을 2~3개로 적절히 나누어 주세요.\n"
        "4. 아래 4가지 소제목을 반드시 그대로 사용하세요.\n\n"
        "🇺🇸 1. 미국 증시 및 거시경제 심층 분석\n"
        "(S&P500·나스닥 지수 움직임의 핵심 동인, 연준(Fed) 통화정책과 국채금리·달러 인덱스 흐름, 인플레이션 및 고용·경기 지표에 대한 월가의 해석과 유동성 환경을 입체적으로 분석)\n\n"
        "💻 2. AI·빅테크 및 핵심 개별 종목 동향\n"
        "(엔비디아, 마이크로소프트, 구글, 아마존, 메타, 테슬라 및 국내외 반도체(삼성전자·SK하이닉스) 등 주도 섹터의 간밤 핵심 이슈, 실적·수주·규제·AI 인프라 투자 흐름과 종목별 차별화 양상을 상세히 서술)\n\n"
        "₿ 3. 비트코인 및 암호화폐 시장 심층 동향\n"
        "(비트코인·이더리움 가격 변동 배경, 미국 현물 ETF 자금 유입·유출 추이, 기관 및 고래 수급 동향, 거시경제(금리·달러)와의 상관관계 및 주요 알트코인·규제 이슈까지 깊이 있게 다룸)\n\n"
        "📌 4. 오늘 국내 증시(코스피·코스닥) 파급효과 및 대응 전략\n"
        "(간밤 미 증시와 코인, 원/달러 환율 흐름이 오늘 장중 코스피·코스닥 수급과 반도체·성장주에 미칠 구체적 영향, 오늘 밤 및 이번 주 예정된 핵심 경제 일정·이벤트, 투자자가 반드시 점검해야 할 리스크와 포트폴리오 대응 전략)\n\n"
        f"[현재 주요 자산 시세]\n{market_summary_str}\n\n"
        f"[국내 증시·거시 헤드라인]\n{kr_m_text}\n\n"
        f"[주요 종목·반도체·빅테크 헤드라인]\n{kr_s_text}\n\n"
        f"[암호화폐 시장 헤드라인]\n{kr_c_text}\n\n"
        f"[미국 현지 글로벌 금융·코인 헤드라인]\n{us_e_text}"
    )

    full_text, err = call_gemini_smart(prompt, api_key)
    if full_text:
        if "===SPLIT===" in full_text:
            parts = full_text.split("===SPLIT===", 1)
            quote = parts[0].strip()
            summary = parts[1].strip()
        else:
            summary = full_text.strip()
    else:
        summary = err

output = {
    "updated_at": now_str,
    "quote": quote,
    "markets": markets,
    "summary": summary
}

with open("data.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
