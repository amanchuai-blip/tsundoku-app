import streamlit as st
import google.generativeai as genai
import trafilatura
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
# 正規表現は不要になりましたが、以下のimportは必要です
from google.generativeai.types import GenerationConfig, Schema, Type 

# --- 1. アプリ全体のデザイン ---
st.set_page_config(page_title="積ん読解消♡Mate", page_icon="🎀", layout="centered")

# --- 2. モデルと設定（最も安定したJSON生成方法） ---
# ★ここにあなたのGemini APIキーを入れてください
API_KEY = "AIzaSyBWgr8g-cA6zybuyDHD9rhP2sS34uAj_24"
genai.configure(api_key=API_KEY)

# ユーザー様の指示に基づきモデルを指定
model = genai.GenerativeModel('gemini-2.5-flash')

# 【JSON構造の定義】これこそが、プログラムが欲しいデータの型（スキーマ）です
tsundoku_schema = Schema(
    type=Type.OBJECT,
    properties={
        "title": Schema(type=Type.STRING, description="記事のキャッチーなタイトル"),
        "summary": Schema(type=Type.STRING, description="3行程度の要約"),
        "point": Schema(type=Type.STRING, description="最も重要なポイント"),
        "action": Schema(type=Type.STRING, description="ユーザーが明日から実行すべき具体的な行動")
    },
    required=["title", "summary", "point", "action"]
)

# 【API設定】JSON形式を強制し、上記スキーマを適用
config = GenerationConfig(
    response_mime_type="application/json",
    response_schema=tsundoku_schema
)

# Google Sheets 接続設定（省略）
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
        st.error(f"DBに繋がらないみたい...権限設定を確認してね🥺\n{e}")
        return None

# --- 3. 裏方の仕事（関数） ---

def fetch_text(url):
    """URLから本文を優しく抜き出します"""
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return None
        text = trafilatura.extract(downloaded)
        return text
    except:
        return None

def analyze_text(text):
    """GeminiにJSONの生成を強制します"""
    # プロンプトはシンプルに。構造はAPI設定で保証されるため。
    prompt = "以下の記事を、定義されたJSONスキーマに従って分析してください。"
    
    try:
        # configを渡すことで、JSON形式での回答が保証されます
        response = model.generate_content(
            [prompt, text[:10000]],
            config=config 
        )
        
        # 回答はJSON形式で返ってくるので、そのままパースします
        return json.loads(response.text) 

    except Exception as e:
        # APIエラーや無効な回答が返ってきた場合に失敗
        print(f"API/Structured Output Error: {e}")
        return None

def add_to_sheet(ws, url, data):
    """スプレッドシートに書き込みます"""
    try:
        ws.insert_row([data['title'], url, data['summary'], data['point'], data['action']], 2)
        return True
    except:
        return False

# --- 4. 画面を作る（UI） ---

st.title("🎀 積ん読解消 Mate")
st.markdown("「あとで読む」を「今、分かった！」に変えちゃおう✨")

# DB接続チェック
ws = get_worksheet()
if not ws:
    st.stop()

# タブ作成
tab1, tab2 = st.tabs(["📥 記事を入れる", "📚 わたしの本棚"])

# --- タブ1：記事登録 ---
with tab1:
    st.write("### 読みたい記事のURLを教えてね")
    url_input = st.text_input("ここにペタッと貼り付け 👇", placeholder="https://...")

    if st.button("✨ AIに読んでもらう"):
        if not url_input:
            st.warning("あれ？URLが空っぽだよ🥺")
        else:
            with st.spinner("Gemini 2.5 Flashが熟読中...ちょっと待ってね☕"):
                # 1. 本文取得
                text = fetch_text(url_input)
                
                if text:
                    # 2. AI解析
                    result = analyze_text(text)
                    if result:
                        # 3. DB保存
                        if add_to_sheet(ws, url_input, result):
                            st.balloons() # 成功の舞！
                            st.success("読み終わったよ！「わたしの本棚」に追加しました💕")
                        else:
                            st.error("保存に失敗しちゃった...スプレッドシートの権限大丈夫かな？💦")
                    else:
                        # 構造化出力が失敗した場合（モデルが意図的に回答を拒否した場合など）
                        st.error("ごめんね、AIが内容を理解できなかったみたい...😭（モデルがJSON生成を拒否しました）")
                else:
                    st.error("ページが開けなかったよ...URLが正しいか確認してね🤔")

# --- タブ2：本棚 ---
with tab2:
    if st.button("🔄 リストを更新"):
        st.rerun()
    
    try:
        records = ws.get_all_records()
        if not records:
            st.info("まだ空っぽだよ。何か記事を入れてみてね！🐣")
        
        # 新しい順（リストの逆順）で表示
        for item in reversed(records):
            title = item.get('title', 'No Title')
            with st.expander(f"📖 {title}", expanded=True):
                st.markdown(f"**要約:** {item.get('summary')}")
                st.info(f"💡 **Point:** {item.get('point')}")
                st.success(f"🚀 **Action:** {item.get('action')}")
                st.caption(f"Source: {item.get('url')}")
                
    except Exception as e:
        st.error("データの読み込みに失敗しました。シートの1行目にヘッダーがあるか確認してね！")
