import streamlit as st
import google.generativeai as genai
import trafilatura
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
# 正規表現は不要になりましたが、importは残しておいても害はありません
import re 

# --- 1. アプリ全体のデザイン ---
st.set_page_config(page_title="積ん読解消♡Mate", page_icon="🎀", layout="centered")

# --- 2. モデルと設定 ---
# Secretsから安全にキーを取り出す
API_KEY = st.secrets["GEMINI_API_KEY"]
genai.configure(api_key=API_KEY)

# モデル設定 (最も安定したGemini 1.5 Pro)
model = genai.GenerativeModel('gemini-2.5-flash')

# 【JSON構造の定義】
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
    """DB(シート)に接続する関数"""
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

# --- 3. 裏方の仕事（関数） ---

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
        response = model.generate_content(
            [prompt, text[:10000]],
            generation_config=config 
        )
        return json.loads(response.text) 
    except Exception as e:
        print(f"API Error: {e}")
        return None

def add_to_sheet(ws, url, data):
    try:
        # 2行目に挿入（1行目はヘッダー）
        ws.insert_row([data['title'], url, data['summary'], data['point'], data['action']], 2)
        return True
    except:
        return False

def delete_row(ws, row_number):
    """指定した行番号を削除する"""
    try:
        ws.delete_rows(row_number)
        return True
    except Exception as e:
        st.error(f"削除エラー: {e}")
        return False

def delete_all_data(ws):
    """データ部分（2行目以降）を全て削除する"""
    try:
        # シートの全行数を取得
        row_count = len(ws.get_all_values())
        if row_count > 1:
            # 2行目から最終行まで削除
            ws.delete_rows(2, row_count)
        return True
    except Exception as e:
        st.error(f"全削除エラー: {e}")
        return False

# --- 4. 画面を作る（UI） ---

st.title("🎀 積ん読解消 Mate")
ws = get_worksheet()
if not ws: st.stop()

tab1, tab2 = st.tabs(["📥 登録", "📚 本棚"])

# --- タブ1：登録 ---
with tab1:
    url = st.text_input("URLを貼り付け 👇")
    if st.button("✨ 解析スタート"):
        if not url:
            st.warning("URLが空です")
        else:
            with st.spinner("Gemini 2.5 flash が解析中..."):
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

# --- タブ2：本棚（削除機能付き） ---
with tab2:
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("🔄 更新"):
            st.rerun()
    with col2:
        # 全削除ボタン（誤爆防止のため確認用チェックボックスなどをつけても良いが、今回はシンプルに）
        if st.button("🗑️ 全て空にする", type="primary"):
            if delete_all_data(ws):
                st.success("全て削除しました！")
                st.rerun()
    
    try:
        # 全データを取得
        records = ws.get_all_records()
        
        if not records:
            st.info("データなし。積ん読ゼロです！✨")
        else:
            # 【重要】削除のために「行番号」を計算しながらループする
            # recordsは0始まりのリストだが、Spreadsheetの行番号は「ヘッダー(1行) + リストのインデックス + 1」で始まる
            # つまり、records[0] は 2行目 にある。
            # 逆順で表示したいので、reversedを使うが、元のインデックスも保持する必要がある。
            
            # (index, item) のリストを作って、それを逆順にする
            indexed_records = list(enumerate(records)) # [(0, item1), (1, item2)...]
            
            for i, item in reversed(indexed_records):
                # Spreadsheet上の行番号 = インデックス(0始まり) + 2 (ヘッダー分)
                row_num = i + 2
                
                with st.expander(f"📖 {item.get('title', 'No Title')}", expanded=True):
                    st.markdown(f"**要約:** {item.get('summary')}")
                    st.info(f"💡 **Point:** {item.get('point')}")
                    st.success(f"🚀 **Action:** {item.get('action')}")
                    st.caption(f"URL: {item.get('url')}")
                    
                    # 個別削除ボタン
                    # keyをユニークにしないとエラーになるので f"del_{row_num}" をつける
                    if st.button("このメモを削除", key=f"del_{row_num}"):
                        if delete_row(ws, row_num):
                            st.rerun() # 削除したら再読み込み
                            
    except Exception as e:
        st.error(f"データ読み込みエラー: {e}")
