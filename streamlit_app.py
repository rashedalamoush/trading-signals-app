# streamlit_app.py — نظام إشارات التداول (ملف واحد مكتفي بذاته)
# شغّله بـ: streamlit run streamlit_app.py

import streamlit as st
import pandas as pd
import numpy as np
import requests
import feedparser
import yfinance as yf
import ccxt
from datetime import datetime, timedelta, timezone
from plotly.subplots import make_subplots
import plotly.graph_objects as go

# ══════════════════════════════════════════════════════
#  إعدادات الصفحة
# ══════════════════════════════════════════════════════
st.set_page_config(page_title="🤖 إشارات التداول", page_icon="📈",
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
#  الإعدادات الافتراضية للأسهم والعملات
# ══════════════════════════════════════════════════════
# تم إضافة أسهم الإمارات هنا بامتداد .AE
DEFAULT_STOCKS = ["AAPL","MSFT","NVDA","TSLA","AMZN","GOOGL","META","NFLX","AMD","INTC",
                  "EMAAR.AE","DIB.AE","EMIRATESNBD.AE","ALDAR.AE","AIRARABIA.AE"]

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
#  جلب البيانات
# ══════════════════════════════════════════════════════
def fetch_stock(symbol):
    try:
        df = yf.Ticker(symbol).history(period="6mo", interval="1d")
        if df.empty: return None
        return df[["Open","High","Low","Close","Volume"]].dropna()
    except: return None

def fetch_crypto(symbol):
    # الطريقة الأولى: الاعتماد على Yahoo Finance (ممتاز ومستقر على السيرفرات السحابية)
    try:
        yf_sym = symbol.replace("/USDT", "-USD")
        df = yf.Ticker(yf_sym).history(period="6mo", interval="1d")
        if not df.empty:
            return df[["Open","High","Low","Close","Volume"]].dropna()
    except:
        pass

    # الطريقة الثانية (بديل CCXT): استخدام KuCoin بدلاً من Binance لتجنب الحظر الجغرافي
    try:
        ex = ccxt.kucoin({"enableRateLimit": True})
        ohlcv = ex.fetch_ohlcv(symbol, timeframe="1d", limit=200)
        if not ohlcv: return None
        df = pd.DataFrame(ohlcv, columns=["ts","Open","High","Low","Close","Volume"])
        df["ts"] = pd.to_datetime(df["ts"], unit="ms")
        return df.set_index("ts").dropna()
    except: 
        return None
# ══════════════════════════════════════════════════════
#  المؤشرات الفنية
# ══════════════════════════════════════════════════════
def calc_indicators(df):
    d = df.copy()
    # RSI
    delta=d["Close"].diff(); gain=delta.clip(lower=0); loss=-delta.clip(upper=0)
    ag=gain.ewm(com=RSI_PERIOD-1,adjust=False).mean()
    al=loss.ewm(com=RSI_PERIOD-1,adjust=False).mean()
    d["RSI"]=100-(100/(1+ag/al.replace(0,np.nan)))
    # MACD
    ef=d["Close"].ewm(span=MACD_FAST,adjust=False).mean()
    es=d["Close"].ewm(span=MACD_SLOW,adjust=False).mean()
    d["MACD"]=ef-es
    d["MACD_Sig"]=d["MACD"].ewm(span=MACD_SIGNAL_P,adjust=False).mean()
    d["MACD_Hist"]=d["MACD"]-d["MACD_Sig"]
    # Bollinger
    sma=d["Close"].rolling(BB_PERIOD).mean()
    std=d["Close"].rolling(BB_PERIOD).std()
    d["BB_U"]=sma+BB_STD*std; d["BB_L"]=sma-BB_STD*std; d["BB_M"]=sma
    # MA
    d[f"MA{MA_SHORT}"]=d["Close"].rolling(MA_SHORT).mean()
    d[f"MA{MA_LONG}"]=d["Close"].rolling(MA_LONG).mean()
    # Volume
    d["Vol_MA"]=d["Volume"].rolling(20).mean()
    d["Vol_R"]=d["Volume"]/d["Vol_MA"]
    return d

def get_signal(df):
    last=df.iloc[-1]; prev=df.iloc[-2]
    buy=0; sell=0; reasons=[]
    
    c=float(last["Close"])
    
    # استراتيجية صيد القيعان (Buy Low Strategy)
    lowest_6m = df["Low"].min()
    dist_from_low = (c - lowest_6m) / lowest_6m
    if dist_from_low <= 0.05: # إذا كان السعر أعلى من القاع بـ 5% أو أقل
        buy+=1; reasons.append(f"🔥 السعر قريب جداً من قاع 6 أشهر ({lowest_6m:.2f}) ← فرصة شراء")

    rsi=float(last["RSI"])
    if rsi<RSI_OVERSOLD:   buy+=1;  reasons.append(f"RSI={rsi:.1f} تشبع بيعي (سعره مغرٍ) ← شراء")
    elif rsi>RSI_OVERBOUGHT: sell+=1; reasons.append(f"RSI={rsi:.1f} تشبع شرائي (سعره مرتفع) ← بيع")
    
    h=float(last["MACD_Hist"]); hp=float(prev["MACD_Hist"])
    if hp<0<h:   buy+=1;  reasons.append("MACD عبر الصفر صعوداً ← شراء")
    elif hp>0>h: sell+=1; reasons.append("MACD عبر الصفر هبوطاً ← بيع")
    
    if c<float(last["BB_L"]):   buy+=1;  reasons.append("السعر تحت مسار Bollinger السفلي ← شراء")
    elif c>float(last["BB_U"]): sell+=1; reasons.append("السعر فوق مسار Bollinger العلوي ← بيع")
    
    ms=float(last[f"MA{MA_SHORT}"]); ml=float(last[f"MA{MA_LONG}"])
    msp=float(prev[f"MA{MA_SHORT}"]); mlp=float(prev[f"MA{MA_LONG}"])
    if msp<mlp and ms>ml:   buy+=1;  reasons.append(f"تقاطع ذهبي MA{MA_SHORT}/MA{MA_LONG} ← شراء")
    elif msp>mlp and ms<ml: sell+=1; reasons.append(f"تقاطع الموت MA{MA_SHORT}/MA{MA_LONG} ← بيع")
    
    vr=float(last["Vol_R"])
    if vr>1.5:
        if buy>sell:   buy+=1;  reasons.append(f"حجم تداول مرتفع ({vr:.1f}x) يؤكد فرصة الشراء")
        elif sell>buy: sell+=1; reasons.append(f"حجم تداول مرتفع ({vr:.1f}x) يؤكد قوة البيع")
        
    net=buy-sell
    if net>=3:    sig="STRONG_BUY"
    elif net>=2:  sig="BUY"
    elif net<=-3: sig="STRONG_SELL"
    elif net<=-2: sig="SELL"
    else:         sig="HOLD"
    return sig, reasons, rsi, float(last["MACD_Hist"]), vr, c

# ══════════════════════════════════════════════════════
#  تحليل الأخبار
# ══════════════════════════════════════════════════════
POS_WORDS={"surge","soar","rally","jump","boom","bullish","breakout","record","growth",
           "profit","beat","upgrade","buy","strong","gain","rise","approved","partnership",
           "adoption","launch","etf","institutional","halving","all-time high"}
NEG_WORDS={"crash","plunge","drop","fall","decline","bearish","loss","miss","downgrade",
           "sell","weak","tumble","slump","recession","ban","hack","fraud","bankruptcy",
           "lawsuit","investigation","exploit","liquidation","sec charges","rug pull"}
STRONG_POS={"surge","soar","boom","record","breakout","approved","all-time high","etf"}
STRONG_NEG={"crash","ban","hack","fraud","bankruptcy","sec charges","rug pull","exploit"}

# إضافة الكلمات المفتاحية لأسهم الإمارات
STOCK_KW={"AAPL":["Apple","AAPL","iPhone"],"MSFT":["Microsoft","MSFT","Azure"],
          "NVDA":["Nvidia","NVDA","GPU"],"TSLA":["Tesla","TSLA","Elon Musk"],
          "AMZN":["Amazon","AMZN","AWS"],"GOOGL":["Google","Alphabet","GOOGL"],
          "META":["Meta","Facebook","Mark Zuckerberg"], "NFLX":["Netflix","NFLX"],
          "AMD":["AMD","Advanced Micro Devices"], "INTC":["Intel","INTC"],
          "EMAAR.AE":["Emaar Properties","Emaar","إعمار"], "DIB.AE":["Dubai Islamic Bank","DIB","بنك دبي الإسلامي"],
          "EMIRATESNBD.AE":["Emirates NBD","الإمارات دبي الوطني"], "ALDAR.AE":["Aldar Properties","Aldar","الدار العقارية"],
          "AIRARABIA.AE":["Air Arabia","طيران العربية"]}
CRYPTO_KW={"BTC/USDT":["Bitcoin","BTC"],"ETH/USDT":["Ethereum","ETH"],
           "SOL/USDT":["Solana","SOL"],"BNB/USDT":["Binance","BNB"],"XRP/USDT":["XRP","Ripple"]}

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
    if s>=0.4:  return "🟢 إيجابي قوي"
    if s>=0.15: return "🟡 إيجابي"
    if s<=-0.4: return "🔴 سلبي قوي"
    if s<=-0.15:return "🟠 سلبي"
    return "⚪ محايد"

def fetch_news(symbol, asset_type, newsapi_key="", cryptopanic_key=""):
    articles=[]; kws=[]
    if asset_type=="stock":    kws=STOCK_KW.get(symbol,[symbol])
    else:                      kws=CRYPTO_KW.get(symbol,[symbol.replace("/USDT","")])

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

    if asset_type=="crypto":
        try:
            feed=feedparser.parse("https://www.coindesk.com/arc/outboundfeeds/rss/")
            kl=[k.lower() for k in kws]
            for e in feed.entries[:20]:
                t=e.get("title",""); sm=e.get("summary","")
                if not any(k in (t+sm).lower() for k in kl): continue
                s=analyze_sentiment(t+" "+sm)
                articles.append({"source":"CoinDesk","title":t,"sentiment":s})
                if len([a for a in articles if a["source"]=="CoinDesk"])>=4: break
        except: pass

    if asset_type=="crypto":
        try:
            coin=symbol.replace("/USDT","")
            params={"currencies":coin,"public":"true","kind":"news"}
            if cryptopanic_key: params["auth_token"]=cryptopanic_key
            r=requests.get("https://cryptopanic.com/api/v1/posts/",params=params,timeout=8)
            for item in r.json().get("results",[])[:6]:
                t=item.get("title",""); s=analyze_sentiment(t)
                v=item.get("votes",{}); s=min(1.0,s+0.1) if v.get("positive",0)>v.get("negative",0) else max(-1.0,s-0.1)
                articles.append({"source":"CryptoPanic","title":t,"sentiment":round(s,2)})
        except: pass

    if newsapi_key:
        try:
            q=" OR ".join(kws[:3])
            r=requests.get("https://newsapi.org/v2/everything",timeout=8,
                params={"q":q,"language":"en","sortBy":"publishedAt","pageSize":5,
                        "apiKey":newsapi_key,"from":(datetime.now()-timedelta(days=2)).strftime("%Y-%m-%d")})
            for item in r.json().get("articles",[]):
                t=(item.get("title") or ""); d=(item.get("description") or "")
                s=analyze_sentiment(t+" "+d)
                articles.append({"source":item.get("source",{}).get("name","News"),"title":t,"sentiment":round(s,2)})
        except: pass

    if not articles:
        return {"label":"⚪ لا أخبار","signal":"HOLD","score":0.0,"articles":[]}

    scores=[a["sentiment"] for a in articles]
    w=list(range(len(scores),0,-1))
    avg=sum(s*wt for s,wt in zip(scores,w))/sum(w)
    pos=sum(1 for s in scores if s>0.1); neg=sum(1 for s in scores if s<-0.1)
    nsig="BUY" if avg>=0.25 and pos>neg else "SELL" if avg<=-0.25 and neg>pos else "HOLD"
    return {"label":sentiment_label(avg),"signal":nsig,"score":round(avg,3),"articles":articles[:8]}

def merge_signals(tech, news_sig, news_score):
    up={"BUY":"STRONG_BUY","SELL":"STRONG_SELL","HOLD":"BUY"}
    dn={"STRONG_BUY":"BUY","STRONG_SELL":"SELL","BUY":"HOLD","SELL":"HOLD"}
    bull=news_sig=="BUY"  and news_score>0.2
    bear=news_sig=="SELL" and news_score<-0.2
    if tech in ("BUY","STRONG_BUY")   and bull: return up.get(tech,tech)
    if tech in ("SELL","STRONG_SELL") and bear: return up.get(tech,tech)
    if tech in ("BUY","STRONG_BUY")   and bear: return dn.get(tech,"HOLD")
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
#  UI الرئيسي
# ══════════════════════════════════════════════════════
st.markdown("# 🤖 نظام إشارات التداول الذكي")
st.markdown("<p style='color:#64748b;margin-top:-14px'>أسهم · عملات رقمية · صيد القيعان · تحليل أخبار</p>",unsafe_allow_html=True)
st.divider()

with st.sidebar:
    st.markdown("### ⚙️ الإعدادات")
    asset_type=st.radio("نوع الأصل",["📈 أسهم","₿ عملات رقمية","🌐 الكل"],index=2)
    st.markdown("**الأسهم (تشمل أمريكا والإمارات)**")
    # تم وضع أسهم الإمارات كجزء من الاختيارات الافتراضية
    sel_stocks=st.multiselect("أسهم",DEFAULT_STOCKS,default=["AAPL","MSFT","EMAAR.AE","DIB.AE"],label_visibility="collapsed")
    st.markdown("**العملات الرقمية**")
    sel_crypto=st.multiselect("كريبتو",DEFAULT_CRYPTO,default=DEFAULT_CRYPTO[:4],label_visibility="collapsed")
    st.markdown("---")
    fetch_news_toggle=st.toggle("📰 تحليل الأخبار",value=True)
    only_actionable=st.toggle("🔔 إشارات فعلية فقط",value=True)
    st.markdown("---")
    st.markdown("**🔑 API Keys**")
    newsapi_key=st.text_input("NewsAPI Key",type="password", value="558f26b08860418ea42396a5794fc124")
    cryptopanic_key=st.text_input("CryptoPanic Key",type="password", value="6417468b0d999e839e5774c350baee05e3297ba7")
    st.markdown("---")
    run_btn=st.button("🔍 ابدأ المسح الآن",use_container_width=True)

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
            news=fetch_news(sym,"stock",newsapi_key,cryptopanic_key) if fetch_news_toggle else {"label":"","signal":"HOLD","score":0.0,"articles":[]}
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
            news=fetch_news(sym,"crypto",newsapi_key,cryptopanic_key) if fetch_news_toggle else {"label":"","signal":"HOLD","score":0.0,"articles":[]}
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
if not results:
    st.markdown("<div style='text-align:center;padding:80px 0'><div style='font-size:5rem'>📡</div><div style='font-size:1.3rem;color:#334155;margin-top:16px'>اضغط ابدأ المسح من القائمة الجانبية</div></div>",unsafe_allow_html=True)
    st.stop()

st.markdown(f"<p style='color:#475569;font-size:.85rem'>⏱ آخر مسح: {st.session_state.last_scan}</p>",unsafe_allow_html=True)

# KPIs
n_sb=sum(1 for r in results if r["signal"]=="STRONG_BUY")
n_b=sum(1 for r in results if r["signal"]=="BUY")
n_h=sum(1 for r in results if r["signal"]=="HOLD")
n_s=sum(1 for r in results if r["signal"] in ("SELL","STRONG_SELL"))
cols=st.columns(5)
for col,(val,lbl,color) in zip(cols,[(len(results),"إجمالي","#e2e8f0"),(n_sb,"🚀 شراء قوي","#00ff88"),
    (n_b,"🟢 شراء","#22c55e"),(n_h,"🟡 انتظار","#eab308"),(n_s,"🔴 بيع","#ef4444")]):
    col.markdown(f"<div class='kpi-box'><div class='kpi-val' style='color:{color}'>{val}</div><div class='kpi-lbl'>{lbl}</div></div>",unsafe_allow_html=True)

st.markdown("<br>",unsafe_allow_html=True)
t1,t2,t3=st.tabs(["📋 الإشارات","📊 الرسم البياني","📰 الأخبار"])

with t1:
    order={"STRONG_BUY":0,"BUY":1,"HOLD":2,"SELL":3,"STRONG_SELL":4}
    display=[r for r in results if not only_actionable or r["signal"]!="HOLD"]
    display.sort(key=lambda x:order.get(x["signal"],2))
    if not display:
        st.info("لا توجد إشارات فعلية حالياً — جميع الأصول في وضع الانتظار.")
    for r in display:
        c=SIGNAL_COLOR.get(r["signal"],"#64748b")
        lbl=SIGNAL_EMOJI.get(r["signal"],r["signal"])
        icon="📈" if r["type"]=="stock" else "₿"
        rs="".join(f"<div style='font-size:.83rem;color:#64748b;margin-top:3px'>• {x}</div>" for x in r["reasons"]) or "<div style='font-size:.83rem;color:#64748b'>لا توجد إشارات فنية واضحة</div>"
        ns=""
        if r["news_label"]:
            nc="#22c55e" if r["news_score"]>0.15 else "#ef4444" if r["news_score"]<-0.15 else "#64748b"
            ns=f"<div style='margin-top:8px;font-size:.82rem;color:{nc}'>📰 {r['news_label']} | درجة: {r['news_score']:+.2f}</div>"
        st.markdown(f"""<div class='sig-card sig-{r["signal"]}'>
          <div style='display:flex;justify-content:space-between;align-items:center'>
            <span style='font-size:1.1rem;font-weight:900;color:#e2e8f0'>{icon} {r["symbol"]}</span>
            <span style='font-size:1.3rem;font-weight:900;color:{c}'>{lbl}</span>
          </div>
          <div style='font-size:.9rem;color:#94a3b8;font-family:IBM Plex Mono,monospace;margin-top:4px'>
            السعر: {r["price"]:,.4f} &nbsp;|&nbsp; RSI: {r["rsi"]:.1f} &nbsp;|&nbsp; الحجم: {r["vol_ratio"]:.1f}x
          </div>
          {rs}{ns}
        </div>""",unsafe_allow_html=True)

with t2:
    syms=[r["symbol"] for r in results]
    chosen=st.selectbox("اختر الأصل",syms)
    df_c=st.session_state.raw_data.get(chosen)
    if df_c is not None:
        sig_c=next((r for r in results if r["symbol"]==chosen),None)
        if sig_c:
            c1,c2,c3,c4=st.columns(4)
            c1.metric("الإشارة",SIGNAL_EMOJI.get(sig_c["signal"],"-"))
            c2.metric("RSI",f"{sig_c['rsi']:.1f}")
            c3.metric("MACD Hist",f"{sig_c['macd_hist']:+.4f}")
            c4.metric("الحجم",f"{sig_c['vol_ratio']:.1f}x")
        st.plotly_chart(draw_chart(df_c,chosen),use_container_width=True)

with t3:
    has=[r for r in results if r.get("articles")]
    if not has:
        st.info("فعّل 'تحليل الأخبار' من الشريط الجانبي.")
    for r in has:
        icon="📈" if r["type"]=="stock" else "₿"
        with st.expander(f"{icon} {r['symbol']}  —  {r['news_label']}  ({r['news_score']:+.2f})"):
            for a in r["articles"]:
                st.markdown(f"<div style='padding:8px 12px;background:#0f1729;border-radius:6px;border:1px solid #1e2d4a;margin-bottom:6px;font-size:.87rem;color:#cbd5e1'>• {a}</div>",unsafe_allow_html=True)
