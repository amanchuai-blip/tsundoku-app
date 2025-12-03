import streamlit as st
import google.generativeai as genai
import trafilatura
import json

# --- 1. アプリ全体のデザイン設定 ---
st.set_page_config(
    page_title="積ん読解消♡Mate",
    page_icon="🎀",
    layout="centered"  # スマホで見やすいように中央寄せ
)

# --- 2. 設定（APIキーなど） ---
# ★ここにGoogle AI Studioで取得したキーを入れてください
API_KEY = "AIzaSyC-XMebT1FNxpq_m7WCWpn4fEDM4LE8ABI"
genai.configure(api_key=API_KEY)

# モデル設定（かわいい反応をしてほしいのでプロンプトで性格付けも可能です）
model = genai.GenerativeModel('gemini-2.5-flash')

# --- 3. データ置き場（セッション） ---
if 'tsundoku_list' not in st.session_state:
    st.session_state['tsundoku_list'] = []

# --- 4. 関数（裏方の仕事） ---

def fetch_text(url):
    """URLから本文を優しく抜き出します"""
    try:
        downloaded = trafilatura.fetch_url(url)
        text = trafilatura.extract(downloaded)
        return text
    except:
        return None

def analyze_text(text):
    """Geminiちゃんに要約をお願いします"""
    prompt = f"""
    あなたは優秀で親切なアシスタントです。以下の記事を読んで、忙しい私のために分かりやすくまとめてください。
    出力は必ず以下のJSON形式のみでお願いします。余計な文字は入れないでね。

    {{
        "title": "記事のタイトル（キャッチーに）",
        "summary": "3行くらいでふんわり要約",
        "point": "特に重要なポイントを1つだけズバリ",
        "action": "私が明日からやるべきこと（ToDo）"
    }}

    ---記事本文---
    {text[:8000]}
    """
    try:
        response = model.generate_content(prompt)
        return json.loads(response.text.replace("```json", "").replace("```", ""))
    except:
        return None

# --- 5. 画面を作る（UI） ---

st.title("🎀 積ん読解消 Mate")
st.markdown("「あとで読む」を「今、分かった！」に変えちゃおう✨")

# タブ作成
tab1, tab2 = st.tabs(["📥 記事を入れる", "📚 わたしの本棚"])

# --- タブ1：記事登録 ---
with tab1:
    st.write("### 読みたい記事のURLを教えてね")
    url = st.text_input("ここにペタッと貼り付け 👇", placeholder="https://...")

    if st.button("✨ AIに読んでもらう"):
        if not url:
            st.warning("あれ？URLが空っぽだよ🥺")
        else:
            with st.spinner("今読んでるからちょっと待ってね...☕"):
                text = fetch_text(url)
                
                if text:
                    result = analyze_text(text)
                    if result:
                        # 成功したらリストに追加
                        item = {
                            "url": url,
                            "data": result
                        }
                        st.session_state['tsundoku_list'].insert(0, item)
                        
                        st.balloons() # かわいい演出！
                        st.success("読み終わったよ！「わたしの本棚」を見てみてね💕")
                    else:
                        st.error("ごめんね、うまく解析できなかったみたい...💦")
                else:
                    st.error("ページが開けなかったよ...URL合ってるかな？🤔")

# --- タブ2：本棚 ---
with tab2:
    if not st.session_state['tsundoku_list']:
        st.info("まだ空っぽだよ。何か記事を入れてみてね！🐣")
    
    for item in st.session_state['tsundoku_list']:
        data = item['data']
        
        # カード風のデザイン
        with st.expander(f"📖 {data['title']}", expanded=True):
            st.markdown(f"**要約:** {data['summary']}")
            st.info(f"💡 **ポイント:** {data['point']}")
            st.success(f"🚀 **Action:** {data['action']}")
            st.caption(f"Original: {item['url']}")