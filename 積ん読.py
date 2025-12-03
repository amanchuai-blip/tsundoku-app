import streamlit as st
import google.generativeai as genai
import trafilatura
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import traceback

st.set_page_config(page_title="積ん読デバッグ", page_icon="🔧", layout="centered")

# --- 設定 ---
# ★ここにAPIキーを入れる
API_KEY = "AIzaSyBWgr8g-cA6zybuyDHD9rhP2sS34uAj_24"
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

# --- DB接続 ---
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']

@st.cache_resource
def get_worksheet():
    try:
        # Secretsの確認
        if "gcp_service_account" not in st.secrets:
            st.error("Secretsに 'gcp_service_account' が設定されていません！")
            return None
            
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client.open("積ん読DB").sheet1
    except Exception as e:
        st.error(f"💥 DB接続エラー:\n{e}")
        return None

# --- ロジック（エラーを表示するように改造） ---

def fetch_text(url):
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded is None:
            st.error(f"URLからデータを取得できませんでした。サイト側でブロックされている可能性があります。\nURL: {url}")
            return None
        text = trafilatura.extract(downloaded)
        if text is None:
            st.error("本文の抽出に失敗しました。")
            return None
        return text
    except Exception as e:
        st.error(f"💥 スクレイピングエラー:\n{e}")
        return None

def analyze_text(text):
    prompt = f"""
    以下の記事を読んでJSON形式で出力してください。
    {{
        "title": "記事タイトル",
        "summary": "3行要約",
        "point": "重要ポイント",
        "action": "Next Action"
    }}
    ---
    {text[:5000]}
    """
    try:
        response = model.generate_content(prompt)
        # 生のレスポンスを表示（デバッグ用）
        print(f"Gemini Response: {response.text}") 
        
        return json.loads(response.text.replace("```json", "").replace("```", ""))
    except Exception as e:
        st.error(f"💥 Geminiエラー（APIキーかプロンプトが原因かも）:\n{e}")
        # 詳細なトレースバックを表示
        st.text(traceback.format_exc())
        return None

def add_to_sheet(ws, url, data):
    try:
        ws.insert_row([data['title'], url, data['summary'], data['point'], data['action']], 2)
    except Exception as e:
        st.error(f"💥 スプレッドシート書き込みエラー:\n{e}")

# --- UI ---
st.title("🔧 デバッグモード")

ws = get_worksheet()
if not ws:
    st.stop()

url = st.text_input("URLを入力", placeholder="https://...")

if st.button("実行"):
    if not url:
        st.warning("URLが空です")
    else:
        st.info("処理開始...")
        
        # 1. スクレイピング
        text = fetch_text(url)
        if text:
            st.success("✅ 本文取得成功")
            
            # 2. AI解析
            result = analyze_text(text)
            if result:
                st.success("✅ AI解析成功")
                st.json(result) # 解析結果を画面に出す
                
                # 3. DB保存
                add_to_sheet(ws, url, result)
                st.success("✅ DB保存完了")
            else:
                st.error("❌ AI解析で停止")
        else:
            st.error("❌ スクレイピングで停止")

