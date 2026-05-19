import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import database as db
from database import DEMO_MODE

# ─── ページ設定 ──────────────────────────────────────────────
st.set_page_config(
    page_title="Seikyu - 請求書管理",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── グローバルCSS ───────────────────────────────────────────
st.markdown("""
<style>
/* サイドバータイトルのアクセントカラー */
section[data-testid="stSidebar"] h1 { color: #1e4d7b; }
/* ボタンの微調整 */
div[data-testid="stButton"] > button[kind="primary"] {
    background-color: #1e4d7b;
    border-color: #1e4d7b;
}
div[data-testid="stButton"] > button[kind="primary"]:hover {
    background-color: #174069;
    border-color: #174069;
}
/* ダウンロードボタン */
div[data-testid="stDownloadButton"] > button[kind="primary"] {
    background-color: #1e4d7b;
    border-color: #1e4d7b;
}
/* pages/ フォルダから自動生成されるサイドバーナビを非表示 */
[data-testid="stSidebarNav"] { display: none; }
</style>
""", unsafe_allow_html=True)

# ─── DB初期化 ────────────────────────────────────────────────
db.init_db()

# ─── デモモードバナー ─────────────────────────────────────────
if DEMO_MODE and not st.session_state.get("_demo_notified"):
    st.session_state["_demo_notified"] = True
    st.toast(
        "データベースを初期化しました。データはアプリ再起動時にリセットされます。",
        icon="🔄",
    )

# ─── サイドバー ──────────────────────────────────────────────
with st.sidebar:
    st.title("📄 Seikyu")
    st.caption("請求書自動生成ツール")
    st.divider()

    PAGES = {
        "👥 顧客一覧":   "顧客一覧",
        "📝 請求書作成": "請求書作成",
        "📋 請求書履歴": "請求書履歴",
        "⚙️ 設定":       "設定",
    }

    page_label = st.radio(
        "メニュー",
        list(PAGES.keys()),
        label_visibility="collapsed",
    )
    page = PAGES[page_label]

    st.divider()

    company = db.get_company_info()
    if company and company.company_name:
        st.caption(f"🏢 **{company.company_name}**")
        if company.registration_number:
            st.caption(f"登録番号：{company.registration_number}")
    else:
        st.warning("⚠️ 自社情報が未設定です。\n「⚙️ 設定」から登録してください。")

    st.divider()
    if DEMO_MODE:
        st.warning("🔄 **デモ版**\nデータは再起動でリセットされます。")
    st.caption("ver 1.0.0")

# ─── 初回セットアップガイド ──────────────────────────────────
if not (company and company.company_name) and page != "設定":
    st.info(
        "**Seikyu へようこそ！** まず自社情報を登録しましょう。\n\n"
        "左のメニューから **⚙️ 設定** を選択し、会社名・住所・振込先などを入力してください。"
        "登録後、顧客の追加・請求書の作成が行えます。",
        icon="👋",
    )
    st.stop()

# ─── ページルーティング ──────────────────────────────────────
if page == "顧客一覧":
    from pages.customers import show
    show()
elif page == "請求書作成":
    from pages.invoice_create import show
    show()
elif page == "請求書履歴":
    from pages.invoice_history import show
    show()
elif page == "設定":
    from pages.settings import show
    show()
