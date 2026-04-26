import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import requests
import re

API_KEY = "AIzaSyAjNB8UrB3ATezt_g8Nzrkzgkj9FqQYLEs"
DB_PATH = "retailsense.db"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=" + API_KEY

SCHEMA = """
Table name: sales
Columns:
  "Order ID"     TEXT
  "Order Date"   TEXT  (YYYY-MM-DD)
  "Ship Date"    TEXT  (YYYY-MM-DD)
  "Ship Mode"    TEXT  (Standard Class | Second Class | First Class | Same Day)
  "Customer ID"  TEXT
  "Customer Name" TEXT
  "Segment"      TEXT  (Consumer | Corporate | Home Office)
  "City"         TEXT
  "State"        TEXT
  "Region"       TEXT  (West | East | Central | South)
  "Product ID"   TEXT
  "Category"     TEXT  (Furniture | Office Supplies | Technology)
  "Sub-Category" TEXT
  "Product Name" TEXT
  "Sales"        REAL
  "Quantity"     INTEGER
  "Discount"     REAL
  "Profit"       REAL
"""

SAMPLE_QUESTIONS = [
    "Which region has the highest total sales?",
    "What are the top 5 most profitable sub-categories?",
    "Show me monthly sales trend for 2023",
    "Which customer segment generates the most profit?",
    "What is the average discount by category?",
    "Which states have negative total profit?",
    "Compare total sales and profit across all categories",
    "What percentage of orders use each shipping mode?",
    "Show total sales by year",
    "Which ship mode is most used by Corporate customers?",
]

def call_gemini(prompt):
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 1024},
    }
    try:
        r = requests.post(GEMINI_URL, json=payload, timeout=30)
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        return f"API_ERROR: {e}"

def generate_sql(question):
    prompt = f"""You are an expert SQLite analyst.
Schema:
{SCHEMA}
Convert the business question below into a valid SQLite SELECT query.
Rules:
- Double-quote every column name that has spaces
- Return ONLY the SQL inside a sql code block
- Add ORDER BY for ranked results; LIMIT 50 unless question implies all rows
- Monthly grouping: strftime('%Y-%m', "Order Date")
- Yearly grouping: strftime('%Y', "Order Date")
Question: {question}"""
    raw = call_gemini(prompt)
    # Try to extract from code block first
    m = re.search(r"```(?:sql)?\s*([\s\S]*?)```", raw, re.IGNORECASE)
    if m:
        sql = m.group(1).strip()
    else:
        # Fallback: find SELECT and take everything from there
        m2 = re.search(r"(SELECT[\s\S]+?)(?:;|\Z)", raw, re.IGNORECASE)
        sql = m2.group(1).strip() if m2 else raw.strip()
    # Final safety: strip anything before SELECT in case of "ite SELECT..." garbage
    sql = re.sub(r"^[\s\S]*?(SELECT)", r"\1", sql, flags=re.IGNORECASE)
    return sql.strip()

def run_query(sql):
    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql_query(sql, conn)
    finally:
        conn.close()
    return df

def generate_insight(question, df):
    preview = df.head(10).to_string(index=False)
    prompt = f"""You are a senior business analyst presenting to a non-technical executive.
Business question: "{question}"
Data ({len(df)} rows; first 10 shown):
{preview}
Write a 3-5 sentence executive insight that:
1. Directly answers the question with the key number or finding
2. Highlights one surprising or notable pattern
3. Ends with one concrete actionable recommendation
Rules: plain English only, no SQL or tech jargon, use $, percentages, specific numbers."""
    return call_gemini(prompt)

def auto_chart(df, question):
    if df.empty or len(df.columns) < 2:
        return None
    num = df.select_dtypes(include="number").columns.tolist()
    cat = df.select_dtypes(include="object").columns.tolist()
    q = question.lower()
    try:
        if any(w in q for w in ["trend", "monthly", "yearly", "over time", "by month", "by year"]):
            if cat and num:
                return px.line(df, x=cat[0], y=num[0], title=question, markers=True,
                               color_discrete_sequence=["#6366f1"])
        if any(w in q for w in ["percentage", "percent", "proportion", "share", "mode"]):
            if cat and num:
                return px.pie(df, names=cat[0], values=num[0], title=question,
                              color_discrete_sequence=px.colors.qualitative.Set3)
        if len(num) >= 2 and cat:
            return px.bar(df, x=cat[0], y=num[:2], title=question, barmode="group",
                          color_discrete_sequence=["#6366f1", "#06b6d4"])
        if cat and num:
            if len(df) <= 8:
                return px.bar(df, x=cat[0], y=num[0], title=question, text_auto=".2s",
                              color=num[0], color_continuous_scale="Blues")
            return px.bar(df, x=num[0], y=cat[0], orientation="h", title=question,
                          text_auto=".2s", color=num[0], color_continuous_scale="Blues")
    except Exception:
        pass
    return None

st.set_page_config(page_title="RetailSense AI", page_icon="🧠",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
.stApp{background:#0f172a;color:#e2e8f0}
.hero h1{font-size:2.4rem;font-weight:800;background:linear-gradient(135deg,#6366f1,#8b5cf6,#06b6d4);
-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;margin-bottom:0}
.hero p{color:#94a3b8;margin-top:.2rem}
.kpi{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:1.2rem;text-align:center}
.kv{font-size:1.7rem;font-weight:700;color:#6366f1}
.kv.g{color:#10b981}.kv.r{color:#ef4444}
.kl{font-size:.72rem;color:#64748b;text-transform:uppercase;letter-spacing:.06em}
.ibox{background:#1e293b;border-left:4px solid #6366f1;border-radius:0 12px 12px 0;
padding:1.2rem 1.5rem;line-height:1.8}
.sqlbox{background:#0d1117;border:1px solid #334155;border-radius:8px;padding:1rem;
font-family:monospace;font-size:.85rem;color:#7dd3fc;white-space:pre-wrap}
div[data-testid="stButton"]>button{
background:linear-gradient(135deg,#6366f1,#8b5cf6);color:#fff;border:none;
border-radius:8px;padding:.5rem 2rem;font-weight:600}
[data-testid="stSidebar"]{background:#0f172a;border-right:1px solid #1e293b}
.stTextInput>div>div>input{background:#1e293b;border:1px solid #475569;
color:#e2e8f0;border-radius:8px;font-size:1rem;padding:.75rem}
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("## 🧠 RetailSense AI")
    st.markdown("<small style='color:#64748b'>Natural Language → SQL → Chart → Insight</small>",
                unsafe_allow_html=True)
    st.divider()
    conn = sqlite3.connect(DB_PATH)
    s = pd.read_sql('SELECT COUNT(*) n, MIN("Order Date") mn, MAX("Order Date") mx FROM sales', conn)
    conn.close()
    row = s.iloc[0]
    st.markdown(f"**Dataset:** {row['n']:,} orders")
    st.markdown(f"**Period:** {row['mn']} → {row['mx']}")
    st.divider()
    st.markdown("**💡 Sample questions**")
    for q in SAMPLE_QUESTIONS:
        if st.button(q, key=f"sq_{q[:20]}", use_container_width=True):
            st.session_state["q"] = q
            st.rerun()
    st.divider()
    st.markdown("<small style='color:#475569'>Python · SQLite · Gemini AI · Streamlit · Plotly</small>",
                unsafe_allow_html=True)

st.markdown("""
<div class='hero'>
  <h1>🧠 RetailSense AI</h1>
  <p>Ask any business question in plain English — get charts, data tables, and AI-generated executive insights instantly.</p>
</div>""", unsafe_allow_html=True)

conn = sqlite3.connect(DB_PATH)
kpi = pd.read_sql("""SELECT ROUND(SUM("Sales"),0) s, ROUND(SUM("Profit"),0) p,
ROUND(SUM("Profit")*100.0/SUM("Sales"),1) m, COUNT(DISTINCT "Order ID") o FROM sales""", conn)
conn.close()
k = kpi.iloc[0]
c1, c2, c3, c4 = st.columns(4)
for col, label, val, cls in [
    (c1, "Total Sales",   f"${k['s']:,.0f}", ""),
    (c2, "Total Profit",  f"${k['p']:,.0f}", "g" if k["p"]>0 else "r"),
    (c3, "Profit Margin", f"{k['m']:.1f}%",  "g" if k["m"]>0 else "r"),
    (c4, "Total Orders",  f"{int(k['o']):,}",""),
]:
    with col:
        st.markdown(f'<div class="kpi"><div class="kv {cls}">{val}</div>'
                    f'<div class="kl">{label}</div></div>', unsafe_allow_html=True)

st.markdown("---")
st.markdown("### 💬 Ask a Business Question")
question = st.text_input("q", value=st.session_state.get("q",""),
                          placeholder="e.g.  Which region has the highest total sales?",
                          label_visibility="collapsed")
go = st.button("🔍  Analyze")

if go and question.strip():
    with st.spinner("🤖 Translating question to SQL..."):
        sql = generate_sql(question)
    with st.spinner("⚡ Querying database..."):
        try:
            df = run_query(sql)
        except Exception as e:
            st.error(f"SQL Error: {e}")
            st.code(sql)
            st.stop()
    with st.spinner("🧠 Generating executive insight..."):
        insight = generate_insight(question, df)

    st.markdown("---")
    st.markdown(f"### 📊 Results — *{question}*")

    if df.empty:
        st.warning("No data returned. Try rephrasing your question.")
    else:
        chart = auto_chart(df, question)
        if chart:
            t1, t2, t3 = st.tabs(["📈 Chart", "📋 Data Table", "🔧 SQL"])
            with t1:
                chart.update_layout(paper_bgcolor="rgba(0,0,0,0)",
                                    plot_bgcolor="rgba(30,41,59,0.5)",
                                    font_color="#e2e8f0", margin=dict(t=40,b=20,l=10,r=10))
                st.plotly_chart(chart, use_container_width=True)
            with t2:
                st.dataframe(df, use_container_width=True, height=350)
                st.download_button("⬇️ Download CSV", df.to_csv(index=False), "result.csv")
            with t3:
                st.code(sql, language="sql")
        else:
            st.dataframe(df, use_container_width=True)
            st.download_button("⬇️ Download CSV", df.to_csv(index=False), "result.csv")
            with st.expander("🔧 SQL Query"):
                st.code(sql, language="sql")

        st.markdown("### 🧠 AI Business Insight")
        st.markdown(f'<div class="ibox">{insight}</div>', unsafe_allow_html=True)

elif go:
    st.warning("Please type a question first.")

st.markdown("---")
st.markdown("<center><small style='color:#334155'>RetailSense AI · Python · SQLite · Gemini AI · Streamlit</small></center>",
            unsafe_allow_html=True)
