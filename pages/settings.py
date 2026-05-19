import re
import os
import streamlit as st
import database as db
from models import CompanyInfo

LOGO_DEST = os.path.join("static", "logo.png")
_REG_NUM_RE = re.compile(r"^T\d{13}$")


# ─── セッション状態初期化 ────────────────────────────────────

def _init_state():
    for key, val in [
        ("stt_success",         None),
        ("stt_logo_deleted",    False),
        ("stt_logo_pending",    None),   # アップロード済みバイト列（未保存）
        ("stt_logo_uploader_v", 0),      # file_uploader のキー番号（リセット用）
    ]:
        if key not in st.session_state:
            st.session_state[key] = val


# ─── バリデーション ──────────────────────────────────────────

def _validate(company_name: str, registration_number: str) -> list[str]:
    errors = []
    if not company_name.strip():
        errors.append("会社名は必須項目です。")
    rn = registration_number.strip()
    if rn and not _REG_NUM_RE.match(rn):
        errors.append("登録番号は「T」＋13桁の数字で入力してください（例：T1234567890123）。")
    return errors


# ─── メイン ─────────────────────────────────────────────────

def show():
    _init_state()
    st.header("⚙️ 設定")

    # 成功メッセージ
    if st.session_state["stt_success"]:
        st.success(st.session_state["stt_success"])
        st.session_state["stt_success"] = None

    info = db.get_company_info() or CompanyInfo()

    tab_company, tab_bank, tab_logo = st.tabs(["🏢 自社情報", "🏦 振込先", "🖼️ ロゴ"])

    # ─── タブ1：自社情報 ────────────────────────────────────
    with tab_company:
        _show_company_form(info)

    # ─── タブ2：振込先 ──────────────────────────────────────
    with tab_bank:
        _show_bank_form(info)

    # ─── タブ3：ロゴ ────────────────────────────────────────
    with tab_logo:
        _show_logo_section(info)


# ─── 自社情報フォーム ────────────────────────────────────────

def _show_company_form(info: CompanyInfo):
    st.subheader("自社情報の設定")
    st.caption("請求書のヘッダー・発行者欄に使用されます。")

    with st.form("company_info_form", border=True):
        company_name = st.text_input(
            "会社名 *",
            value=info.company_name,
            placeholder="株式会社〇〇",
        )

        address = st.text_area(
            "住所",
            value=info.address,
            height=80,
            placeholder="〒100-0001　東京都千代田区〇〇1-1-1",
        )

        col_phone, col_reg = st.columns(2)
        with col_phone:
            phone = st.text_input(
                "電話番号",
                value=info.phone,
                placeholder="03-0000-0000",
            )
        with col_reg:
            registration_number = st.text_input(
                "適格請求書発行事業者 登録番号",
                value=info.registration_number,
                placeholder="T1234567890123",
                help="インボイス制度の登録番号。「T」＋13桁の数字。未登録の場合は空白で構いません。",
            )

        submitted = st.form_submit_button(
            "💾 自社情報を保存する",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        errors = _validate(company_name, registration_number)
        if errors:
            for e in errors:
                st.error(e)
            return
        _save_partial(info,
                      company_name=company_name.strip(),
                      address=address.strip(),
                      phone=phone.strip(),
                      registration_number=registration_number.strip())
        st.session_state["stt_success"] = "✅ 自社情報を保存しました。"
        st.rerun()


# ─── 振込先フォーム ──────────────────────────────────────────

def _show_bank_form(info: CompanyInfo):
    st.subheader("振込先の設定")
    st.caption("入力すると請求書の下部に振込先欄が印刷されます。")

    with st.form("bank_form", border=True):
        col_bank, col_branch = st.columns(2)
        with col_bank:
            bank_name = st.text_input(
                "銀行名",
                value=info.bank_name,
                placeholder="〇〇銀行",
            )
        with col_branch:
            bank_branch = st.text_input(
                "支店名",
                value=info.bank_branch,
                placeholder="〇〇支店",
            )

        col_type, col_num, col_holder = st.columns([1, 2, 3])
        with col_type:
            account_type = st.selectbox(
                "口座種別",
                ["普通", "当座"],
                index=0 if info.account_type != "当座" else 1,
            )
        with col_num:
            account_number = st.text_input(
                "口座番号",
                value=info.account_number,
                placeholder="1234567",
            )
        with col_holder:
            account_holder = st.text_input(
                "口座名義（カタカナ）",
                value=info.account_holder,
                placeholder="カブシキガイシャ〇〇",
            )

        submitted = st.form_submit_button(
            "💾 振込先を保存する",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        _save_partial(info,
                      bank_name=bank_name.strip(),
                      bank_branch=bank_branch.strip(),
                      account_type=account_type,
                      account_number=account_number.strip(),
                      account_holder=account_holder.strip())
        st.session_state["stt_success"] = "✅ 振込先を保存しました。"
        st.rerun()

    # 振込先プレビュー
    if info.bank_name:
        with st.container(border=True):
            st.caption("請求書への表示イメージ")
            parts = [info.bank_name]
            if info.bank_branch:
                parts.append(info.bank_branch)
            parts += [info.account_type, info.account_number, info.account_holder]
            st.markdown(f"**【お振込先】**　{'　'.join(p for p in parts if p)}")


# ─── ロゴ管理 ────────────────────────────────────────────────

def _show_logo_section(info: CompanyInfo):
    st.subheader("ロゴ画像の管理")
    st.caption("PNG または JPG 形式。請求書のヘッダー左上に表示されます。推奨サイズ：横 300px 以上、縦 120px 以下。")

    pending: bytes | None = st.session_state["stt_logo_pending"]

    # ── プレビュー表示 ───────────────────────────────────────
    if pending is not None:
        # アップロード済みだが未保存の状態
        st.image(pending, width=250, caption="プレビュー（未保存）")
        col_save, col_cancel = st.columns(2)
        with col_save:
            if st.button("💾 このロゴを保存する", type="primary", use_container_width=True):
                os.makedirs("static", exist_ok=True)
                with open(LOGO_DEST, "wb") as f:
                    f.write(pending)
                _save_partial(info, logo_path=LOGO_DEST)
                # pending をクリアし、uploader ウィジェットをリセット（再ループ防止）
                st.session_state["stt_logo_pending"] = None
                st.session_state["stt_logo_uploader_v"] += 1
                st.session_state["stt_success"] = "✅ ロゴを保存しました。"
                st.rerun()
        with col_cancel:
            if st.button("✕ キャンセル", use_container_width=True):
                st.session_state["stt_logo_pending"] = None
                st.session_state["stt_logo_uploader_v"] += 1
                st.rerun()

    elif info.logo_path and os.path.exists(info.logo_path):
        # 保存済みのロゴを表示
        col_img, col_del = st.columns([3, 1])
        with col_img:
            st.image(info.logo_path, width=250, caption="現在のロゴ")
        with col_del:
            st.write("")
            st.write("")
            if st.button("🗑️ ロゴを削除", type="secondary", use_container_width=True):
                _delete_logo(info)
                st.session_state["stt_success"] = "✅ ロゴを削除しました。"
                st.rerun()
    else:
        st.info("ロゴは未登録です。")

    st.divider()

    # ── ファイルアップローダー ────────────────────────────────
    # pending がある間はアップローダーを非表示にして二重アップロードを防ぐ
    if pending is None:
        uploader_key = f"logo_uploader_{st.session_state['stt_logo_uploader_v']}"
        uploaded = st.file_uploader(
            "ロゴ画像をアップロード",
            type=["png", "jpg", "jpeg"],
            help="アップロード後にプレビューを確認し、「保存」ボタンで確定します。",
            key=uploader_key,
        )
        # アップロードされたらバイト列を session_state に保持してから rerun する。
        # rerun 後は pending is not None になるため uploader が非表示になり、
        # uploaded が評価されなくなる → 無限ループを防止。
        if uploaded is not None:
            st.session_state["stt_logo_pending"] = uploaded.read()
            st.rerun()


# ─── DB保存ヘルパー ──────────────────────────────────────────

def _save_partial(info: CompanyInfo, **kwargs) -> None:
    """既存の CompanyInfo に kwargs をマージして保存する。"""
    updated = CompanyInfo(
        company_name       = kwargs.get("company_name",        info.company_name),
        address            = kwargs.get("address",             info.address),
        phone              = kwargs.get("phone",               info.phone),
        registration_number= kwargs.get("registration_number", info.registration_number),
        bank_name          = kwargs.get("bank_name",           info.bank_name),
        bank_branch        = kwargs.get("bank_branch",         info.bank_branch),
        account_type       = kwargs.get("account_type",        info.account_type),
        account_number     = kwargs.get("account_number",      info.account_number),
        account_holder     = kwargs.get("account_holder",      info.account_holder),
        logo_path          = kwargs.get("logo_path",           info.logo_path),
    )
    db.save_company_info(updated)


def _delete_logo(info: CompanyInfo) -> None:
    if info.logo_path and os.path.exists(info.logo_path):
        os.remove(info.logo_path)
    _save_partial(info, logo_path=None)
