import os
import json
import urllib.request
import urllib.parse
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

def fetch_rss_titles(query, limit=10):
    titles = []
    try:
        encoded_query = urllib.parse.quote(query)
        url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as res:
            root = ET.fromstring(res.read())
            for item in root.findall('.//item')[:limit]:
                titles.append(item.find('title').text)
    except Exception:
        pass
    return list(dict.fromkeys(titles))

us_market_news = fetch_rss_titles("미국증시 OR 나스닥 OR 연준 OR FOMC OR 엔비디아", limit=10)
crypto_news = fetch_rss_titles("비트코인 OR 이더리움 OR 암호화폐 OR 가상자산 ETF", limit=10)

api_key = os.environ.get("GEMINI_API_KEY", "").strip()

quote = "오늘도 냉철한 판단과 흔들림 없는 원칙으로 시장을 이기는 하루를 시작하세요!"
summary = ""

if not api_key:
    summary = "오류: GitHub Secrets에 GEMINI_API_KEY가 등록되지 않았거나 비어 있습니다."
elif not us_market_news and not crypto_news:
    summary = "오류: 구글 뉴스 헤드라인을 수집하지 못했습니다."
else:
    try:
        us_text = "\n".join(f"- {t}" for t in us_market_news)
        crypto_text = "\n".join(f"- {t}" for t in crypto_news)

        prompt = (
            f"오늘은 {today_date}입니다. 당신은 월스트리트 매크로 전략가 겸 암호화폐 수석 애널리스트입니다. "
            "아래 수집된 간밤의 미국 증시 뉴스와 비트코인/코인 시장 뉴스를 바탕으로 두 가지를 작성해 주세요.\n\n"
            "[출력 형식 - 반드시 아래 구분선 '===SPLIT==='을 기준으로 두 부분을 나누어 출력하세요]\n"
            "첫 번째 부분: 아침에 앱을 켠 투자자의 정신이 번쩍 들고, 하루를 시작할 힘이 나게 만드는 강렬하고 묵직한 모닝 마인드셋/동기부여 문구 (오늘 시장 분위기를 살짝 반영하되, 1~2문장으로 짧고 굵게 작성. 따옴표나 부가 설명 없이 문장만 출력)\n"
            "===SPLIT===\n"
            "두 번째 부분: 아침 9시 30분에 투자자가 시장을 깊이 있게 이해할 수 있는 상세 모닝 리포트\n"
            "- 각 섹션마다 구체적인 원인·배경·시장 반응을 포함해 5~7문장 이상으로 자세하게 서술하세요.\n"
            "- 아래 3가지 소제목을 반드시 사용하세요.\n\n"
            "🇺🇸 1. 미국 증시 및 거시경제 심층 분석\n"
            "(간밤 뉴욕 증시의 주요 지수 흐름, 연준 인사 발언이나 금리·물가 지표 영향, 엔비디아·빅테크 등 주도 섹터의 움직임과 그 배경을 상세히 설명)\n\n"
            "₿ 2. 비트코인 및 암호화폐 시장 동향\n"
            "(비트코인 및 주요 알트코인의 가격 흐름, 현물 ETF 자금 유입·유출, 기관 동향, 규제 및 거시경제와의 커플링/디커플링 요인을 깊이 있게 분석)\n\n"
            "📌 3. 오늘의 핵심 관전 포인트 및 전략\n"
            "(미국 시장과 코인 흐름이 오늘 국내 증시(코스피/코스닥)와 환율에 미칠 영향, 오늘 밤 예정된 주요 일정이나 투자자가 주의해야 할 리스크 요인 정리)\n\n"
            f"[수집된 미국 증시 헤드라인]\n{us_text}\n\n"
            f"[수집된 암호화폐 헤드라인]\n{crypto_text}"
        )

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        payload = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as res:
            result = json.loads(res.read().decode())
            full_text = result["candidates"][0]["content"]["parts"][0]["text"]
            if "===SPLIT===" in full_text:
                parts = full_text.split("===SPLIT===", 1)
                quote = parts[0].strip()
                summary = parts[1].strip()
            else:
                summary = full_text.strip()
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="ignore")
        summary = f"AI API 호출 오류 ({e.code}): {err_body}"
    except Exception as e:
        summary = f"AI 요약 오류: {str(e)}"

output = {
    "updated_at": now_str,
    "quote": quote,
    "markets": markets,
    "summary": summary
}

with open("data.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
