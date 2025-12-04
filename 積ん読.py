import streamlit as st
import google.generativeai as genai
import trafilatura
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
# ★ エラーの原因だった import 行を削除しました

# --- 1. アプリ全体のデザイン ---
st.set_page_config(page_title="積ん読解消♡Mate", page_icon="🎀", layout="centered")

# --- 2. 設定 ---
API_KEY = "AIzaSyBWgr8g-cA6zybuyDHD9rhP2sS34uAj_24"
genai.configure(api_key=API_KEY)

# モデル設定 (JSONモード対応の最新版)
model = genai.GenerativeModel('gemini-2.5-flash')

# 【修正】Schemaクラスを使わず、辞書型(dict)で定義する（これでImportErrorは起きない）
tsundoku_schema = {
    "type": "OBJECT",
    "properties": {
        "title": {"type": "STRING", "description": "記事のキャッチーなタイトル"},
        "summary": {"type": "STRING", "description": "3行程度の要約"},
        "point": {"type": "STRING", "description": "最も重要なポイント"},
        "action": {"type": "STRING", "description": "明日からやるべき具体的なアクション"}
    },
    "required": ["title", "summary", "point", "action"]
}

# API設定
config = genai.types.GenerationConfig(
    response_mime_type="application/json",
    response_schema=tsundoku_schema
)

# Google Sheets 接続設定
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']

@st.cache_resource
def get_worksheet():
    try:
        if "gcp_service_account" not in st.secrets:
            st.error("設定エラー: SecretsにGoogle Cloudの鍵が見つからないよ💦")
            return None
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client.open("積ん読DB").sheet1
    except Exception as e:
        st.error(f"DB接続エラー: {e}")
        return None

# --- 3. 関数群 ---

def fetch_text(url):
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded: return None
        return trafilatura.extract(downloaded)
    except:
        return None

def analyze_text(text):
    prompt = "以下の記事を分析してください。"
    try:
        # configを渡してJSON強制
        response = model.generate_content(
            [prompt, text[:10000]],
            generation_config=config 
        )
        return json.loads(response.text)
    except Exception as e:
        st.error(f"解析エラー: {e}")
        return None

def add_to_sheet(ws, url, data):
    try:
        ws.insert_row([data['title'], url, data['summary'], data['point'], data['action']], 2)
        return True
    except:
        return False

# --- 4. UI ---

st.title("🎀 積ん読解消 Mate")
ws = get_worksheet()
if not ws: st.stop()

tab1, tab2 = st.tabs(["📥 登録", "📚 本棚"])

with tab1:
    url = st.text_input("URLを貼り付け 👇")
    if st.button("✨ 解析スタート"):
        if not url:
            st.warning("URLが空です")
        else:
            with st.spinner("Gemini 2.5 Proが解析中..."):
                text = fetch_text(url)
                if text:
                    result = analyze_text(text)
                    if result:
                        if add_to_sheet(ws, url, result):
                            st.balloons()
                            st.success("完了！本棚に追加しました")
                        else:
                            st.error("DB保存失敗")
                    else:
                        st.error("AI解析失敗")
                else:
                    st.error("URL読み込み失敗")

with tab2:
    if st.button("🔄 更新"): st.rerun()
    try:
        records = ws.get_all_records()
        if not records: st.info("データなし")
        for item in reversed(records):
            with st.expander(f"📖 {item.get('title')}", expanded=True):
                st.write(item.get('summary'))
                st.info(f"Point: {item.get('point')}")
                st.success(f"Action: {item.get('action')}")
                st.caption(f"URL: {item.get('url')}")
    except:
        st.error("データ読み込みエラー")
