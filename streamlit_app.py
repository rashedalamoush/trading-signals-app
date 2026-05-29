# streamlit_app.py — نظام إشارات التداول ومحفظة الاستثمار
# شغّله بـ: streamlit run streamlit_app.py
# Streamlit Cloud: ضع ANTHROPIC_API_KEY في Secrets

import streamlit as st
import pandas as pd
import numpy as np
import requests
import feedparser
import yfinance as yf
import os
from datetime import datetime, timedelta, timezone
from plotly.subplots import make_subplots
import plotly.graph_objects as go

# ══════════════════════════════════════════════════════
#  إعدادات الصفحة
# ══════════════════════════════════════════════════════
st.set_page_config(
    page_title="🤖 إشارات التداول والمحفظة",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=Tajawal:wght@400;700;900&display=swap');
html,body,[class*="css"]{font-family:'Tajawal',sans-serif;direction:rtl;}
.stApp{background:#0a0e1a;}
section[data-testid="stSidebar"]{background:#0d1120;border-right:1px solid #1e2d4a;}
.sig-card{border-radius:12px;padding:18px 22px;margin-bottom:12px;border:1px solid #1e2d4a;background:#0f1729;}
.sig-STRONG_BUY{border-left:5px solid #00ff88;background:#0a1f15;}
.sig-BUY{border-left:5px solid #22c55e;background:#0d1a12;}
.sig-HOLD{border-left:5px solid #eab308;background:#1a160a;}
.sig-SELL{border-left:5px solid #f97316;background:#1a0f08;}
.sig-STRONG_SELL{border-left:5px solid #ef4444;background:#1a0a0a;}
.kpi-box{background:#0f1729;border:1px solid #1e2d4a;border-radius:10px;padding:16px;text-align:center;}
.kpi-val{font-size:2rem;font-weight:900;font-family:'IBM Plex Mono',monospace;}
.kpi-lbl{font-size:.8rem;color:#64748b;margin-top:4px;}
div[data-testid="stButton"]>button{background:linear-gradient(135deg,#1d4ed8,#0ea5e9);color:white;border:none;
  border-radius:10px;padding:12px 28px;font-size:1.1rem;font-family:'Tajawal',sans-serif;font-weight:700;width:100%;}
h1,h2,h3{font-family:'Tajawal',sans-serif!important;color:#e2e8f0!important;}
.etf-card{border-radius:10px;padding:14px 18px;margin-bottom:10px;border:1px solid #1e3a5f;background:#0a1628;}
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════
#  Anthropic AI  — عبر requests (بدون حزمة anthropic)
# ══════════════════════════════════════════════════════
def call_claude(prompt: str, system: str = "", max_tokens: int = 800) -> str:
    """يستدعي Claude API مباشرةً بدون حزمة anthropic."""
    api_key = ""
    try:
        api_key = st.secrets["ANTHROPIC_API_KEY"]
    except Exception:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    if not api_key:
        return (
            "⚠️ **لم يُضف مفتاح API.**\n\n"
            "على Streamlit Cloud: اذهب إلى **Settings → Secrets** وأضف:\n"
            "```\nANTHROPIC_API_KEY = \"sk-ant-...\"\n```"
        )

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    body: dict = {
        "model": "claude-opus-4-5",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system

    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=body,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["content"][0]["text"]
    except requests.exceptions.Timeout:
        return "⏱️ انتهت مهلة الطلب. حاول مرة أخرى."
    except requests.exceptions.HTTPError as e:
        code = e.response.status_code if e.response is not None else 0
        if code == 401:
            return "❌ مفتاح API غير صالح. تحقق من ANTHROPIC_API_KEY."
        if code == 429:
            return "⚠️ تجاوزت حد الطلبات. انتظر قليلاً."
        return f"❌ خطأ HTTP {code}: {e}"
    except Exception as e:
        return f"❌ خطأ: {e}"


# ══════════════════════════════════════════════════════
#  المحفظة — CSV محلي
# ══════════════════════════════════════════════════════
PORTFOLIO_FILE = "portfolio.csv"

def load_portfolio() -> pd.DataFrame:
    if os.path.exists(PORTFOLIO_FILE):
        return pd.read_csv(PORTFOLIO_FILE)
    return pd.DataFrame(columns=["Symbol", "AssetType", "Quantity", "AvgPrice", "AddedAt"])

def add_to_portfolio(symbol: str, asset_type: str, qty: float, price: float) -> None:
    df = load_portfolio()
    if symbol in df["Symbol"].values:
        idx       = df.index[df["Symbol"] == symbol][0]
        old_qty   = df.at[idx, "Quantity"]
        old_price = df.at[idx, "AvgPrice"]
        new_qty   = old_qty + qty
        df.at[idx, "Quantity"] = new_qty
        df.at[idx, "AvgPrice"] = (old_qty * old_price + qty * price) / new_qty
    else:
        new_row = pd.DataFrame([{
            "Symbol": symbol, "AssetType": asset_type,
            "Quantity": qty,  "AvgPrice": price,
            "AddedAt": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }])
        df = pd.concat([df, new_row], ignore_index=True)
    df.to_csv(PORTFOLIO_FILE, index=False)

def remove_from_portfolio(symbol: str) -> None:
    df = load_portfolio()
    df[df["Symbol"] != symbol].to_csv(PORTFOLIO_FILE, index=False)

def clear_portfolio() -> None:
    if os.path.exists(PORTFOLIO_FILE):
        os.remove(PORTFOLIO_FILE)

# ══════════════════════════════════════════════════════
#  قوائم الأصول
# ══════════════════════════════════════════════════════
# ── أسهم أمريكية مقسّمة بالقطاعات ──────────────────────
US_SECTORS: dict[str, list[str]] = {
    "التكنولوجيا": [
        "NVDA","MSFT","AAPL","GOOGL","META","AMZN","AMD","AVGO","QCOM","ORCL",
        "CRM","NOW","ADBE","INTC","TXN","AMAT","LRCX","KLAC","SNPS","CDNS",
        "MRVL","FTNT","PANW","CRWD","ZS","OKTA","DDOG","MDB","SNOW","PLTR",
        "NET","HUBS","WDAY","TEAM","VEEV","TTD","ROKU","TWLO","BILL","RBLX",
        "U","PAYC","DOCU","ZM","EPAM","ANSS","PTC","FSLR","MSCI","COIN",
        "DELL","NTAP","PD","MX",
    ],
    "الصحة والأدوية": [
        "LLY","UNH","JNJ","ABBV","MRK","TMO","ABT","DHR","BMY","AMGN",
        "GILD","ISRG","REGN","VRTX","SYK","BSX","MDT","EW","BDX","IDXX",
        "IQV","MRNA","BNTX","BIIB","ALNY","INCY","ILMN","SRPT","HALO","IONS",
        "RXRX","NUVL","LEGN","KYMR","ARVN","BEAM","CRSP","EDIT","NTLA","PACB",
        "ROIV","ACAD","CRL","ZBH","SDGR","EXEL","RARE","PTGX","BDTX","CRVS",
        "REPL","SLXN","CMND","CDT","SNSE","CCCC","KDLY","RDGT",
    ],
    "المال والبنوك": [
        "BRK-B","JPM","V","MA","BAC","WFC","MS","GS","AXP","SPGI",
        "BLK","CB","PGR","AON","MMC","ICE","CME","MCO","FDS","AIG",
        "TRV","ALL","AFL","MET","PRU","COF","DFS","SYF","ALLY","SOFI",
        "AFRM","UPST","LC","HOOD","MSTR","MARA","RIOT","CLSK","HUT","BITF",
        "FNF","FAF","AMP","RJF","SEIC","LPLA","TROW","BEN","IVZ","WDR",
    ],
    "الطاقة": [
        "XOM","CVX","COP","SLB","EOG","MPC","PSX","VLO","DVN","FANG",
        "HAL","BKR","OXY","HES","APA","MRO","CTRA","PR","SM","ENPH",
        "SEDG","RUN","ARRY","NEE","AES","CEG","VST","NRG","OKE","WMB",
        "KMI","ET","EPD","LNG","CWEN","CLNE","BE","PLUG","FCEL","RIG",
        "VAL","NOV","WHD","PTEN","NE","HP","PBF","PARR","DKL","CAPL",
    ],
    "الاستهلاك": [
        "TSLA","HD","MCD","NKE","SBUX","LOW","TJX","BKNG","CMG","YUM",
        "DPZ","QSR","DKNG","MGM","WYNN","LVS","CZR","HLT","MAR","RCL",
        "CCL","NCLH","UAL","DAL","AAL","LUV","ABNB","UBER","LYFT","DASH",
        "ETSY","W","RVLV","CPRI","TPR","RL","PVH","LEVI","DECK","ONON",
        "LULU","COLM","SKX","VFC","HBI","PTON","CHWY","SFIX","REAL","RENT",
    ],
    "الصناعة": [
        "CAT","HON","RTX","DE","LMT","NOC","GD","BA","GE","MMM",
        "EMR","ETN","PH","IR","AME","ROK","FTV","CARR","TT","JCI",
        "XYL","GNRC","GWW","MSC","FAST","SWK","ITW","DOV","ROP","VRSK",
        "CPRT","SAIA","ODFL","XPO","CHRW","EXPD","FDX","UPS","JBHT","KNX",
        "WERN","ARCB","HTLD","MRTN","SNDR","AXON","TDG","HEI","TXT","SPR",
    ],
    "ناشئة ومضاربية 🆕": [
        "LGCB","SGBX","VCIG","CISO","DGNX","TNMG","LSE","CLIK",
    ],
}
US_STOCKS = [s for stocks in US_SECTORS.values() for s in stocks]

# ── الأسهم الإماراتية مقسّمة بالقطاعات ──────────────────
UAE_SECTORS: dict[str, list[str]] = {
    "العقارات 🏗️": [
        "EMAAR.AE","ALDAR.AE","EMAARDEV.AE","DEYAAR.AE","MAZAYA.AE",
        "AMLAK.AE","ALFIRDOU.AE","NIND.AE","ARMX.AE","ERC.AE",
    ],
    "البنوك والمال 🏦": [
        "EMIRATESNBD.AE","DIB.AE","CBD.AE","MASQ.AE","AJMANBAN.AE",
        "WATANI.AE","EIBANK.AE","SHUAA.AE","GFH.AE","EKTTITAB.AE",
        "ALANSARI.AE","AMANAT.AE","SALAMA.AE",
    ],
    "الطاقة والمرافق ⚡": [
        "DEWA.AE","TABREED.AE","EMPOWER.AE","NCC.AE",
    ],
    "الاتصالات والتقنية 📡": [
        "DU.AE","TECOM.AE","DIC.AE","DSI.AE",
    ],
    "النقل والخدمات 🚗": [
        "AIRARABI.AE","SALIK.AE","PARKIN.AE","GULFNAV.AE",
    ],
    "الاستهلاك والتجزئة 🛒": [
        "TALABAT.AE","SPINNEYS.AE","TAALEEM.AE",
    ],
    "أخرى 🏢": [
        "DFM.AE","IFA.AE","ALRAMZ.AE",
    ],
}
UAE_STOCKS = [s for stocks in UAE_SECTORS.values() for s in stocks]

# ── الأسهم الأوروبية / الألمانية مقسّمة بالقطاعات ───────
#   رموز yfinance:  .DE = شيتْرا (ألمانيا) · .VI = فيينا · .L = لندن
#   .PA = باريس · .OL = أوسلو · .T = طوكيو · .HK = هونغ كونغ
#   .KS = كوريا · .SI = سنغافورة · .AX = أستراليا · .TO = تورنتو
EU_SECTORS: dict[str, list[str]] = {
    "تقنية وبرمجيات 💻": [
        "SAP.DE","IFX.DE","NEM.DE","BC8.DE","NA9.DE","ADN1.DE","GFT.DE","AOF.DE",
        "YSN.DE","FAA.DE","PSAN.DE","D6H.DE","MUM.DE","A1OS.DE","EXL.DE","IXX.DE",
        "COK.DE","SYT.DE","DAM.DE","CSH.DE","SYZ.DE","NFN.DE","LSX.DE","QBY.DE",
        "CYR.DE","SHF.DE","S92.DE","WAF.DE","AIXA.DE","ELG.DE","SMHN.DE","TPE.DE",
        "LPK.DE","SCE.DE","IS7.DE","V6C.DE","BSL.DE","MBQ.DE","M7U.DE","PO0.DE",
    ],
    "صناعة وسيارات 🏭": [
        "SIE.DE","MBG.DE","BMW.DE","VOW3.DE","P911.DE","PAH3.DE","CON.DE","DTG.DE",
        "KGX.DE","HOT.DE","G1A.DE","SHA.DE","HLE.DE","GMM.DE","VOS.DE","DEZ.DE",
        "PFV.DE","ADV.DE","DUE.DE","ZIL2.DE","BDT.DE","NOEJ.DE","KBX.DE","STM.DE",
        "MZX.DE","NTG.DE","PWO.DE","SFQ.DE","JST.DE","MSAG.DE","SF3.DE","SKB.DE",
        "SNG.DE","OHB.DE","TNIE.DE","SUR.DE","RSL2.DE","ED4.DE","HP3A.DE","TTR1.DE",
        "DAR.DE","A6T.DE","S4A.DE","ST5.DE","ULC.DE","ACWN.DE","DLX.DE","UZU.DE",
    ],
    "كيماويات ومواد 🧪": [
        "BAS.DE","BAYN.DE","SY1.DE","BNR.DE","SDF.DE","LXS.DE","NDA.DE","EVK.DE",
        "WCH.DE","1COV.DE","SZG.DE","FPE3.DE","ACT.DE","IBU.DE","DR0.DE","BFSA.DE",
    ],
    "بنوك ومال 🏦": [
        "DBK.DE","CBK.DE","ALV.DE","MUV2.DE","HNR1.DE","TLX.DE","DWS.DE","HYQ.DE",
        "GLJ.DE","PCZ.DE","UBK.DE","BWB.DE","JDC.DE","WUW.DE","NBG6.DE","PBB.DE",
        "MLP.DE","VG8.DE","MBB.DE","DBAN.DE","A7A.DE","MWB.DE","SB1.DE","SXP.DE",
        "BKHT.DE","DBQ.DE","FRU.DE","MUX.DE",
    ],
    "طاقة ومرافق ⚡": [
        "RWE.DE","EOAN.DE","EBK.DE","ENR.DE","NDX1.DE","2GB.DE","VBK.DE","PNE3.DE",
        "AB9.DE","HRPK.DE","EKT.DE","F3C.DE","NCH2.DE","H2O.DE","UUU.DE",
    ],
    "صحة وأدوية ⚕️": [
        "FRE.DE","FME.DE","MRK.DE","QIA.DE","SRT3.DE","EVT.DE","AFX.DE","RDC.DE",
        "GXI.DE","DRW3.DE","HPHA.DE","ILM1.DE","FYB.DE","B8F.DE","EUZ.DE","MED.DE",
        "M12.DE","RHK.DE","GME.DE","V3V.DE","AJ91.DE","BNN.DE","BGT.DE","AAQ.DE",
    ],
    "استهلاك وتجزئة 🛒": [
        "ADS.DE","PUM.DE","BOSS.DE","ZAL.DE","HFG.DE","DHER.DE","G24.DE","RAA.DE",
        "DOU.DE","BIJ.DE","FIE.DE","LEI.DE","BYW6.DE","SZU.DE","HBH.DE","TTK.DE",
        "WEW.DE","GFG.DE","BIKE.DE","AG1.DE","DEX.DE","SWA.DE","BEZ.DE","HAW.DE",
        "BST.DE","KA8.DE","ACX.DE","EDL.DE","SPG.DE","CEC.DE","RRTL.DE","BVB.DE",
        "PGN.DE","CA1.DE","R1B.DE","HNL.DE","KWS.DE",
    ],
    "عقارات 🏗️": [
        "VNA.DE","LEG.DE","TEG.DE","GYC.DE","DWNI.DE","AT1.DE","ADJ.DE","GTY.DE",
        "FC9.DE","RCM.DE","DEQ.DE","DEF.DE","PAT.DE","VIH.DE",
    ],
    "طيران ودفاع وشحن ✈️": [
        "AIR.DE","RHM.DE","MTX.DE","LHA.DE","TKA.DE","FRA.DE","HLAG.DE","R3NK.DE",
        "FQT.DE","PYR.DE","MA10.DE","LMIA.DE","INH.DE","GSC1.DE","KCO.DE","LIK.DE",
    ],
    "صناعات أخرى 🔧": [
        "HEI.DE","KSB3.DE","DIE.DE","YOC.DE","SBX.DE","TIMA.DE","1SXP.DE","PZS.DE",
    ],
    "أسهم عالمية وآسيوية 🌍": [
        "NVO","ERIC","BTI","BP","PBR","RR.L","H.TO","CS.TO","SCATC.OL","BABA",
        "BYDDY","1810.HK","9992.HK","1913.HK","000660.KS","006400.KS","NTDOY",
        "9983.T","6367.T","6301.T","HTHIY","7011.T","7012.T","8058.T","MITSY",
        "ITOCY","FJTSY","9101.T","5802.T","TKOMY","300750.SZ","J36.SI","U11.SI",
        "S68.SI","CBA.AX","LYC.AX",
    ],
    "النمسا 🇦🇹": [
        "EBS.VI","RBI.VI","VOE.VI","VER.VI","WIE.VI","ANDR.VI","STR.VI","TKA.VI",
        "OMV.VI","ATS.VI","POS.VI","FACC.VI","ZAG.VI",
    ],
}
EU_STOCKS = [s for stocks in EU_SECTORS.values() for s in stocks]

DEFAULT_STOCKS = US_STOCKS + UAE_STOCKS + EU_STOCKS

# ── ETFs ──────────────────────────────────────────────
ETF_CATALOG: dict[str, dict] = {
    "SPY":  {"name": "SPDR S&P 500",             "category": "سوق أمريكي",   "er": "0.09%"},
    "VOO":  {"name": "Vanguard S&P 500",          "category": "سوق أمريكي",   "er": "0.03%"},
    "VTI":  {"name": "Vanguard Total Market",     "category": "سوق أمريكي",   "er": "0.03%"},
    "IVV":  {"name": "iShares Core S&P 500",      "category": "سوق أمريكي",   "er": "0.03%"},
    "QQQ":  {"name": "Invesco Nasdaq-100",         "category": "تقنية",        "er": "0.20%"},
    "QQQM": {"name": "Invesco Nasdaq-100 Mini",   "category": "تقنية",        "er": "0.15%"},
    "XLK":  {"name": "Technology Select Sector",  "category": "تقنية",        "er": "0.09%"},
    "XLF":  {"name": "Financial Select Sector",   "category": "مالي",         "er": "0.09%"},
    "XLE":  {"name": "Energy Select Sector",      "category": "طاقة",         "er": "0.09%"},
    "XLV":  {"name": "Health Care Select",        "category": "صحة",          "er": "0.09%"},
    "XLY":  {"name": "Consumer Discretionary",    "category": "استهلاكي",     "er": "0.09%"},
    "XLI":  {"name": "Industrial Select",         "category": "صناعي",        "er": "0.09%"},
    "BOTZ": {"name": "Global X Robotics & AI",    "category": "ذكاء اصطناعي","er": "0.68%"},
    "AIQ":  {"name": "Global X AI & Tech",        "category": "ذكاء اصطناعي","er": "0.68%"},
    "ARKK": {"name": "ARK Innovation",            "category": "ابتكار",       "er": "0.75%"},
    "ARKG": {"name": "ARK Genomic Revolution",    "category": "تقنية حيوية",  "er": "0.75%"},
    "ARKW": {"name": "ARK Next Gen Internet",     "category": "ابتكار",       "er": "0.88%"},
    "EEM":  {"name": "iShares MSCI Em. Markets",  "category": "أسواق ناشئة",  "er": "0.68%"},
    "VWO":  {"name": "Vanguard Em. Markets",      "category": "أسواق ناشئة",  "er": "0.08%"},
    "VXUS": {"name": "Vanguard Total Intl",       "category": "دولي",         "er": "0.07%"},
    "EFA":  {"name": "iShares MSCI EAFE",         "category": "دولي متقدم",   "er": "0.32%"},
    "GLD":  {"name": "SPDR Gold Shares",          "category": "ذهب",          "er": "0.40%"},
    "IAU":  {"name": "iShares Gold Trust",        "category": "ذهب",          "er": "0.25%"},
    "SLV":  {"name": "iShares Silver Trust",      "category": "فضة",          "er": "0.50%"},
    "USO":  {"name": "United States Oil Fund",    "category": "نفط",          "er": "0.60%"},
    "TLT":  {"name": "iShares 20+ Yr Treasury",   "category": "سندات",        "er": "0.15%"},
    "AGG":  {"name": "iShares Core US Agg Bond",  "category": "سندات",        "er": "0.03%"},
    "BND":  {"name": "Vanguard Total Bond",       "category": "سندات",        "er": "0.03%"},
    "IWM":  {"name": "iShares Russell 2000",      "category": "شركات صغيرة", "er": "0.19%"},
    "VUG":  {"name": "Vanguard Growth ETF",       "category": "نمو",          "er": "0.04%"},
    "VTV":  {"name": "Vanguard Value ETF",        "category": "قيمة",         "er": "0.04%"},
}
DEFAULT_ETF = list(ETF_CATALOG.keys())

# ══════════════════════════════════════════════════════
#  معاملات المؤشرات
# ══════════════════════════════════════════════════════
RSI_OVERSOLD = 30; RSI_OVERBOUGHT = 70; RSI_PERIOD = 14
MACD_FAST = 12;   MACD_SLOW = 26;       MACD_SIGNAL_P = 9
BB_PERIOD = 20;   BB_STD = 2.0
MA_SHORT = 20;    MA_LONG = 50

SIGNAL_EMOJI = {
    "STRONG_BUY":  "🚀 شراء قوي",
    "BUY":         "🟢 شراء",
    "HOLD":        "🟡 انتظار",
    "SELL":        "🔴 بيع",
    "STRONG_SELL": "💥 بيع قوي",
}
SIGNAL_COLOR = {
    "STRONG_BUY":  "#00ff88",
    "BUY":         "#22c55e",
    "HOLD":        "#eab308",
    "SELL":        "#f97316",
    "STRONG_SELL": "#ef4444",
}

# ══════════════════════════════════════════════════════
#  جلب البيانات
# ══════════════════════════════════════════════════════
def fetch_stock(symbol: str):
    try:
        df = yf.Ticker(symbol).history(period="6mo", interval="1d")
        if df.empty:
            return None
        return df[["Open","High","Low","Close","Volume"]].dropna()
    except:
        return None

fetch_etf = fetch_stock

def get_current_price(symbol: str) -> float:
    try:
        return float(yf.Ticker(symbol).history(period="2d")["Close"].iloc[-1])
    except:
        return 0.0

# ══════════════════════════════════════════════════════
#  المؤشرات التقنية
# ══════════════════════════════════════════════════════
def calc_indicators(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    delta = d["Close"].diff()
    gain  = delta.clip(lower=0)
    loss  = -delta.clip(upper=0)
    ag = gain.ewm(com=RSI_PERIOD - 1, adjust=False).mean()
    al = loss.ewm(com=RSI_PERIOD - 1, adjust=False).mean()
    d["RSI"]      = 100 - (100 / (1 + ag / al.replace(0, np.nan)))
    ef = d["Close"].ewm(span=MACD_FAST,     adjust=False).mean()
    es = d["Close"].ewm(span=MACD_SLOW,     adjust=False).mean()
    d["MACD"]     = ef - es
    d["MACD_Sig"] = d["MACD"].ewm(span=MACD_SIGNAL_P, adjust=False).mean()
    d["MACD_Hist"]= d["MACD"] - d["MACD_Sig"]
    sma = d["Close"].rolling(BB_PERIOD).mean()
    std = d["Close"].rolling(BB_PERIOD).std()
    d["BB_U"] = sma + BB_STD * std
    d["BB_L"] = sma - BB_STD * std
    d["BB_M"] = sma
    d[f"MA{MA_SHORT}"] = d["Close"].rolling(MA_SHORT).mean()
    d[f"MA{MA_LONG}"]  = d["Close"].rolling(MA_LONG).mean()
    d["Vol_MA"] = d["Volume"].rolling(20).mean()
    d["Vol_R"]  = d["Volume"] / d["Vol_MA"]
    return d

def get_signal(df: pd.DataFrame):
    last = df.iloc[-1]; prev = df.iloc[-2]
    buy = 0; sell = 0; reasons = []
    c = float(last["Close"])

    low6m = df["Low"].min()
    if low6m > 0 and (c - low6m) / low6m <= 0.05:
        buy += 1; reasons.append(f"🔥 قريب من قاع 6 أشهر ({low6m:.4f})")

    rsi = float(last["RSI"])
    if rsi < RSI_OVERSOLD:
        buy  += 1; reasons.append(f"RSI={rsi:.1f} تشبع بيعي")
    elif rsi > RSI_OVERBOUGHT:
        sell += 1; reasons.append(f"RSI={rsi:.1f} تشبع شرائي")

    h = float(last["MACD_Hist"]); hp = float(prev["MACD_Hist"])
    if hp < 0 < h:
        buy  += 1; reasons.append("MACD عبر الصفر صعوداً")
    elif hp > 0 > h:
        sell += 1; reasons.append("MACD عبر الصفر هبوطاً")

    if c < float(last["BB_L"]):
        buy  += 1; reasons.append("السعر تحت Bollinger السفلي")
    elif c > float(last["BB_U"]):
        sell += 1; reasons.append("السعر فوق Bollinger العلوي")

    ms = float(last[f"MA{MA_SHORT}"]); ml  = float(last[f"MA{MA_LONG}"])
    msp= float(prev[f"MA{MA_SHORT}"]); mlp = float(prev[f"MA{MA_LONG}"])
    if msp < mlp and ms > ml:
        buy  += 1; reasons.append(f"تقاطع ذهبي MA{MA_SHORT}/MA{MA_LONG}")
    elif msp > mlp and ms < ml:
        sell += 1; reasons.append(f"تقاطع الموت MA{MA_SHORT}/MA{MA_LONG}")

    vr = float(last["Vol_R"])
    if vr > 1.5:
        if buy > sell:
            buy  += 1; reasons.append(f"حجم مرتفع ({vr:.1f}x) يؤكد الشراء")
        elif sell > buy:
            sell += 1; reasons.append(f"حجم مرتفع ({vr:.1f}x) يؤكد البيع")

    net = buy - sell
    if net >= 3:    sig = "STRONG_BUY"
    elif net >= 2:  sig = "BUY"
    elif net <= -3: sig = "STRONG_SELL"
    elif net <= -2: sig = "SELL"
    else:           sig = "HOLD"
    return sig, reasons, rsi, float(last["MACD_Hist"]), vr, c

# ══════════════════════════════════════════════════════
#  تحليل الأخبار
# ══════════════════════════════════════════════════════
POS_WORDS  = {"surge","soar","rally","jump","boom","bullish","breakout","record",
              "growth","profit","beat","upgrade","buy","strong","gain","rise","approved","partnership"}
NEG_WORDS  = {"crash","plunge","drop","fall","decline","bearish","loss","miss",
              "downgrade","sell","weak","tumble","slump","recession","ban","fraud","bankruptcy"}
STRONG_POS = {"surge","soar","boom","record","breakout","approved"}
STRONG_NEG = {"crash","ban","fraud","bankruptcy","rug pull"}

STOCK_KW = {
    "AAPL":["Apple","AAPL"],"MSFT":["Microsoft","MSFT"],"NVDA":["Nvidia","NVDA"],
    "TSLA":["Tesla","TSLA"],"EMAAR.AE":["Emaar","إعمار"],"DIB.AE":["Dubai Islamic Bank"],
    "EMIRATESNBD.AE":["Emirates NBD"],"ALDAR.AE":["Aldar","الدار"],"AIRARABI.AE":["Air Arabia"],
    "DEWA.AE":["DEWA","ديوا"],"SALIK.AE":["Salik","سالك"],"TALABAT.AE":["Talabat","طلبات"],
    "SAP.DE":["SAP"],"SIE.DE":["Siemens"],"MBG.DE":["Mercedes-Benz","Mercedes"],
    "BMW.DE":["BMW"],"VOW3.DE":["Volkswagen"],"ALV.DE":["Allianz"],"BAYN.DE":["Bayer"],
    "BAS.DE":["BASF"],"DBK.DE":["Deutsche Bank"],"RHM.DE":["Rheinmetall"],"AIR.DE":["Airbus"],
    "IFX.DE":["Infineon"],"DTE.DE":["Deutsche Telekom"],"ADS.DE":["Adidas"],"PUM.DE":["Puma"],
    "NVO":["Novo Nordisk"],"BABA":["Alibaba"],"BYDDY":["BYD"],"PBR":["Petrobras"],
    "DELL":["Dell"],"NTAP":["NetApp"],"PD":["PagerDuty"],"REPL":["Replimune"],
}
ETF_KW = {
    "SPY":["S&P 500","SPY"],"QQQ":["Nasdaq","QQQ"],"VTI":["Vanguard","VTI"],
    "GLD":["Gold","GLD","ذهب"],"ARKK":["ARK","ARKK"],
    "TLT":["Treasury","TLT","bonds"],"EEM":["emerging markets","EEM"],
}

def analyze_sentiment(text: str) -> float:
    t = text.lower(); score = 0.0
    for w in STRONG_POS:
        if w in t: score += 0.4
    for w in STRONG_NEG:
        if w in t: score -= 0.4
    for w in POS_WORDS - STRONG_POS:
        if w in t: score += 0.15
    for w in NEG_WORDS - STRONG_NEG:
        if w in t: score -= 0.15
    return max(-1.0, min(1.0, score))

def sentiment_label(s: float) -> str:
    if s >=  0.4: return "🟢 إيجابي قوي"
    if s >=  0.15: return "🟡 إيجابي"
    if s <= -0.4: return "🔴 سلبي قوي"
    if s <= -0.15: return "🟠 سلبي"
    return "⚪ محايد"

def fetch_news(symbol: str, asset_type: str) -> dict:
    articles = []
    kws_map = ETF_KW if asset_type == "etf" else STOCK_KW
    fallback = symbol
    for suf in (".AE",".DE",".VI",".L",".PA",".OL",".T",".HK",".KS",".SI",".AX",".TO",".SZ"):
        fallback = fallback.replace(suf, "")
    kws = kws_map.get(symbol, [fallback])
    try:
        q    = kws[0].replace(" ", "+")
        feed = feedparser.parse(
            f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={q}&region=US&lang=en-US"
        )
        cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
        for e in feed.entries[:5]:
            try:
                pub = datetime(*e.published_parsed[:6], tzinfo=timezone.utc)
            except:
                pub = datetime.now(timezone.utc)
            if pub < cutoff:
                continue
            t = e.get("title", "")
            s = analyze_sentiment(t + " " + e.get("summary", ""))
            articles.append({"source": "Yahoo", "title": t, "sentiment": s})
    except:
        pass

    if not articles:
        return {"label": "⚪ لا أخبار", "signal": "HOLD", "score": 0.0, "articles": []}

    scores = [a["sentiment"] for a in articles]
    w      = list(range(len(scores), 0, -1))
    avg    = sum(s * wt for s, wt in zip(scores, w)) / sum(w)
    pos    = sum(1 for s in scores if s > 0.1)
    neg    = sum(1 for s in scores if s < -0.1)
    nsig   = "BUY" if avg >= 0.25 and pos > neg else "SELL" if avg <= -0.25 and neg > pos else "HOLD"
    return {"label": sentiment_label(avg), "signal": nsig, "score": round(avg, 3), "articles": articles[:8]}

def merge_signals(tech: str, news_sig: str, news_score: float) -> str:
    up = {"BUY":"STRONG_BUY","SELL":"STRONG_SELL","HOLD":"BUY"}
    dn = {"STRONG_BUY":"BUY","STRONG_SELL":"SELL","BUY":"HOLD","SELL":"HOLD"}
    bull = news_sig == "BUY"  and news_score >  0.2
    bear = news_sig == "SELL" and news_score < -0.2
    if tech in ("BUY","STRONG_BUY")   and bull: return up.get(tech, tech)
    if tech in ("SELL","STRONG_SELL") and bear: return up.get(tech, tech)
    if tech in ("BUY","STRONG_BUY")   and bear: return dn.get(tech, "HOLD")
    if tech in ("SELL","STRONG_SELL") and bull: return dn.get(tech, "HOLD")
    if tech == "HOLD" and bull: return "BUY"
    if tech == "HOLD" and bear: return "SELL"
    return tech

# ══════════════════════════════════════════════════════
#  الرسم البياني
# ══════════════════════════════════════════════════════
def draw_chart(df: pd.DataFrame, symbol: str) -> go.Figure:
    d   = df.tail(90)
    fig = make_subplots(
        rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.04,
        row_heights=[0.55, 0.25, 0.20],
        subplot_titles=["السعر + Bollinger + MA", "RSI", "MACD"],
    )
    fig.add_trace(go.Candlestick(
        x=d.index, open=d["Open"], high=d["High"], low=d["Low"], close=d["Close"],
        increasing_line_color="#22c55e", decreasing_line_color="#ef4444", name="السعر"),
        row=1, col=1)
    for band, nm in [("BB_U","BB U"), ("BB_L","BB L")]:
        fig.add_trace(go.Scatter(x=d.index, y=d[band],
            line=dict(color="#3b82f6", width=1, dash="dot"),
            fill="tonexty" if band == "BB_L" else None,
            fillcolor="rgba(59,130,246,0.07)", name=nm), row=1, col=1)
    fig.add_trace(go.Scatter(x=d.index, y=d["BB_M"],  line=dict(color="#475569",width=1),   name="BB Mid"),    row=1, col=1)
    fig.add_trace(go.Scatter(x=d.index, y=d[f"MA{MA_SHORT}"], line=dict(color="#f59e0b",width=1.5), name=f"MA{MA_SHORT}"), row=1, col=1)
    fig.add_trace(go.Scatter(x=d.index, y=d[f"MA{MA_LONG}"],  line=dict(color="#a855f7",width=1.5), name=f"MA{MA_LONG}"),  row=1, col=1)
    fig.add_trace(go.Scatter(x=d.index, y=d["RSI"], line=dict(color="#0ea5e9",width=2), name="RSI"), row=2, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="#ef4444", line_width=1, row=2, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="#22c55e", line_width=1, row=2, col=1)
    hist_colors = ["#22c55e" if v >= 0 else "#ef4444" for v in d["MACD_Hist"]]
    fig.add_trace(go.Bar(x=d.index, y=d["MACD_Hist"], marker_color=hist_colors, name="Hist", opacity=0.7), row=3, col=1)
    fig.add_trace(go.Scatter(x=d.index, y=d["MACD"],     line=dict(color="#0ea5e9",width=1.5), name="MACD"),   row=3, col=1)
    fig.add_trace(go.Scatter(x=d.index, y=d["MACD_Sig"], line=dict(color="#f59e0b",width=1.5), name="Signal"), row=3, col=1)
    fig.update_layout(
        height=600, paper_bgcolor="#0a0e1a", plot_bgcolor="#0a0e1a",
        font=dict(color="#94a3b8", family="IBM Plex Mono"),
        legend=dict(orientation="h", y=1.02, bgcolor="rgba(0,0,0,0)"),
        xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=30, b=10),
    )
    for i in range(1, 4):
        fig.update_xaxes(gridcolor="#1e2d4a", row=i, col=1)
        fig.update_yaxes(gridcolor="#1e2d4a", row=i, col=1)
    return fig

# ══════════════════════════════════════════════════════
#  UI — Header + Sidebar
# ══════════════════════════════════════════════════════
st.markdown("# 🤖 نظام إشارات التداول الذكي")
st.markdown(
    "<p style='color:#64748b;margin-top:-14px'>أسهم أمريكية · إماراتية · أوروبية · ETFs · محفظة · أخبار · مستشار AI</p>",
    unsafe_allow_html=True,
)
st.divider()

with st.sidebar:
    st.markdown("### ⚙️ الإعدادات")
    asset_type = st.radio(
        "نوع الأصل",
        ["📈 أسهم", "📦 ETFs", "🌐 الكل"],
        index=2,
    )

    # ── الأسهم الأمريكية بالقطاعات ──────────────────────
    st.markdown("**📈 الأسهم الأمريكية — اختر القطاع**")
    us_sector_sel = st.selectbox(
        "القطاع الأمريكي",
        ["الكل"] + list(US_SECTORS.keys()),
        label_visibility="collapsed",
        key="us_sec",
    )
    us_pool = US_STOCKS if us_sector_sel == "الكل" else US_SECTORS[us_sector_sel]
    sel_us = st.multiselect(
        "أسهم أمريكية", us_pool,
        default=["NVDA","MSFT","AAPL","AMZN","TSLA"],
        label_visibility="collapsed",
        key="us_stocks",
    )

    st.markdown("---")

    # ── الأسهم الإماراتية بالقطاعات ─────────────────────
    st.markdown("**🇦🇪 الأسهم الإماراتية — اختر القطاع**")
    uae_sector_sel = st.selectbox(
        "القطاع الإماراتي",
        ["الكل"] + list(UAE_SECTORS.keys()),
        label_visibility="collapsed",
        key="uae_sec",
    )
    uae_pool = UAE_STOCKS if uae_sector_sel == "الكل" else UAE_SECTORS[uae_sector_sel]
    sel_uae = st.multiselect(
        "أسهم إماراتية", uae_pool,
        default=["EMAAR.AE","SALIK.AE","DEWA.AE","DIB.AE","EMIRATESNBD.AE"],
        label_visibility="collapsed",
        key="uae_stocks",
    )

    st.markdown("---")

    # ── الأسهم الأوروبية / الألمانية بالقطاعات ───────────
    st.markdown("**🇪🇺 الأسهم الأوروبية — اختر القطاع**")
    eu_sector_sel = st.selectbox(
        "القطاع الأوروبي",
        ["الكل"] + list(EU_SECTORS.keys()),
        label_visibility="collapsed",
        key="eu_sec",
    )
    eu_pool = EU_STOCKS if eu_sector_sel == "الكل" else EU_SECTORS[eu_sector_sel]
    sel_eu = st.multiselect(
        "أسهم أوروبية", eu_pool,
        default=["SAP.DE","SIE.DE","ALV.DE","MBG.DE","RHM.DE"],
        label_visibility="collapsed",
        key="eu_stocks",
    )

    sel_stocks = sel_us + sel_uae + sel_eu

    st.markdown("---")

    st.markdown("**📦 صناديق ETF**")
    sel_etfs = st.multiselect(
        "ETFs", DEFAULT_ETF,
        default=["SPY","QQQ","GLD","ARKK","TLT"],
        label_visibility="collapsed",
    )

    st.markdown("---")
    run_btn = st.button("🔍 ابدأ مسح السوق الآن", use_container_width=True)

# ══════════════════════════════════════════════════════
#  Session State
# ══════════════════════════════════════════════════════
for k, v in [("results",[]), ("raw_data",{}), ("last_scan",None), ("ai_chat",[])]:
    if k not in st.session_state:
        st.session_state[k] = v

# ══════════════════════════════════════════════════════
#  المسح
# ══════════════════════════════════════════════════════
if run_btn:
    results: list = []
    raw: dict     = {}

    do_stocks = "أسهم"   in asset_type or "الكل" in asset_type
    do_etfs   = "ETF"    in asset_type or "الكل" in asset_type

    scan_s = sel_stocks if do_stocks else []
    scan_e = sel_etfs   if do_etfs   else []

    total = len(scan_s) + len(scan_e)
    step  = [0]
    prog  = st.progress(0, text="جاري المسح...")
    icons = {"stock": "📈", "etf": "📦"}

    def _process(sym: str, atype: str, fetch_fn) -> None:
        pct = max(step[0] / max(total, 1), 0.01)
        prog.progress(pct, text=f"{icons.get(atype,'•')} {sym}...")
        df = fetch_fn(sym)
        if df is not None and len(df) >= 50:
            df_i = calc_indicators(df)
            raw[sym] = df_i
            news = fetch_news(sym, atype)
            tech_sig, reasons, rsi, mh, vr, price = get_signal(df_i)
            final = merge_signals(tech_sig, news["signal"], news["score"])
            results.append({
                "symbol": sym, "type": atype, "signal": final, "tech": tech_sig,
                "reasons": reasons, "rsi": rsi, "macd_hist": mh, "vol_ratio": vr,
                "price": price, "news_label": news["label"],
                "news_signal": news["signal"], "news_score": news["score"],
                "articles": [a["title"] for a in news["articles"][:4]],
            })
        step[0] += 1

    for sym in scan_s: _process(sym, "stock",  fetch_stock)
    for sym in scan_e: _process(sym, "etf",    fetch_etf)

    prog.empty()
    st.session_state.results   = results
    st.session_state.raw_data  = raw
    st.session_state.last_scan = datetime.now().strftime("%H:%M:%S")
    st.rerun()

results = st.session_state.results
if st.session_state.last_scan:
    st.caption(f"آخر مسح: {st.session_state.last_scan} | {len(results)} أصل")
if not results:
    st.info("👈 اضغط 'ابدأ مسح السوق الآن' من القائمة الجانبية.")
st.markdown("<br>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════
#  التبويبات
# ══════════════════════════════════════════════════════
t1, t2, t3, t4, t5, t6 = st.tabs([
    "📋 إشارات السوق",
    "📦 ETFs",
    "📊 الرسم البياني",
    "📰 الأخبار",
    "💼 محفظتي",
    "🤖 مستشار AI",
])

# ── Tab 1 ─────────────────────────────────────────────
with t1:
    if results:
        order   = {"STRONG_BUY":0,"BUY":1,"HOLD":2,"SELL":3,"STRONG_SELL":4}
        f1, f2, f3  = st.columns([2,1,1])
        sig_f   = f1.multiselect("إشارة", list(SIGNAL_EMOJI.keys()), default=list(SIGNAL_EMOJI.keys()))
        type_f  = f2.multiselect("النوع",["stock","etf"], default=["stock","etf"])

        # بناء قائمة القطاعات المتاحة من النتائج
        def get_sector(sym: str) -> str:
            if sym in UAE_STOCKS: return "🇦🇪 إماراتي"
            for sec, stocks in US_SECTORS.items():
                if sym in stocks: return sec
            for sec, stocks in EU_SECTORS.items():
                if sym in stocks: return f"🇪🇺 {sec}"
            return "أخرى"
        all_sectors = sorted(set(get_sector(r["symbol"]) for r in results if r["type"]=="stock"))
        sector_f = f3.multiselect("القطاع", ["الكل"]+all_sectors, default=["الكل"])

        display = sorted(
            [r for r in results if r["signal"] in sig_f and r["type"] in type_f
             and ("الكل" in sector_f or r["type"]!="stock" or get_sector(r["symbol"]) in sector_f)],
            key=lambda x: order.get(x["signal"], 2),
        )
        TYPE_BG = {"stock":"#1e3a5f","etf":"#1f3a2a"}
        TYPE_LBL= {"stock":"سهم","etf":"ETF"}
        TYPE_IC = {"stock":"📈","etf":"📦"}
        for r in display:
            clr = SIGNAL_COLOR.get(r["signal"],"#64748b")
            lbl = SIGNAL_EMOJI.get(r["signal"], r["signal"])
            sec_tag = get_sector(r["symbol"])
            rs  = "".join(f"<div style='font-size:.83rem;color:#64748b;margin-top:3px'>• {x}</div>" for x in r["reasons"])
            st.markdown(f"""<div class='sig-card sig-{r["signal"]}'>
              <div style='display:flex;justify-content:space-between;align-items:center'>
                <span style='font-size:1.1rem;font-weight:900;color:#e2e8f0'>
                  {TYPE_IC.get(r["type"],"•")} {r["symbol"]}
                  <span style='font-size:.7rem;padding:2px 8px;border-radius:8px;
                    background:{TYPE_BG.get(r["type"],"#1e2d4a")};color:#94a3b8;margin-right:6px'>
                    {TYPE_LBL.get(r["type"],r["type"])}
                  </span>
                  <span style='font-size:.65rem;padding:2px 6px;border-radius:8px;
                    background:#1a2a1a;color:#6ee7b7;margin-right:4px'>
                    {sec_tag}
                  </span>
                </span>
                <span style='font-size:1.3rem;font-weight:900;color:{clr}'>{lbl}</span>
              </div>
              <div style='font-size:.9rem;color:#94a3b8;font-family:IBM Plex Mono,monospace;margin-top:4px'>
                السعر: {r["price"]:,.4f} &nbsp;|&nbsp; RSI: {r["rsi"]:.1f} &nbsp;|&nbsp; {r["news_label"]}
              </div>
              {rs}
            </div>""", unsafe_allow_html=True)
    else:
        st.info("ابدأ المسح لرؤية الإشارات.")

# ── Tab 2 : ETFs ──────────────────────────────────────
with t2:
    st.markdown("### 📦 دليل صناديق ETF")

    cats    = sorted({v["category"] for v in ETF_CATALOG.values()})
    sel_cat = st.multiselect("تصفية حسب الفئة", cats, default=cats, key="etf_cat")

    etf_res = {r["symbol"]: r for r in results if r["type"] == "etf"}

    by_cat: dict[str, list] = {}
    for ticker, info in ETF_CATALOG.items():
        if info["category"] in sel_cat:
            by_cat.setdefault(info["category"], []).append((ticker, info))

    for cat, items in sorted(by_cat.items()):
        st.markdown(f"**{cat}**")
        cols = st.columns(2)
        for i, (ticker, info) in enumerate(items):
            res = etf_res.get(ticker)
            clr = SIGNAL_COLOR.get(res["signal"],"#475569") if res else "#475569"
            lbl = SIGNAL_EMOJI.get(res["signal"],"—")       if res else "غير مفحوص"
            price_str = f"${res['price']:,.2f}"   if res else "—"
            rsi_str   = f"| RSI: {res['rsi']:.1f}" if res else ""
            with cols[i % 2]:
                st.markdown(f"""<div class='etf-card'>
                  <div style='display:flex;justify-content:space-between;align-items:center'>
                    <span style='font-size:1rem;font-weight:900;color:#38bdf8'>{ticker}</span>
                    <span style='font-size:.85rem;color:{clr};font-weight:700'>{lbl}</span>
                  </div>
                  <div style='font-size:.8rem;color:#94a3b8'>{info['name']}</div>
                  <div style='font-size:.75rem;color:#475569;margin-top:4px'>
                    رسوم: {info['er']} &nbsp;|&nbsp; {price_str} {rsi_str}
                  </div>
                </div>""", unsafe_allow_html=True)
        st.markdown("")

# ── Tab 3 : الرسم البياني ─────────────────────────────
with t3:
    if results:
        syms   = [r["symbol"] for r in results]
        chosen = st.selectbox("اختر الأصل", syms)
        df_c   = st.session_state.raw_data.get(chosen)
        if df_c is not None:
            st.plotly_chart(draw_chart(df_c, chosen), use_container_width=True)
    else:
        st.info("ابدأ المسح أولاً.")

# ── Tab 4 : الأخبار ───────────────────────────────────
with t4:
    if results:
        has = [r for r in results if r.get("articles")]
        if has:
            TYPE_IC = {"stock":"📈","etf":"📦"}
            for r in has:
                icon = TYPE_IC.get(r["type"],"•")
                with st.expander(f"{icon} {r['symbol']} — {r['news_label']} ({r['news_score']:+.2f})"):
                    for a in r["articles"]:
                        st.write(f"• {a}")
        else:
            st.info("لا توجد أخبار حديثة.")
    else:
        st.info("ابدأ المسح أولاً.")

# ── Tab 5 : محفظتي ────────────────────────────────────
with t5:
    st.markdown("### 💼 محفظتي الاستثمارية")
    all_assets = sorted(set(DEFAULT_STOCKS + DEFAULT_ETF))

    with st.form("add_form"):
        st.markdown("**إضافة صفقة جديدة:**")
        c1, c2, c3, c4 = st.columns([2,1,1,1])
        p_sym   = c1.selectbox("الأصل", all_assets)
        p_type  = c2.selectbox("النوع", ["stock","etf"])
        p_qty   = c3.number_input("الكمية",    min_value=0.0001, value=1.0,   step=0.1,  format="%.4f")
        p_price = c4.number_input("السعر ($)", min_value=0.0001, value=100.0, step=0.01, format="%.4f")
        if st.form_submit_button("➕ احفظ الصفقة"):
            add_to_portfolio(p_sym, p_type, p_qty, p_price)
            st.success(f"✅ تمت إضافة {p_qty:.4f} من {p_sym}!")
            st.rerun()

    df_port = load_portfolio()
    if not df_port.empty:
        st.markdown("---")
        st.markdown("### 📊 أداء المحفظة")
        total_inv = 0.0; total_cur = 0.0; rows = []

        with st.spinner("جاري جلب الأسعار..."):
            for _, row in df_port.iterrows():
                sym       = row["Symbol"]
                qty       = float(row["Quantity"])
                avg_p     = float(row["AvgPrice"])
                inv       = qty * avg_p
                cur_p     = get_current_price(sym)
                cur_v     = qty * cur_p
                pnl_usd   = cur_v - inv
                pnl_pct   = (pnl_usd / inv * 100) if inv > 0 else 0
                total_inv += inv; total_cur += cur_v
                rows.append({
                    "الأصل":          sym,
                    "النوع":          row.get("AssetType","—"),
                    "الكمية":         f"{qty:.4f}",
                    "متوسط شراء":     f"${avg_p:,.4f}",
                    "السعر الحالي":   f"${cur_p:,.4f}",
                    "التكلفة":        f"${inv:,.2f}",
                    "القيمة الحالية": f"${cur_v:,.2f}",
                    "ر/خ ($)":        f"{'🟢' if pnl_usd>=0 else '🔴'} ${pnl_usd:,.2f}",
                    "ر/خ (%)":        f"{pnl_pct:+.2f}%",
                    "أُضيف":          row.get("AddedAt","—"),
                })

        total_pnl = total_cur - total_inv
        pnl_pct   = (total_pnl / total_inv * 100) if total_inv > 0 else 0
        k1, k2, k3 = st.columns(3)
        k1.metric("إجمالي الاستثمار",   f"${total_inv:,.2f}")
        k2.metric("القيمة الحالية",      f"${total_cur:,.2f}")
        k3.metric("صافي الربح/الخسارة", f"${total_pnl:,.2f}", f"{pnl_pct:+.2f}%")
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        d1, d2 = st.columns([3,1])
        del_sym = d1.selectbox("اختر الأصل للحذف", df_port["Symbol"].tolist(), key="del")
        if d2.button("🗑️ حذف"):
            remove_from_portfolio(del_sym)
            st.rerun()
        if st.button("⚠️ مسح المحفظة كاملاً", type="secondary"):
            clear_portfolio(); st.rerun()
    else:
        st.info("محفظتك فارغة. أضف صفقتك الأولى أعلاه.")

# ── Tab 6 : مستشار AI ─────────────────────────────────
with t6:
    st.markdown("### 🤖 المستشار المالي بالذكاء الاصطناعي")
    st.caption("يستخدم Claude AI — أضف ANTHROPIC_API_KEY في Secrets لتفعيله.")

    if results and st.button("✨ حلّل نتائج المسح كاملاً", use_container_width=True):
        lines = [
            f"- {r['symbol']} ({r['type']}): {r['signal']}, "
            f"RSI={r['rsi']:.1f}, Price={r['price']:.4f}, "
            f"أسباب: {'; '.join(r['reasons'])}"
            for r in results
        ]
        prompt = (
            "أنت محلل مالي خبير. نتائج مسح السوق:\n\n"
            + "\n".join(lines)
            + "\n\nقدّم تحليلاً يتضمن:\n"
              "1. أبرز فرص الشراء القوية مع أسبابها\n"
              "2. أصول يجب تجنبها الآن\n"
              "3. توصية تخصيص محفظة مقترحة\n"
              "4. ملاحظات مهمة على وضع السوق\n"
              "اجعل الرد منظماً ومختصراً. التنبيه: هذا للأغراض التعليمية فقط."
        )
        with st.spinner("Claude يحلل السوق..."):
            reply = call_claude(
                prompt,
                system="أنت محلل مالي متخصص. ردودك بالعربية دائماً.",
                max_tokens=1000,
            )
        st.markdown(reply)
        st.divider()

    for msg in st.session_state.ai_chat:
        with st.chat_message("user" if msg["role"] == "user" else "assistant"):
            st.write(msg["content"])

    if prompt_in := st.chat_input("اسأل عن أي أصل أو استراتيجية..."):
        st.session_state.ai_chat.append({"role": "user", "content": prompt_in})
        with st.chat_message("user"):
            st.write(prompt_in)

        ctx = ""
        if results:
            ctx = "نتائج المسح الحالية:\n" + "\n".join(
                f"- {r['symbol']}: {r['signal']}, RSI={r['rsi']:.1f}, Price={r['price']:.4f}"
                for r in results[:25]
            ) + "\n\n"

        with st.chat_message("assistant"):
            with st.spinner("يفكر..."):
                reply = call_claude(
                    ctx + prompt_in,
                    system=(
                        "أنت مستشار مالي ذكي متخصص في الأسهم الأمريكية والإماراتية والأوروبية والـ ETFs. "
                        "تجيب بالعربية دائماً بشكل مختصر وعملي. "
                        "تنبّه أن ردودك تعليمية وليست نصيحة مرخصة."
                    ),
                    max_tokens=700,
                )
            st.write(reply)
        st.session_state.ai_chat.append({"role": "assistant", "content": reply})
