# streamlit_app.py — نظام إشارات التداول ومحفظة الاستثمار
# شغّله بـ: streamlit run streamlit_app.py

import streamlit as st
import pandas as pd
import numpy as np
import requests
import feedparser
import yfinance as yf
import ccxt
import os
import json
import anthropic
from datetime import datetime, timedelta, timezone
from plotly.subplots import make_subplots
import plotly.graph_objects as go

# ══════════════════════════════════════════════════════
#  إعدادات الصفحة
# ══════════════════════════════════════════════════════
st.set_page_config(page_title="🤖 إشارات التداول والمحفظة", page_icon="📈",
                   layout="wide", initial_sidebar_state="expanded")

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
div[data-testid="stButton"]>button{background:linear-gradient(135deg,#1d4ed8,#0ea5e9);color:white;border:none;border-radius:10px;padding:12px 28px;font-size:1.1rem;font-family:'Tajawal',sans-serif;font-weight:700;width:100%;}
h1,h2,h3{font-family:'Tajawal',sans-serif!important;color:#e2e8f0!important;}
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════
#  ملف تتبع المحفظة (الاحتفاظ بالبيانات)
# ══════════════════════════════════════════════════════
PORTFOLIO_FILE = "portfolio.csv"

def load_portfolio():
    if os.path.exists(PORTFOLIO_FILE):
        return pd.read_csv(PORTFOLIO_FILE)
    return pd.DataFrame(columns=["Symbol", "Quantity", "AvgPrice"])

def add_to_portfolio(symbol, qty, price):
    df = load_portfolio()
    if symbol in df["Symbol"].values:
        idx = df.index[df["Symbol"] == symbol].tolist()[0]
        old_qty = df.at[idx, "Quantity"]
        old_price = df.at[idx, "AvgPrice"]
        new_qty = old_qty + qty
        new_price = ((old_qty * old_price) + (qty * price)) / new_qty
        df.at[idx, "Quantity"] = new_qty
        df.at[idx, "AvgPrice"] = new_price
    else:
        new_row = pd.DataFrame([{"Symbol": symbol, "Quantity": qty, "AvgPrice": price}])
        df = pd.concat([df, new_row], ignore_index=True)
    df.to_csv(PORTFOLIO_FILE, index=False)

def clear_portfolio():
    if os.path.exists(PORTFOLIO_FILE):
        os.remove(PORTFOLIO_FILE)

# ══════════════════════════════════════════════════════
#  الإعدادات الافتراضية للأسهم والعملات
# ══════════════════════════════════════════════════════
US_STOCKS = ["AAPL","MSFT","NVDA","TSLA","AMZN","GOOGL","META","NFLX","AMD","INTC"]
UAE_STOCKS = [
    "IFA.AE", "SALAMA.AE", "SALAMBAH.AE", "DSI.AE", "DIC.AE", "EIBANK.AE",
    "DEYAAR.AE", "WATANI.AE", "TAALEEM.AE", "ARMX.AE", "ERC.AE", "DEWA.AE",
    "TABREED.AE", "TAKAFULE.AE", "AMLAK.AE", "MAZAYA.AE", "UPP.AE",
    "ALFIRDOU.AE", "SUKOONTA.AE", "NIND.AE", "NGI.AE", "NAHO.AE", "ITHMR.AE",
    "GFH.AE", "EMAARDEV.AE", "DNIR.AE", "AGLTY.AE", "AIRARABI.AE",
    "EKTTITAB.AE", "EMAAR.AE", "MASQ.AE", "DU.AE", "ALRAMZ.AE", "PARKIN.AE",
    "NIH.AE", "AJMANBAN.AE", "AMANAT.AE", "ALANSARI.AE", "SHUAA.AE",
    "GULFNAV.AE", "SALIK.AE", "TECOM.AE", "TALABAT.AE", "EMPOWER.AE",
    "DTC.AE", "DFM.AE", "NCC.AE", "SPINNEYS.AE", "EMIRATESNBD.AE",
    "BHMCAPIT.AE", "CBD.AE", "DIB.AE", "ALDAR.AE"
]
DEFAULT_STOCKS = US_STOCKS + UAE_STOCKS

extracted_cryptos = [
    "BTC", "ETH", "BNB", "XRP", "SOL", "TRX", "DOGE", "ADA", "BCH", "XLM", "WBTC", "WBETH", "LINK", 
    "HBAR", "USD1", "LTC", "AVAX", "TAO", "ZEC", "SUI", "SHIB", "UNI", "TON", "WLFI", "PAXG", "DOT", 
    "TRUMP", "AAVE", "SKY", "ASTER", "NEAR", "BFUSD", "WLD", "PEPE", "RLUSD", "ETC", "ICP", "ONDO", 
    "ZRO", "PUMP", "FIL", "POL", "U", "MORPHO", "BNSOL", "RENDER", "QNT", "ATOM", "ARB", "APT", "ENA", 
    "ALGO", "NIGHT", "VIRTUAL", "FET", "DEXE", "JUP", "VET", "ENS", "NEXO", "BONK", "JST", "ETHFI", 
    "OP", "CAKE", "KITE", "PENGU", "STX", "DASH", "XTZ", "SEI", "DCR", "CRV", "CHZ", "PENDLE", "SUN", 
    "GNO", "TIA", "RAY", "BTTC", "CFX", "KAIA", "INJ", "IMX", "AXS", "LDO", "JTO", "FLOKI", "SYRUP", 
    "JASMY", "NEO", "GRT", "Z2", "IOTA", "SAND", "XPL", "PYTH", "STRK", "TWT", "LUNC", "STG", "COMP", 
    "WIF", "ZK", "WAL", "FF", "CVX", "RUNE", "MANA", "THETA", "BAT", "SFP", "SENT", "GALA", "OG", 
    "KMNO", "KAITO", "1INCH", "XEC", "BARD", "BANANAS31", "A", "GLM", "EIGEN", "S", "AR", "EGLD", 
    "COW", "BERA", "LPT", "RSR", "GAS", "SNX", "FTT", "AMP", "ROSE", "ZEN", "FORM", "AWE", "CFG", 
    "QTUM", "YFI", "W", "1000CHEEMS"
]
DEFAULT_CRYPTO = [f"{c}/USDT" for c in extracted_cryptos]

RSI_OVERSOLD=30; RSI_OVERBOUGHT=70; RSI_PERIOD=14
MACD_FAST=12; MACD_SLOW=26; MACD_SIGNAL_P=9
BB_PERIOD=20; BB_STD=2.0
MA_SHORT=20;  MA_LONG=50

SIGNAL_EMOJI={"STRONG_BUY":"🚀 شراء قوي","BUY":"🟢 شراء","HOLD":"🟡 انتظار","SELL":"🔴 بيع","STRONG_SELL":"💥 بيع قوي"}
SIGNAL_COLOR={"STRONG_BUY":"#00ff88","BUY":"#22c55e","HOLD":"#eab308","SELL":"#f97316","STRONG_SELL":"#ef4444"}

# ══════════════════════════════════════════════════════
#  جلب البيانات السريعة والتاريخية
# ══════════════════════════════════════════════════════
def fetch_stock(symbol):
    try:
        df = yf.Ticker(symbol).history(period="6mo", interval="1d")
        if df.empty: return None
        return df[["Open","High","Low","Close","Volume"]].dropna()
    except: return None

def fetch_crypto(symbol):
    try:
        yf_sym = symbol.replace("/USDT", "-USD")
        df = yf.Ticker(yf_sym).history(period="6mo", interval="1d")
        if not df.empty:
            return df[["Open","High","Low","Close","Volume"]].dropna()
    except: pass
    try:
        ex = ccxt.kucoin({"enableRateLimit": True})
        ohlcv = ex.fetch_ohlcv(symbol, timeframe="1d", limit=200)
        if not ohlcv: return None
        df = pd.DataFrame(ohlcv, columns=["ts","Open","High","Low","Close","Volume"])
        df["ts"] = pd.to_datetime(df["ts"], unit="ms")
        return df.set_index("ts").dropna()
    except: return None

def get_current_price(symbol):
    """جلب السعر الحالي بسرعة لصفحة المحفظة"""
    try:
        if "/USDT" in symbol:
            yf_sym = symbol.replace("/USDT", "-USD")
            return float(yf.Ticker(yf_sym).history(period="1d")['Close'].iloc[-1])
        else:
            return float(yf.Ticker(symbol).history(period="1d")['Close'].iloc[-1])
    except:
        return 0.0

# ══════════════════════════════════════════════════════
#  المؤشرات والأخبار (كما هي سابقاً)
# ══════════════════════════════════════════════════════
def calc_indicators(df):
    d = df.copy()
    delta=d["Close"].diff(); gain=delta.clip(lower=0); loss=-delta.clip(upper=0)
    ag=gain.ewm(com=RSI_PERIOD-1,adjust=False).mean()
    al=loss.ewm(com=RSI_PERIOD-1,adjust=False).mean()
    d["RSI"]=100-(100/(1+ag/al.replace(0,np.nan)))
    ef=d["Close"].ewm(span=MACD_FAST,adjust=False).mean()
    es=d["Close"].ewm(span=MACD_SLOW,adjust=False).mean()
    d["MACD"]=ef-es
    d["MACD_Sig"]=d["MACD"].ewm(span=MACD_SIGNAL_P,adjust=False).mean()
    d["MACD_Hist"]=d["MACD"]-d["MACD_Sig"]
    sma=d["Close"].rolling(BB_PERIOD).mean()
    std=d["Close"].rolling(BB_PERIOD).std()
    d["BB_U"]=sma+BB_STD*std; d["BB_L"]=sma-BB_STD*std; d["BB_M"]=sma
    d[f"MA{MA_SHORT}"]=d["Close"].rolling(MA_SHORT).mean()
    d[f"MA{MA_LONG}"]=d["Close"].rolling(MA_LONG).mean()
    d["Vol_MA"]=d["Volume"].rolling(20).mean()
    d["Vol_R"]=d["Volume"]/d["Vol_MA"]
    return d

def get_signal(df):
    last=df.iloc[-1]; prev=df.iloc[-2]
    buy=0; sell=0; reasons=[]
    c=float(last["Close"])
    
    lowest_6m = df["Low"].min()
    dist_from_low = (c - lowest_6m) / lowest_6m
    if dist_from_low <= 0.05:
        buy+=1; reasons.append(f"🔥 السعر قريب جداً من قاع 6 أشهر ({lowest_6m:.2f})")

    rsi=float(last["RSI"])
    if rsi<RSI_OVERSOLD: buy+=1; reasons.append(f"RSI={rsi:.1f} تشبع بيعي")
    elif rsi>RSI_OVERBOUGHT: sell+=1; reasons.append(f"RSI={rsi:.1f} تشبع شرائي")
    
    h=float(last["MACD_Hist"]); hp=float(prev["MACD_Hist"])
    if hp<0<h: buy+=1; reasons.append("MACD عبر الصفر صعوداً")
    elif hp>0>h: sell+=1; reasons.append("MACD عبر الصفر هبوطاً")
    
    if c<float(last["BB_L"]): buy+=1; reasons.append("السعر تحت مسار Bollinger السفلي")
    elif c>float(last["BB_U"]): sell+=1; reasons.append("السعر فوق مسار Bollinger العلوي")
    
    ms=float(last[f"MA{MA_SHORT}"]); ml=float(last[f"MA{MA_LONG}"])
    msp=float(prev[f"MA{MA_SHORT}"]); mlp=float(prev[f"MA{MA_LONG}"])
    if msp<mlp and ms>ml: buy+=1; reasons.append(f"تقاطع ذهبي MA{MA_SHORT}/MA{MA_LONG}")
    elif msp>mlp and ms<ml: sell+=1; reasons.append(f"تقاطع الموت MA{MA_SHORT}/MA{MA_LONG}")
    
    vr=float(last["Vol_R"])
    if vr>1.5:
        if buy>sell: buy+=1; reasons.append(f"حجم تداول مرتفع ({vr:.1f}x) يؤكد الشراء")
        elif sell>buy: sell+=1; reasons.append(f"حجم تداول مرتفع ({vr:.1f}x) يؤكد البيع")
        
    net=buy-sell
    if net>=3: sig="STRONG_BUY"
    elif net>=2: sig="BUY"
    elif net<=-3: sig="STRONG_SELL"
    elif net<=-2: sig="SELL"
    else: sig="HOLD"
    return sig, reasons, rsi, float(last["MACD_Hist"]), vr, c

POS_WORDS={"surge","soar","rally","jump","boom","bullish","breakout","record","growth","profit","beat","upgrade","buy","strong","gain","rise","approved","partnership"}
NEG_WORDS={"crash","plunge","drop","fall","decline","bearish","loss","miss","downgrade","sell","weak","tumble","slump","recession","ban","fraud","bankruptcy"}
STRONG_POS={"surge","soar","boom","record","breakout","approved","all-time high"}
STRONG_NEG={"crash","ban","fraud","bankruptcy","sec charges","rug pull"}

STOCK_KW={"AAPL":["Apple","AAPL"],"MSFT":["Microsoft","MSFT"],"NVDA":["Nvidia","NVDA"],"TSLA":["Tesla","TSLA"],
          "EMAAR.AE":["Emaar","إعمار"],"DIB.AE":["Dubai Islamic Bank","بنك دبي الإسلامي"],
          "EMIRATESNBD.AE":["Emirates NBD","الإمارات دبي الوطني"],"ALDAR.AE":["Aldar","الدار العقارية"],
          "AIRARABI.AE":["Air Arabia","طيران العربية"],"DEWA.AE":["DEWA","ديوا","كهرباء دبي"],
          "SALIK.AE":["Salik","سالك"],"TALABAT.AE":["Talabat","طلبات"]}
CRYPTO_KW={"BTC/USDT":["Bitcoin","BTC"],"ETH/USDT":["Ethereum","ETH"],"SOL/USDT":["Solana","SOL"],"ARB/USDT":["Arbitrum","ARB"],"SKY/USDT":["Sky","SKY"],"AMP/USDT":["Amp","AMP"]}

def analyze_sentiment(text):
    t=text.lower(); score=0.0
    for w in STRONG_POS:
        if w in t: score+=0.4
    for w in STRONG_NEG:
        if w in t: score-=0.4
    for w in POS_WORDS-STRONG_POS:
        if w in t: score+=0.15
    for w in NEG_WORDS-STRONG_NEG:
        if w in t: score-=0.15
    return max(-1.0,min(1.0,score))

def sentiment_label(s):
    if s>=0.4: return "🟢 إيجابي قوي"
    if s>=0.15: return "🟡 إيجابي"
    if s<=-0.4: return "🔴 سلبي قوي"
    if s<=-0.15: return "🟠 سلبي"
    return "⚪ محا محايد"

def fetch_news(symbol, asset_type, newsapi_key="", cryptopanic_key=""):
    articles=[]; kws=[]
    if asset_type=="stock": kws=STOCK_KW.get(symbol,[symbol.replace(".AE","")])
    else: kws=CRYPTO_KW.get(symbol,[symbol.replace("/USDT","")])

    try:
        q=kws[0].replace(" ","+")
        feed=feedparser.parse(f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={q}&region=US&lang=en-US")
        cutoff=datetime.now(timezone.utc)-timedelta(hours=48)
        for e in feed.entries[:5]:
            try: pub=datetime(*e.published_parsed[:6],tzinfo=timezone.utc)
            except: pub=datetime.now(timezone.utc)
            if pub<cutoff: continue
            t=e.get("title",""); s=analyze_sentiment(t+" "+e.get("summary",""))
            articles.append({"source":"Yahoo","title":t,"sentiment":s})
    except: pass

    if not articles: return {"label":"⚪ لا أخبار","signal":"HOLD","score":0.0,"articles":[]}

    scores=[a["sentiment"] for a in articles]
    w=list(range(len(scores),0,-1))
    avg=sum(s*wt for s,wt in zip(scores,w))/sum(w)
    pos=sum(1 for s in scores if s>0.1); neg=sum(1 for s in scores if s<-0.1)
    nsig="BUY" if avg>=0.25 and pos>neg else "SELL" if avg<=-0.25 and neg>pos else "HOLD"
    return {"label":sentiment_label(avg),"signal":nsig,"score":round(avg,3),"articles":articles[:8]}

def merge_signals(tech, news_sig, news_score):
    up={"BUY":"STRONG_BUY","SELL":"STRONG_SELL","HOLD":"BUY"}
    dn={"STRONG_BUY":"BUY","STRONG_SELL":"SELL","BUY":"HOLD","SELL":"HOLD"}
    bull=news_sig=="BUY" and news_score>0.2
    bear=news_sig=="SELL" and news_score<-0.2
    if tech in ("BUY","STRONG_BUY") and bull: return up.get(tech,tech)
    if tech in ("SELL","STRONG_SELL") and bear: return up.get(tech,tech)
    if tech in ("BUY","STRONG_BUY") and bear: return dn.get(tech,"HOLD")
    if tech in ("SELL","STRONG_SELL") and bull: return dn.get(tech,"HOLD")
    if tech=="HOLD" and bull: return "BUY"
    if tech=="HOLD" and bear: return "SELL"
    return tech

# ══════════════════════════════════════════════════════
#  الرسم البياني
# ══════════════════════════════════════════════════════
def draw_chart(df, symbol):
    d=df.tail(90)
    fig=make_subplots(rows=3,cols=1,shared_xaxes=True,vertical_spacing=0.04,
                      row_heights=[0.55,0.25,0.20],
                      subplot_titles=["السعر + Bollinger + MA","RSI","MACD"])
    fig.add_trace(go.Candlestick(x=d.index,open=d["Open"],high=d["High"],
        low=d["Low"],close=d["Close"],
        increasing_line_color="#22c55e",decreasing_line_color="#ef4444",name="السعر"),row=1,col=1)
    fig.add_trace(go.Scatter(x=d.index,y=d["BB_U"],line=dict(color="#3b82f6",width=1,dash="dot"),name="BB U"),row=1,col=1)
    fig.add_trace(go.Scatter(x=d.index,y=d["BB_L"],line=dict(color="#3b82f6",width=1,dash="dot"),
        fill="tonexty",fillcolor="rgba(59,130,246,0.07)",name="BB L"),row=1,col=1)
    fig.add_trace(go.Scatter(x=d.index,y=d["BB_M"],line=dict(color="#475569",width=1),name="BB Mid"),row=1,col=1)
    fig.add_trace(go.Scatter(x=d.index,y=d[f"MA{MA_SHORT}"],line=dict(color="#f59e0b",width=1.5),name=f"MA{MA_SHORT}"),row=1,col=1)
    fig.add_trace(go.Scatter(x=d.index,y=d[f"MA{MA_LONG}"],line=dict(color="#a855f7",width=1.5),name=f"MA{MA_LONG}"),row=1,col=1)
    fig.add_trace(go.Scatter(x=d.index,y=d["RSI"],line=dict(color="#0ea5e9",width=2),name="RSI"),row=2,col=1)
    fig.add_hline(y=70,line_dash="dash",line_color="#ef4444",line_width=1,row=2,col=1)
    fig.add_hline(y=30,line_dash="dash",line_color="#22c55e",line_width=1,row=2,col=1)
    colors=["#22c55e" if v>=0 else "#ef4444" for v in d["MACD_Hist"]]
    fig.add_trace(go.Bar(x=d.index,y=d["MACD_Hist"],marker_color=colors,name="Hist",opacity=0.7),row=3,col=1)
    fig.add_trace(go.Scatter(x=d.index,y=d["MACD"],line=dict(color="#0ea5e9",width=1.5),name="MACD"),row=3,col=1)
    fig.add_trace(go.Scatter(x=d.index,y=d["MACD_Sig"],line=dict(color="#f59e0b",width=1.5),name="Signal"),row=3,col=1)
    fig.update_layout(height=600,paper_bgcolor="#0a0e1a",plot_bgcolor="#0a0e1a",
        font=dict(color="#94a3b8",family="IBM Plex Mono"),
        legend=dict(orientation="h",y=1.02,bgcolor="rgba(0,0,0,0)"),
        xaxis_rangeslider_visible=False,margin=dict(l=10,r=10,t=30,b=10))
    for i in range(1,4):
        fig.update_xaxes(gridcolor="#1e2d4a",row=i,col=1)
        fig.update_yaxes(gridcolor="#1e2d4a",row=i,col=1)
    return fig

# ══════════════════════════════════════════════════════
#  🤖 وظائف المستشار الذكي (Claude AI)
# ══════════════════════════════════════════════════════
def build_ai_client(api_key):
    """بناء عميل Claude"""
    try:
        return anthropic.Anthropic(api_key=api_key)
    except Exception as e:
        return None

def ai_top_opportunities(client, results):
    """تحليل أقوى فرص السوق من نتائج المسح"""
    if not results:
        return "⚠️ لا توجد نتائج مسح. ابدأ مسح السوق أولاً من القائمة الجانبية."
    
    # تجهيز ملخص النتائج للـ AI
    strong_signals = [r for r in results if r["signal"] in ("STRONG_BUY", "BUY")]
    summary = []
    for r in results[:30]:  # نحد لـ 30 لتجنب تجاوز التوكنز
        summary.append({
            "symbol": r["symbol"],
            "type": r["type"],
            "signal": r["signal"],
            "rsi": round(r["rsi"], 1),
            "macd_hist": round(r["macd_hist"], 4),
            "vol_ratio": round(r["vol_ratio"], 2),
            "price": round(r["price"], 4),
            "news": r["news_label"],
            "reasons": r["reasons"][:3]
        })
    
    prompt = f"""أنت مستشار مالي خبير متخصص بالأسواق المالية. بناءً على نتائج المسح التقني التالية، قدّم تحليلاً احترافياً.

نتائج المسح:
{json.dumps(summary, ensure_ascii=False, indent=2)}

المطلوب منك:
1. **أقوى 5 فرص استثمارية** الآن مع تبرير كل فرصة (RSI, MACD, حجم التداول، الأخبار)
2. **تصنيف المخاطر** لكل فرصة (منخفض / متوسط / مرتفع)
3. **المدة الزمنية المقترحة** للاحتفاظ (يوم / أسبوع / شهر)
4. **نقطة الدخول المثلى** والهدف السعري التقديري
5. **تحذيرات** مهمة يجب أخذها بعين الاعتبار

اكتب بالعربية بأسلوب واضح ومنظم مع استخدام الرموز التعبيرية المناسبة."""

    try:
        with client.messages.stream(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}]
        ) as stream:
            return stream.get_final_text()
    except Exception as e:
        return f"❌ خطأ في الاتصال بالذكاء الاصطناعي: {str(e)}"

def ai_budget_allocation(client, budget, risk_profile, results):
    """توصية ذكية لتوزيع الميزانية"""
    strong = [r for r in results if r["signal"] in ("STRONG_BUY", "BUY")][:10]
    
    signals_text = ""
    for r in strong:
        signals_text += f"- {r['symbol']} ({r['type']}): إشارة {r['signal']}, RSI={r['rsi']:.1f}, سعر={r['price']:.4f}\n"
    
    if not signals_text:
        signals_text = "لا توجد إشارات شراء حالية - السوق في وضع انتظار"
    
    prompt = f"""أنت مستشار مالي خبير. العميل لديه ميزانية استثمارية ويريد توزيعها بذكاء.

**الميزانية المتاحة:** ${budget:,.2f}
**ملف المخاطر:** {risk_profile}

**الإشارات الإيجابية الحالية في السوق:**
{signals_text}

المطلوب: خطة توزيع الميزانية الكاملة تشمل:

1. **التوزيع الاستراتيجي** (مثال: 40% أسهم آمنة، 30% عملات، 20% فرص نمو، 10% احتياطي)
2. **المبالغ المحددة بالدولار** لكل فئة
3. **الأصول المقترحة** من القائمة أعلاه مع المبلغ المخصص لكل أصل
4. **استراتيجية الدخول**: كل مرة أم على دفعات؟
5. **نقطة وقف الخسارة** الموصى بها (Stop Loss %)
6. **هدف الربح** المتوقع خلال 3-6 أشهر

اكتب بالعربية مع جداول واضحة وأرقام دقيقة."""

    try:
        with client.messages.stream(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}]
        ) as stream:
            return stream.get_final_text()
    except Exception as e:
        return f"❌ خطأ: {str(e)}"

def ai_doubling_analysis(client, symbol, amount, current_price, results):
    """تحليل إمكانية مضاعفة المبلغ"""
    asset_data = next((r for r in results if r["symbol"] == symbol), None)
    
    if asset_data:
        context = f"""بيانات تقنية لـ {symbol}:
- الإشارة الحالية: {asset_data['signal']}
- RSI: {asset_data['rsi']:.1f}
- حجم التداول: {asset_data['vol_ratio']:.2f}x المعدل
- الأسباب التقنية: {', '.join(asset_data['reasons'])}
- أخبار: {asset_data['news_label']}"""
    else:
        context = f"الأصل: {symbol} - السعر الحالي: ${current_price}"
    
    prompt = f"""أنت محلل مالي خبير. قيّم إمكانية مضاعفة مبلغ استثماري.

**الأصل:** {symbol}
**المبلغ المستثمر:** ${amount:,.2f}
**السعر الحالي:** ${current_price}

{context}

قدّم تحليلاً شاملاً يتضمن:

1. **هل التضعيف ممكن؟** (نعم/ربما/مستبعد) مع التبرير
2. **الإطار الزمني الواقعي** للوصول لـ 2x (أشهر/سنوات)
3. **السيناريوهات الثلاثة:**
   - 🟢 سيناريو متفائل: السعر المستهدف والمدة
   - 🟡 سيناريو محايد: العائد المتوقع
   - 🔴 سيناريو متشائم: أقصى خسارة محتملة
4. **مقارنة بدائل أسرع** لتحقيق نفس الهدف
5. **نصيحة عملية**: هل تنصح بالاستثمار في هذا الأصل تحديداً أم لا؟
6. **استراتيجية التراكم** (DCA) إذا كانت أفضل من الدخول دفعة واحدة

اكتب بالعربية بصدق تام مع التحذيرات اللازمة."""

    try:
        with client.messages.stream(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}]
        ) as stream:
            return stream.get_final_text()
    except Exception as e:
        return f"❌ خطأ: {str(e)}"

def ai_portfolio_advice(client, portfolio_data, results):
    """تحليل ذكي لأداء المحفظة الحالية"""
    prompt = f"""أنت مستشار مالي خبير. حلّل أداء المحفظة الاستثمارية وقدّم توصيات.

**بيانات المحفظة:**
{json.dumps(portfolio_data, ensure_ascii=False, indent=2)}

**ملخص السوق الحالي:**
عدد الإشارات الإيجابية: {sum(1 for r in results if r['signal'] in ('STRONG_BUY','BUY'))}
عدد إشارات البيع: {sum(1 for r in results if r['signal'] in ('STRONG_SELL','SELL'))}

قدّم:
1. **تقييم المحفظة الحالية**: هل التوزيع جيد؟
2. **الأصول الرابحة**: هل تحتفظ بها أم تجني الأرباح؟
3. **الأصول الخاسرة**: هل تقطع الخسائر أم تتراكم؟
4. **فرص إعادة التوازن**: ما الذي يجب تعديله؟
5. **التوصية الفورية**: أهم 3 إجراءات يجب اتخاذها الآن

اكتب بالعربية بوضوح تام."""

    try:
        with client.messages.stream(
            model="claude-sonnet-4-20250514",
            max_tokens=1200,
            messages=[{"role": "user", "content": prompt}]
        ) as stream:
            return stream.get_final_text()
    except Exception as e:
        return f"❌ خطأ: {str(e)}"

# ══════════════════════════════════════════════════════
#  UI الرئيسي
# ══════════════════════════════════════════════════════
st.markdown("# 🤖 نظام إشارات التداول الذكي")
st.markdown("<p style='color:#64748b;margin-top:-14px'>أسهم · عملات رقمية · محفظة · تحليل أخبار</p>",unsafe_allow_html=True)
st.divider()

with st.sidebar:
    st.markdown("### ⚙️ الإعدادات والمراقبة")
    
    st.markdown("---")
    st.markdown("### 🤖 مستشار الذكاء الاصطناعي")
    anthropic_key = st.text_input("🔑 Anthropic API Key", type="password",
                                   placeholder="sk-ant-...",
                                   help="أدخل مفتاح Anthropic API لتفعيل المستشار الذكي")
    if anthropic_key:
        st.success("✅ مفتاح API مفعّل")
    else:
        st.info("💡 أدخل مفتاح API لتفعيل التبويب الخامس")
    st.markdown("---")
    
    asset_type=st.radio("نوع الأصل",["📈 أسهم","₿ عملات رقمية","🌐 الكل"],index=2)
    
    st.markdown("**الأسهم (تشمل أمريكا والإمارات)**")
    # الخيارات الافتراضية للأسهم الإماراتية هنا 👇
    sel_stocks=st.multiselect("أسهم", DEFAULT_STOCKS, 
                              default=["EMAAR.AE", "SALIK.AE", "DEWA.AE", "DIB.AE"], 
                              label_visibility="collapsed")
    
    st.markdown("**العملات الرقمية**")
    # الخيارات الافتراضية للعملات التي طلبتها هنا 👇
    sel_crypto=st.multiselect("كريبتو", DEFAULT_CRYPTO, 
                              default=["SOL/USDT", "ARB/USDT", "SKY/USDT", "AMP/USDT"], 
                              label_visibility="collapsed")
    
    st.markdown("---")
    run_btn=st.button("🔍 ابدأ مسح السوق الآن",use_container_width=True)

if "results" not in st.session_state:
    st.session_state.results=[]
    st.session_state.raw_data={}
    st.session_state.last_scan=None

if run_btn:
    results=[]; raw={}
    scan_s = sel_stocks if "أسهم" in asset_type or "الكل" in asset_type else []
    scan_c = sel_crypto if "عملات" in asset_type or "الكل" in asset_type else []
    total=len(scan_s)+len(scan_c); step=0
    prog=st.progress(0,text="جاري المسح...")

    for sym in scan_s:
        prog.progress(max(step/max(total,1),0.01),text=f"📈 {sym}...")
        df=fetch_stock(sym)
        if df is not None and len(df) >= 50:
            df_i=calc_indicators(df)
            raw[sym]=df_i
            news=fetch_news(sym,"stock")
            tech_sig,reasons,rsi,mh,vr,price=get_signal(df_i)
            final=merge_signals(tech_sig,news["signal"],news["score"])
            results.append({"symbol":sym,"type":"stock","signal":final,"tech":tech_sig,
                "reasons":reasons,"rsi":rsi,"macd_hist":mh,"vol_ratio":vr,"price":price,
                "news_label":news["label"],"news_signal":news["signal"],"news_score":news["score"],
                "articles":[a["title"] for a in news["articles"][:4]]})
        step+=1

    for sym in scan_c:
        prog.progress(max(step/max(total,1),0.01),text=f"₿ {sym}...")
        df=fetch_crypto(sym)
        if df is not None and len(df) >= 50:
            df_i=calc_indicators(df)
            raw[sym]=df_i
            news=fetch_news(sym,"crypto")
            tech_sig,reasons,rsi,mh,vr,price=get_signal(df_i)
            final=merge_signals(tech_sig,news["signal"],news["score"])
            results.append({"symbol":sym,"type":"crypto","signal":final,"tech":tech_sig,
                "reasons":reasons,"rsi":rsi,"macd_hist":mh,"vol_ratio":vr,"price":price,
                "news_label":news["label"],"news_signal":news["signal"],"news_score":news["score"],
                "articles":[a["title"] for a in news["articles"][:4]]})
        step+=1

    prog.empty()
    st.session_state.results=results
    st.session_state.raw_data=raw
    st.session_state.last_scan=datetime.now().strftime("%H:%M:%S")
    st.rerun()

results=st.session_state.results
if not results and not os.path.exists(PORTFOLIO_FILE):
    st.info("👈 اضغط على 'ابدأ مسح السوق الآن' من القائمة الجانبية للبدء، أو اذهب لتبويب 'محفظتي' لإضافة صفقاتك.")

st.markdown("<br>",unsafe_allow_html=True)

# ══════════════════════════════════════════════════════
#  التبويبات الرئيسية
# ══════════════════════════════════════════════════════
t1, t2, t3, t4, t5 = st.tabs(["📋 إشارات السوق", "📊 الرسم البياني", "📰 الأخبار", "💼 محفظتي", "🤖 المستشار الذكي"])

with t1:
    if results:
        order={"STRONG_BUY":0,"BUY":1,"HOLD":2,"SELL":3,"STRONG_SELL":4}
        display=sorted(results, key=lambda x:order.get(x["signal"],2))
        for r in display:
            c=SIGNAL_COLOR.get(r["signal"],"#64748b")
            lbl=SIGNAL_EMOJI.get(r["signal"],r["signal"])
            icon="📈" if r["type"]=="stock" else "₿"
            rs="".join(f"<div style='font-size:.83rem;color:#64748b;margin-top:3px'>• {x}</div>" for x in r["reasons"])
            st.markdown(f"""<div class='sig-card sig-{r["signal"]}'>
              <div style='display:flex;justify-content:space-between;align-items:center'>
                <span style='font-size:1.1rem;font-weight:900;color:#e2e8f0'>{icon} {r["symbol"]}</span>
                <span style='font-size:1.3rem;font-weight:900;color:{c}'>{lbl}</span>
              </div>
              <div style='font-size:.9rem;color:#94a3b8;font-family:IBM Plex Mono,monospace;margin-top:4px'>
                السعر: {r["price"]:,.4f} &nbsp;|&nbsp; RSI: {r["rsi"]:.1f}
              </div>
              {rs}
            </div>""",unsafe_allow_html=True)
    else:
        st.write("قم ببدء المسح لرؤية الإشارات.")

with t2:
    if results:
        syms=[r["symbol"] for r in results]
        chosen=st.selectbox("اختر الأصل لعرض رسمه البياني",syms)
        df_c=st.session_state.raw_data.get(chosen)
        if df_c is not None:
            st.plotly_chart(draw_chart(df_c,chosen),use_container_width=True)

with t3:
    if results:
        has=[r for r in results if r.get("articles")]
        for r in has:
            with st.expander(f"{r['symbol']}  —  {r['news_label']}  ({r['news_score']:+.2f})"):
                for a in r["articles"]:
                    st.write(f"• {a}")

# --- التبويب الرابع: المحفظة الاستثمارية ---
with t4:
    st.markdown("### 💼 إدارة المحفظة الاستثمارية")
    st.markdown("سيتم حفظ بيانات صفقاتك محلياً على جهازك ولن تفقدها عند إغلاق التطبيق.")
    
    # نموذج إضافة صفقة جديدة
    with st.form("add_trade_form"):
        st.markdown("**إضافة شراء جديد للمحفظة:**")
        col1, col2, col3 = st.columns(3)
        p_sym = col1.selectbox("الأصل", DEFAULT_STOCKS + DEFAULT_CRYPTO)
        p_qty = col2.number_input("الكمية المشتراة", min_value=0.0001, value=1.0, step=0.1)
        p_price = col3.number_input("متوسط سعر الشراء", min_value=0.0001, value=100.0, step=0.1)
        
        if st.form_submit_button("➕ احفظ الصفقة"):
            add_to_portfolio(p_sym, p_qty, p_price)
            st.success(f"تمت إضافة {p_qty} من {p_sym} لمحفظتك بنجاح!")
            st.rerun()
            
    # عرض المحفظة والأسعار اللحظية
    df_port = load_portfolio()
    if not df_port.empty:
        st.markdown("---")
        st.markdown("### 📊 أداء محفظتك اللحظي")
        
        total_invested = 0.0
        total_current_value = 0.0
        
        # جدول احترافي لعرض البيانات
        st.write("*(جاري جلب الأسعار اللحظية...)*")
        display_data = []
        for index, row in df_port.iterrows():
            sym = row["Symbol"]
            qty = float(row["Quantity"])
            avg_price = float(row["AvgPrice"])
            
            # حسابات القيمة
            invested = qty * avg_price
            current_price = get_current_price(sym)
            current_val = qty * current_price
            
            pnl_usd = current_val - invested
            pnl_pct = (pnl_usd / invested) * 100 if invested > 0 else 0
            
            total_invested += invested
            total_current_value += current_val
            
            display_data.append({
                "الأصل": sym,
                "الكمية": f"{qty:.4f}",
                "متوسط الشراء": f"${avg_price:,.4f}",
                "السعر الحالي": f"${current_price:,.4f}",
                "الاستثمار (تكلفة)": f"${invested:,.2f}",
                "الربح/الخسارة ($)": f"${pnl_usd:,.2f}",
                "الربح/الخسارة (%)": f"{pnl_pct:,.2f}%"
            })
            
        # عرض بطاقات الإجمالي
        total_pnl = total_current_value - total_invested
        total_pnl_pct = (total_pnl / total_invested) * 100 if total_invested > 0 else 0
        
        c1, c2, c3 = st.columns(3)
        c1.metric("إجمالي الاستثمار", f"${total_invested:,.2f}")
        c2.metric("القيمة الحالية للمحفظة", f"${total_current_value:,.2f}")
        c3.metric("صافي الربح/الخسارة", f"${total_pnl:,.2f}", f"{total_pnl_pct:,.2f}%")
        
        # عرض الجدول
        df_display = pd.DataFrame(display_data)
        st.dataframe(df_display, use_container_width=True)
        
        # زر تصفير المحفظة
        if st.button("🗑️ مسح جميع بيانات المحفظة"):
            clear_portfolio()
            st.rerun()
    else:
        st.info("محفظتك فارغة حالياً. استخدم النموذج أعلاه لإضافة صفقاتك.")

# ══════════════════════════════════════════════════════
#  التبويب الخامس: المستشار الذكي
# ══════════════════════════════════════════════════════
with t5:
    st.markdown("## 🤖 المستشار المالي الذكي")
    st.markdown("<p style='color:#64748b'>مدعوم بـ Claude AI · تحليل عميق للفرص والمخاطر</p>", unsafe_allow_html=True)
    
    if not anthropic_key:
        st.warning("⚠️ أدخل مفتاح Anthropic API في القائمة الجانبية لتفعيل هذا التبويب.")
        st.markdown("""
        **ما يقدمه المستشار الذكي:**
        - 🚀 **أقوى الفرص**: يحلل نتائج المسح ويختار أفضل 5 فرص استثمارية
        - 💰 **توزيع الميزانية**: خطة ذكية لتوزيع رأس مالك بناءً على ملف مخاطرك
        - 📈 **تحليل التضعيف**: هل يمكن مضاعفة مبلغك من أصل معين؟
        - 💼 **تحليل المحفظة**: مراجعة ذكية لمحفظتك الحالية مع توصيات فورية
        """)
        st.stop()
    
    ai_client = build_ai_client(anthropic_key)
    if not ai_client:
        st.error("❌ مفتاح API غير صحيح. تحقق منه وأعد المحاولة.")
        st.stop()
    
    results = st.session_state.get("results", [])
    
    # ── القسم 1: أقوى الفرص ──────────────────────────
    st.markdown("---")
    st.markdown("### 🚀 أقوى فرص رأس المال")
    
    col_a, col_b = st.columns([3,1])
    with col_a:
        st.markdown("يحلل نتائج مسح السوق ويختار أفضل الفرص الاستثمارية الحالية مع تبريرات تقنية وإخبارية.")
    with col_b:
        btn_opps = st.button("🔍 اعرض الفرص", use_container_width=True, key="btn_opps")
    
    if btn_opps:
        if not results:
            st.warning("👈 ابدأ مسح السوق أولاً من القائمة الجانبية ثم عد هنا.")
        else:
            with st.spinner("🤖 يحلل Claude البيانات ويختار أفضل الفرص..."):
                analysis = ai_top_opportunities(ai_client, results)
            st.markdown(f"""
            <div style='background:#0f1729;border:1px solid #1e3a5f;border-radius:12px;padding:24px;
                        border-left:4px solid #00ff88;font-family:Tajawal,sans-serif;line-height:1.9'>
            {analysis.replace(chr(10), '<br>')}
            </div>
            """, unsafe_allow_html=True)
    
    # ── القسم 2: توزيع الميزانية ────────────────────
    st.markdown("---")
    st.markdown("### 💰 خطة توزيع الميزانية")
    
    col1, col2 = st.columns(2)
    with col1:
        budget = st.number_input("💵 الميزانية المتاحة ($)", min_value=100.0, value=5000.0, step=100.0, key="budget_input")
    with col2:
        risk_profile = st.selectbox("⚖️ ملف المخاطر", 
                                     ["🟢 محافظ (مخاطر منخفضة)", 
                                      "🟡 متوازن (مخاطر متوسطة)", 
                                      "🔴 مغامر (مخاطر مرتفعة)"],
                                     index=1, key="risk_profile")
    
    btn_budget = st.button("📊 احسب التوزيع المثالي", use_container_width=True, key="btn_budget")
    
    if btn_budget:
        with st.spinner("🤖 Claude يضع خطة التوزيع..."):
            budget_plan = ai_budget_allocation(ai_client, budget, risk_profile, results)
        st.markdown(f"""
        <div style='background:#0f1729;border:1px solid #1e3a5f;border-radius:12px;padding:24px;
                    border-left:4px solid #0ea5e9;font-family:Tajawal,sans-serif;line-height:1.9'>
        {budget_plan.replace(chr(10), '<br>')}
        </div>
        """, unsafe_allow_html=True)
    
    # ── القسم 3: تحليل التضعيف ──────────────────────
    st.markdown("---")
    st.markdown("### 📈 هل أقدر أضاعف مبلغي؟")
    st.markdown("اختر أصلاً وحدد مبلغك لمعرفة إمكانية مضاعفته مع تحليل واقعي.")
    
    col3, col4 = st.columns(2)
    all_symbols = list(set([r["symbol"] for r in results])) if results else DEFAULT_STOCKS[:10] + ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
    
    with col3:
        double_symbol = st.selectbox("🎯 اختر الأصل", all_symbols, key="double_sym")
        double_amount = st.number_input("💵 المبلغ المراد استثماره ($)", min_value=50.0, value=1000.0, step=50.0, key="double_amt")
    with col4:
        # جلب السعر الحالي
        current_p = get_current_price(double_symbol) if double_symbol else 0.0
        st.metric("السعر الحالي", f"${current_p:,.4f}" if current_p > 0 else "غير متاح")
        asset_result = next((r for r in results if r["symbol"] == double_symbol), None)
        if asset_result:
            sig_color = SIGNAL_COLOR.get(asset_result["signal"], "#64748b")
            sig_label = SIGNAL_EMOJI.get(asset_result["signal"], asset_result["signal"])
            st.markdown(f"<div style='margin-top:8px'>الإشارة: <span style='color:{sig_color};font-weight:900'>{sig_label}</span></div>", unsafe_allow_html=True)
    
    btn_double = st.button("🔮 حلل إمكانية التضعيف", use_container_width=True, key="btn_double")
    
    if btn_double:
        if current_p == 0:
            st.warning("⚠️ تعذّر جلب السعر الحالي. جرب مسح السوق أولاً.")
        else:
            with st.spinner(f"🤖 Claude يحلل إمكانية مضاعفة ${double_amount:,.0f} في {double_symbol}..."):
                double_analysis = ai_doubling_analysis(ai_client, double_symbol, double_amount, current_p, results)
            st.markdown(f"""
            <div style='background:#0f1729;border:1px solid #1e3a5f;border-radius:12px;padding:24px;
                        border-left:4px solid #f59e0b;font-family:Tajawal,sans-serif;line-height:1.9'>
            {double_analysis.replace(chr(10), '<br>')}
            </div>
            """, unsafe_allow_html=True)
    
    # ── القسم 4: تحليل المحفظة ──────────────────────
    st.markdown("---")
    st.markdown("### 💼 تحليل محفظتي الحالية")
    
    df_port_ai = load_portfolio()
    if df_port_ai.empty:
        st.info("💡 أضف صفقات في تبويب 'محفظتي' أولاً ثم عد هنا للحصول على تحليل ذكي.")
    else:
        # حساب أداء المحفظة
        portfolio_summary = []
        for _, row in df_port_ai.iterrows():
            sym = row["Symbol"]
            qty = float(row["Quantity"])
            avg_p = float(row["AvgPrice"])
            curr_p = get_current_price(sym)
            invested = qty * avg_p
            current_val = qty * curr_p
            pnl_pct = ((current_val - invested) / invested * 100) if invested > 0 else 0
            portfolio_summary.append({
                "symbol": sym,
                "quantity": qty,
                "avg_buy_price": avg_p,
                "current_price": curr_p,
                "invested": round(invested, 2),
                "current_value": round(current_val, 2),
                "pnl_percent": round(pnl_pct, 2)
            })
        
        total_inv = sum(p["invested"] for p in portfolio_summary)
        total_curr = sum(p["current_value"] for p in portfolio_summary)
        total_pnl_pct = ((total_curr - total_inv) / total_inv * 100) if total_inv > 0 else 0
        
        c1, c2, c3 = st.columns(3)
        c1.metric("إجمالي الاستثمار", f"${total_inv:,.2f}")
        c2.metric("القيمة الحالية", f"${total_curr:,.2f}")
        pnl_delta = f"{total_pnl_pct:+.2f}%"
        c3.metric("صافي الأداء", f"${total_curr - total_inv:,.2f}", pnl_delta)
        
        btn_port_ai = st.button("🤖 اطلب تحليل ذكي للمحفظة", use_container_width=True, key="btn_port_ai")
        
        if btn_port_ai:
            with st.spinner("🤖 Claude يراجع محفظتك ويضع التوصيات..."):
                port_advice = ai_portfolio_advice(ai_client, portfolio_summary, results)
            st.markdown(f"""
            <div style='background:#0f1729;border:1px solid #1e3a5f;border-radius:12px;padding:24px;
                        border-left:4px solid #a855f7;font-family:Tajawal,sans-serif;line-height:1.9'>
            {port_advice.replace(chr(10), '<br>')}
            </div>
            """, unsafe_allow_html=True)
    
    # تنبيه قانوني
    st.markdown("---")
    st.markdown("""
    <div style='background:#1a0a00;border:1px solid #7c2d12;border-radius:8px;padding:12px;font-size:.8rem;color:#94a3b8;text-align:center'>
    ⚠️ <strong>تنبيه قانوني:</strong> هذه التحليلات للأغراض التعليمية والمعلوماتية فقط وليست نصيحة مالية. 
    التداول في الأسواق المالية ينطوي على مخاطر عالية وقد تخسر رأس مالك. استشر مستشاراً مالياً مرخصاً قبل اتخاذ أي قرار استثماري.
    </div>
    """, unsafe_allow_html=True)
