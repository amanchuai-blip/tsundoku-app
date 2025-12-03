import streamlit as st
import google.generativeai as genai
import trafilatura
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- 1. アプリ設定 ---
st.set_page_config(page_title="積ん読解消♡Mate", page_icon="🎀", layout="centered")

# --- 2. 接続設定 ---
# ★ Gemini APIキー (GitHubで編集するときにここを書き換えてね)
API_KEY = 'AIzaSyBWgr8g-cA6zybuyDHD9rhP2sS34uAj_24'
genai.configure(api_key='AIzaSyBWgr8g-cA6zybuyDHD9rhP2sS34uAj_24')
model = genai.GenerativeModel('gemini-1.5-flash')

# Google Sheets 接続設定
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']

@st.cache_resource
def get_worksheet():
    """DB(シート)に接続する。接続コストが高いのでキャッシュする"""
    try:
        # Secretsから鍵を取り出す
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        # ファイル名でシートを探す
        return client.open("積ん読DB").sheet1
    except Exception as e:
        st.error(f"DB接続エラー: {e}")
        return None

# --- 3. ロジック ---
def fetch_text(url):
    try:
        downloaded = trafilatura.fetch_url(url)
        return trafilatura.extract(downloaded)
    except:
        return None

def analyze_text(text):
    prompt = f"""
    記事を読んでJSONで出力してください。
    {{
        "title": "記事タイトル",
        "summary": "3行要約",
        "point": "重要ポイント",
        "action": "Next Action"
    }}
    ---
    {text[:8000]}
    """
    try:
        response = model.generate_content(prompt)
        return json.loads(response.text.replace("```json", "").replace("```", ""))
    except:
        return None

def add_to_sheet(ws, url, data):
    # 2行目に挿入（1行目はヘッダーなので）
    ws.insert_row([data['title'], url, data['summary'], data['point'], data['action']], 2)

# --- 4. UI ---
st.title("🎀 積ん読解消 Mate (Cloud)")

# DB接続チェック
ws = get_worksheet()
if not ws:
    st.stop()

tab1, tab2 = st.tabs(["📥 登録", "📚 本棚"])

with tab1:
    url = st.text_input("URLを貼ってね", placeholder="https://...")
    if st.button("✨ 保存"):
        if url:
            with st.spinner("解析 & DB保存中..."):
                text = fetch_text(url)
                if text and (res := analyze_text(text)):
                    add_to_sheet(ws, url, res)
                    st.balloons()
                    st.success("完了！")
                else:
                    st.error("失敗...")

with tab2:
    if st.button("🔄 更新"):
        st.rerun()
    
    # データ取得
    records = ws.get_all_records()
    if not records:
        st.info("データがないよ")
    
    # 新しい順に表示
    for item in reversed(records):
        with st.expander(f"📖 {item.get('title')}", expanded=True):
            st.write(item.get('summary'))
            st.info(f"Point: {item.get('point')}")
            st.success(f"Action: {item.get('action')}")
            st.caption(f"URL: {item.get('url')}")


