import streamlit as st
import google.generativeai as genai
import trafilatura
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- 1. アプリ全体のデザイン ---
st.set_page_config(page_title="積ん読解消♡Mate", page_icon="🎀", layout="centered")

# --- 2. 設定（APIキー & DB接続） ---
# ★ここにあなたのGemini APIキーを入れてください (有効なキーであることを確認済み！)
API_KEY = "AIzaSyBWgr8g-cA6zybuyDHD9rhP2sS34uAj_24" 
genai.configure(api_key=API_KEY)

# 最新のGemini 2.5 Proモデルを使用
model = genai.GenerativeModel('gemini-2.5-pro')

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
        # ファイル名「積ん読DB」でシートを開く
        return client.open("積ん読DB").sheet1
    except Exception as e:
        # 権限やファイル名が間違っている場合にエラーを表示
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
    """Gemini 2.5 Pro先生に要約をお願いします"""
    prompt = f"""
    あなたは優秀な専属秘書です。以下の記事を読んで、忙しい私のために要点をまとめてください。
    出力は必ず以下のJSON形式のみでお願いします。余計な前置きや説明文は一切書かないでください。
    {{
        "title": "記事のタイトル（キャッチーに）",
        "summary": "3行で要約",
        "point": "一番の重要ポイント",
        "action": "私が明日からやるべき具体的なAction"
    }}
    ---記事本文---
    {text[:10000]}
    """
    try:
        response = model.generate_content(prompt)
        
        # 正規表現で、回答全体から波括弧{...}で囲まれたJSONブロックだけを確実に抽出する
        match = re.search(r'\{.*\}', response.text, re.DOTALL)
        
        if match:
            cleaned_text = match.group(0)
            return json.loads(cleaned_text) 
        else:
            # JSON形式の回答が得られなかった場合
            return None
            
    except:
        return None

def add_to_sheet(ws, url, data):
    """スプレッドシートに書き込みます"""
    try:
        # 2行目に挿入（1行目はヘッダーなので）
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
            with st.spinner("Gemini 2.5 Proが熟読中...ちょっと待ってね☕"):
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
                        st.error("ごめんね、AIが内容を理解できなかったみたい...😭（サイトの文字が少なすぎるかも）")
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

