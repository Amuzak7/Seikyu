import re
import streamlit as st
import pandas as pd
import database as db
from models import Customer


# ─── セッション状態初期化 ────────────────────────────────────

def _init_state():
    for key, default in [
        ("cust_mode",          None),   # None | "add" | "edit" | "delete" | "deactivate"
        ("cust_edit_id",       None),
        ("cust_success",       None),
        ("cust_show_inactive", False),  # 無効顧客を一覧に表示するか
    ]:
        if key not in st.session_state:
            st.session_state[key] = default


# ─── バリデーション ──────────────────────────────────────────

def _validate(company_name: str, email: str) -> list[str]:
    errors = []
    if not company_name.strip():
        errors.append("会社名は必須項目です。")
    if email.strip() and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email.strip()):
        errors.append("メールアドレスの形式が正しくありません。")
    return errors


# ─── メイン ─────────────────────────────────────────────────

def show():
    _init_state()
    st.header("👥 顧客一覧")

    # 成功メッセージ（rerun後に表示して消す）
    if st.session_state["cust_success"]:
        st.success(st.session_state["cust_success"])
        st.session_state["cust_success"] = None

    # 検索バー + フィルター + 新規登録ボタン
    col_search, col_toggle, col_btn = st.columns([4, 2, 1])
    with col_search:
        search = st.text_input(
            "検索",
            placeholder="🔍 会社名・担当者名で検索",
            label_visibility="collapsed",
        )
    with col_toggle:
        show_inactive = st.checkbox(
            "無効な顧客も表示",
            value=st.session_state["cust_show_inactive"],
            key="cust_show_inactive_widget",
        )
        st.session_state["cust_show_inactive"] = show_inactive
    with col_btn:
        if st.button(
            "＋ 新規登録",
            type="primary",
            use_container_width=True,
            disabled=st.session_state["cust_mode"] is not None,
        ):
            st.session_state["cust_mode"] = "add"
            st.session_state["cust_edit_id"] = None
            st.rerun()

    # active_only はチェックボックスの逆
    customers = db.get_customers(search, active_only=not show_inactive)

    # ─── 顧客テーブル ────────────────────────────────────────
    if not customers:
        if search:
            st.info(f"「{search}」に一致する顧客が見つかりませんでした。")
        else:
            st.info("顧客が登録されていません。「＋ 新規登録」から追加してください。")
    else:
        active_count   = sum(1 for c in customers if c.is_active)
        inactive_count = sum(1 for c in customers if not c.is_active)

        if show_inactive and inactive_count:
            st.caption(f"全 {len(customers)} 件（有効 {active_count} 件 / 無効 {inactive_count} 件）")
        else:
            st.caption(f"全 {len(customers)} 件")

        # 無効顧客は会社名に「（無効）」を付けてグレーアウト
        df_rows = []
        for c in customers:
            name = c.company_name if c.is_active else f"{c.company_name}（無効）"
            df_rows.append({
                "状態":        "✅ 有効" if c.is_active else "⛔ 無効",
                "会社名":      name,
                "担当者":      c.contact_person,
                "電話番号":    c.phone,
                "メールアドレス": c.email,
            })
        df = pd.DataFrame(df_rows)

        # 無効行をグレーに
        def _row_style(row):
            return (
                ["color:#aaaaaa"] * len(row)
                if customers[row.name].is_active == 0
                else [""] * len(row)
            )

        event = st.dataframe(
            df.style.apply(_row_style, axis=1),
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            column_config={
                "状態":          st.column_config.TextColumn(width="small"),
                "会社名":        st.column_config.TextColumn(width="medium"),
                "担当者":        st.column_config.TextColumn(width="small"),
                "電話番号":      st.column_config.TextColumn(width="small"),
                "メールアドレス": st.column_config.TextColumn(width="medium"),
            },
        )

        # 行選択時のアクションボタン
        sel_rows = event.selection.rows if event.selection else []
        if sel_rows:
            selected = customers[sel_rows[0]]
            st.caption(f"選択中：**{selected.company_name}**")
            _show_action_buttons(selected)

    # ─── アクションパネル ────────────────────────────────────
    mode = st.session_state["cust_mode"]
    if mode in ("add", "edit"):
        st.divider()
        _show_form(mode, customers if customers else [])
    elif mode == "delete":
        st.divider()
        _show_delete_confirm()
    elif mode == "deactivate":
        st.divider()
        _show_deactivate_confirm()


# ─── 行選択アクションボタン ──────────────────────────────────

def _show_action_buttons(selected: Customer):
    is_mode_open = st.session_state["cust_mode"] is not None

    if selected.is_active:
        # 有効顧客：編集 / 無効化 / 削除
        col_edit, col_deact, col_del, _ = st.columns([1, 1, 1, 5])
        with col_edit:
            if st.button(
                "✏️ 編集",
                use_container_width=True,
                disabled=is_mode_open,
            ):
                st.session_state["cust_mode"]    = "edit"
                st.session_state["cust_edit_id"] = selected.id
                st.rerun()
        with col_deact:
            if st.button(
                "🚫 無効化",
                use_container_width=True,
                disabled=is_mode_open,
            ):
                st.session_state["cust_mode"]    = "deactivate"
                st.session_state["cust_edit_id"] = selected.id
                st.rerun()
        with col_del:
            if st.button(
                "🗑️ 削除",
                type="secondary",
                use_container_width=True,
                disabled=is_mode_open,
            ):
                st.session_state["cust_mode"]    = "delete"
                st.session_state["cust_edit_id"] = selected.id
                st.rerun()
    else:
        # 無効顧客：有効化 / 削除のみ
        col_act, col_del, _ = st.columns([1, 1, 6])
        with col_act:
            if st.button(
                "✅ 有効化",
                type="primary",
                use_container_width=True,
                disabled=is_mode_open,
            ):
                db.activate_customer(selected.id)
                st.session_state["cust_success"] = (
                    f"✅ 顧客「{selected.company_name}」を有効化しました。"
                )
                st.rerun()
        with col_del:
            if st.button(
                "🗑️ 削除",
                type="secondary",
                use_container_width=True,
                disabled=is_mode_open,
            ):
                st.session_state["cust_mode"]    = "delete"
                st.session_state["cust_edit_id"] = selected.id
                st.rerun()


# ─── 登録・編集フォーム ──────────────────────────────────────

def _show_form(mode: str, customers: list):
    cid      = st.session_state["cust_edit_id"]
    existing = db.get_customer(cid) if cid else None
    title    = "＋ 新規顧客登録" if mode == "add" else "✏️ 顧客情報を編集"
    st.subheader(title)

    with st.form("customer_form", border=True):
        col_a, col_b = st.columns(2)
        with col_a:
            company_name = st.text_input(
                "会社名 *",
                value=existing.company_name if existing else "",
                placeholder="株式会社〇〇",
            )
        with col_b:
            contact_person = st.text_input(
                "担当者名",
                value=existing.contact_person if existing else "",
                placeholder="山田 太郎",
            )

        col_c, col_d = st.columns(2)
        with col_c:
            phone = st.text_input(
                "電話番号",
                value=existing.phone if existing else "",
                placeholder="03-0000-0000",
            )
        with col_d:
            email = st.text_input(
                "メールアドレス",
                value=existing.email if existing else "",
                placeholder="contact@example.com",
            )

        address = st.text_area(
            "住所",
            value=existing.address if existing else "",
            height=80,
            placeholder="〒100-0001 東京都千代田区〇〇1-1-1",
        )
        notes = st.text_area(
            "備考",
            value=existing.notes if existing else "",
            height=60,
            placeholder="任意のメモ（支払条件など）",
        )

        col_save, col_cancel, _ = st.columns([2, 2, 6])
        with col_save:
            submitted = st.form_submit_button(
                "💾 保存する", type="primary", use_container_width=True
            )
        with col_cancel:
            cancelled = st.form_submit_button("キャンセル", use_container_width=True)

    if submitted:
        errors = _validate(company_name, email)
        if errors:
            for e in errors:
                st.error(e)
            return

        # 重複会社名チェック（警告のみ・ブロックしない）
        other_names = [c.company_name for c in customers if c.id != cid]
        if company_name.strip() in other_names:
            st.warning(f"「{company_name.strip()}」と同じ会社名が既に登録されています。続けて保存しますか？")

        c = Customer(
            id=cid,
            company_name=company_name.strip(),
            contact_person=contact_person.strip(),
            phone=phone.strip(),
            email=email.strip(),
            address=address.strip(),
            notes=notes.strip(),
        )
        if mode == "add":
            db.add_customer(c)
            st.session_state["cust_success"] = f"✅ 顧客「{c.company_name}」を登録しました。"
        else:
            db.update_customer(c)
            st.session_state["cust_success"] = f"✅ 顧客「{c.company_name}」の情報を更新しました。"

        st.session_state["cust_mode"]    = None
        st.session_state["cust_edit_id"] = None
        st.rerun()

    if cancelled:
        st.session_state["cust_mode"]    = None
        st.session_state["cust_edit_id"] = None
        st.rerun()


# ─── 無効化確認 ──────────────────────────────────────────────

def _show_deactivate_confirm():
    cid    = st.session_state["cust_edit_id"]
    target = db.get_customer(cid)
    if not target:
        st.session_state["cust_mode"] = None
        return

    inv_count = db.get_invoice_count_by_customer(cid)

    st.subheader("🚫 顧客の無効化")
    st.warning(
        f"**{target.company_name}** を無効化しますか？\n\n"
        "無効化すると顧客一覧から非表示になります。"
        f"{'この顧客には ' + str(inv_count) + ' 件の請求書があります。' if inv_count else ''}"
        "過去の請求書履歴はすべて保持されます。\n\n"
        "あとから「有効化」ボタンでいつでも元に戻せます。",
    )

    col_yes, col_no, _ = st.columns([2, 2, 6])
    with col_yes:
        if st.button("はい、無効化する", type="primary", use_container_width=True):
            db.deactivate_customer(cid)
            st.session_state["cust_success"] = (
                f"🚫 顧客「{target.company_name}」を無効化しました。"
            )
            st.session_state["cust_mode"]    = None
            st.session_state["cust_edit_id"] = None
            st.rerun()
    with col_no:
        if st.button("キャンセル", use_container_width=True):
            st.session_state["cust_mode"]    = None
            st.session_state["cust_edit_id"] = None
            st.rerun()


# ─── 削除確認 ────────────────────────────────────────────────

def _show_delete_confirm():
    cid    = st.session_state["cust_edit_id"]
    target = db.get_customer(cid)
    if not target:
        st.session_state["cust_mode"] = None
        return

    st.subheader("🗑️ 顧客削除の確認")

    inv_count = db.get_invoice_count_by_customer(cid)

    if inv_count > 0:
        # 請求書あり → 削除ブロック・無効化を提案
        st.error(
            f"**{target.company_name}** には請求書が **{inv_count} 件** "
            "登録されているため削除できません。\n\n"
            "請求書の履歴を残すには、削除ではなく **「🚫 無効化」** をご利用ください。"
        )
        if st.button("閉じる", use_container_width=False):
            st.session_state["cust_mode"]    = None
            st.session_state["cust_edit_id"] = None
            st.rerun()
        return

    # 請求書なし → 通常の削除確認
    st.warning(
        f"**{target.company_name}** を削除しますか？\n\n"
        "この操作は取り消せません。"
    )

    col_yes, col_no, _ = st.columns([2, 2, 6])
    with col_yes:
        if st.button("はい、削除する", type="primary", use_container_width=True):
            try:
                db.delete_customer(cid)
                st.session_state["cust_success"] = (
                    f"🗑️ 顧客「{target.company_name}」を削除しました。"
                )
            except Exception as e:
                st.error(f"削除できませんでした：{e}")
            st.session_state["cust_mode"]    = None
            st.session_state["cust_edit_id"] = None
            st.rerun()
    with col_no:
        if st.button("キャンセル", use_container_width=True):
            st.session_state["cust_mode"]    = None
            st.session_state["cust_edit_id"] = None
            st.rerun()
