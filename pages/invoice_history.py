import os
import streamlit as st
import pandas as pd
from datetime import date

import database as db


# ─── ユーティリティ ──────────────────────────────────────────

def _customer_label(inv: dict) -> str:
    """請求書dictから顧客表示名を返す。
    - 削除済み顧客 → 「（削除済み）」
    - 無効化された顧客 → 「〇〇株式会社（無効）」
    - 通常 → 顧客名
    """
    name = inv.get("customer_name")
    if not name:
        return "（削除済み）"
    if inv.get("customer_is_active") == 0:
        return f"{name}（無効）"
    return name


# ─── セッション状態初期化 ────────────────────────────────────

def _init_state():
    for key, val in [
        ("hist_search",    ""),
        ("hist_date_from", None),
        ("hist_date_to",   None),
        ("hist_amt_min",   None),
        ("hist_amt_max",   None),
        ("hist_show_adv",  False),
        ("hist_files",     {}),     # {f"{inv_id}_{fmt}": filepath}
    ]:
        if key not in st.session_state:
            st.session_state[key] = val


# ─── フィルタリング ──────────────────────────────────────────

def _apply_filters(invoices: list[dict]) -> list[dict]:
    result = invoices
    search   = st.session_state.get("hist_search", "")
    df_from  = st.session_state.get("hist_date_from")
    df_to    = st.session_state.get("hist_date_to")
    amt_min  = st.session_state.get("hist_amt_min")
    amt_max  = st.session_state.get("hist_amt_max")

    if search:
        s = search.lower()
        result = [i for i in result
                  if s in (i.get("customer_name") or "").lower()
                  or s in i["invoice_number"].lower()]

    if df_from:
        result = [i for i in result if (i.get("issue_date") or "") >= str(df_from)]
    if df_to:
        result = [i for i in result if (i.get("issue_date") or "") <= str(df_to)]
    if amt_min is not None:
        result = [i for i in result if i["total"] >= amt_min]
    if amt_max is not None:
        result = [i for i in result if i["total"] <= amt_max]

    return result


def _has_filter() -> bool:
    return bool(
        st.session_state.get("hist_search")
        or st.session_state.get("hist_date_from")
        or st.session_state.get("hist_date_to")
        or st.session_state.get("hist_amt_min") is not None
        or st.session_state.get("hist_amt_max") is not None
    )


# ─── メイン ─────────────────────────────────────────────────

def show():
    _init_state()
    st.header("📋 請求書履歴")

    _show_filter_panel()

    all_invoices = db.get_invoices()
    invoices     = _apply_filters(all_invoices)

    if not invoices:
        if _has_filter():
            st.info("絞り込み条件に一致する請求書が見つかりませんでした。")
        else:
            st.info("請求書がまだありません。「📝 請求書作成」から作成してください。")
        return

    # ─── 件数表示 ────────────────────────────────────────────
    if len(invoices) < len(all_invoices):
        st.caption(f"{len(invoices)} 件（全 {len(all_invoices)} 件中）")
    else:
        st.caption(f"全 {len(invoices)} 件")

    # ─── 請求書テーブル ──────────────────────────────────────
    df = pd.DataFrame([
        {
            "請求書番号":  inv["invoice_number"],
            "顧客名":      _customer_label(inv),
            "発行日":      inv["issue_date"] or "",
            "支払期限":    inv["due_date"] or "",
            "合計（税込）": inv["total"],
        }
        for inv in invoices
    ])

    event = st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        column_config={
            "請求書番号": st.column_config.TextColumn(width="medium"),
            "顧客名":     st.column_config.TextColumn(width="medium"),
            "発行日":     st.column_config.TextColumn(width="small"),
            "支払期限":   st.column_config.TextColumn(width="small"),
            "合計（税込）": st.column_config.NumberColumn(
                width="medium", format="¥%d"
            ),
        },
    )

    # ─── 行選択 → 詳細表示 ──────────────────────────────────
    sel_rows = event.selection.rows if event.selection else []
    if sel_rows:
        selected_inv = invoices[sel_rows[0]]
        details      = db.get_invoice_details(selected_inv["id"])
        st.divider()
        _show_detail(details)


# ─── フィルターパネル ────────────────────────────────────────

def _show_filter_panel():
    col_search, col_adv, col_reset = st.columns([5, 1, 1])

    with col_search:
        st.session_state["hist_search"] = st.text_input(
            "検索",
            placeholder="🔍 顧客名・請求書番号で検索",
            label_visibility="collapsed",
            value=st.session_state["hist_search"],
            key="hist_search_widget",
        )

    with col_adv:
        adv_label = "▲ 閉じる" if st.session_state["hist_show_adv"] else "詳細絞込"
        if st.button(adv_label, use_container_width=True):
            st.session_state["hist_show_adv"] = not st.session_state["hist_show_adv"]
            st.rerun()

    with col_reset:
        if st.button("リセット", use_container_width=True, disabled=not _has_filter()):
            st.session_state.update({
                "hist_search":    "",
                "hist_date_from": None,
                "hist_date_to":   None,
                "hist_amt_min":   None,
                "hist_amt_max":   None,
                "hist_show_adv":  False,
            })
            st.rerun()

    if st.session_state["hist_show_adv"]:
        with st.container(border=True):
            st.caption("詳細フィルター")
            col_df, col_dt, col_sep, col_amin, col_amax = st.columns([2, 2, 0.3, 2, 2])

            with col_df:
                df_from = st.date_input(
                    "発行日（開始）",
                    value=st.session_state["hist_date_from"],
                    key="hist_df_from_widget",
                )
                st.session_state["hist_date_from"] = df_from if df_from else None

            with col_dt:
                df_to = st.date_input(
                    "発行日（終了）",
                    value=st.session_state["hist_date_to"],
                    key="hist_df_to_widget",
                )
                st.session_state["hist_date_to"] = df_to if df_to else None

            with col_sep:
                st.write("")

            with col_amin:
                amt_min_val = st.session_state["hist_amt_min"]
                amt_min = st.number_input(
                    "合計 下限（円）",
                    value=float(amt_min_val) if amt_min_val is not None else 0.0,
                    min_value=0.0,
                    step=10000.0,
                    format="%.0f",
                    key="hist_amt_min_widget",
                )
                st.session_state["hist_amt_min"] = amt_min if amt_min > 0 else None

            with col_amax:
                amt_max_val = st.session_state["hist_amt_max"]
                amt_max = st.number_input(
                    "合計 上限（円）",
                    value=float(amt_max_val) if amt_max_val is not None else 0.0,
                    min_value=0.0,
                    step=10000.0,
                    format="%.0f",
                    key="hist_amt_max_widget",
                )
                st.session_state["hist_amt_max"] = amt_max if amt_max > 0 else None

            # アクティブフィルターのバッジ表示
            active = []
            if st.session_state["hist_date_from"]:
                active.append(f"発行日 ≥ {st.session_state['hist_date_from']}")
            if st.session_state["hist_date_to"]:
                active.append(f"発行日 ≤ {st.session_state['hist_date_to']}")
            if st.session_state["hist_amt_min"]:
                active.append(f"合計 ≥ ¥{int(st.session_state['hist_amt_min']):,}")
            if st.session_state["hist_amt_max"]:
                active.append(f"合計 ≤ ¥{int(st.session_state['hist_amt_max']):,}")
            if active:
                st.caption("適用中：" + "　|　".join(active))


# ─── 詳細パネル ──────────────────────────────────────────────

def _show_detail(details: dict):
    with st.container(border=True):
        # ヘッダー行
        col_title, col_badge = st.columns([3, 1])
        with col_title:
            st.subheader(f"📄 {details['invoice_number']}")
        with col_badge:
            total_str = f"¥{int(details['total']):,}"
            st.markdown(
                f"<div style='text-align:right;font-size:1.3rem;font-weight:bold;color:#1e4d7b'>{total_str}</div>",
                unsafe_allow_html=True,
            )

        # 基本情報
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f"**顧客名**  \n{details.get('customer_name') or '（削除済み）'}")
        with col2:
            st.markdown(f"**発行日**  \n{details.get('issue_date', '—')}")
            st.markdown(f"**支払期限**  \n{details.get('due_date', '—')}")
        with col3:
            st.markdown(f"**小計（税抜）**  \n¥{int(details['subtotal']):,}")
            if details.get("tax_10"):
                st.markdown(f"**消費税（10%）**  \n¥{int(details['tax_10']):,}")
            if details.get("tax_8"):
                st.markdown(f"**消費税（8% 軽減）**  \n¥{int(details['tax_8']):,}")

        if details.get("notes"):
            st.caption(f"備考：{details['notes']}")

        # 明細テーブル
        st.divider()
        items_df = pd.DataFrame([
            {
                "品名":      it["item_name"],
                "数量":      it["quantity"],
                "単価（円）": it["unit_price"],
                "金額（円）": it["amount"],
                "税率":      f"{it['tax_rate']}%",
            }
            for it in details["items"]
        ])
        st.dataframe(
            items_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "単価（円）": st.column_config.NumberColumn(format="¥%d"),
                "金額（円）": st.column_config.NumberColumn(format="¥%d"),
            },
        )

        # ダウンロードボタン
        st.divider()
        col_pdf, col_docx = st.columns(2)
        with col_pdf:
            _download_or_generate(details, "pdf")
        with col_docx:
            _download_or_generate(details, "docx")


# ─── ダウンロード / 生成ボタン ────────────────────────────────

def _download_or_generate(details: dict, fmt: str) -> None:
    """
    ファイルが存在すればダウンロードボタンを直接表示する。
    未生成の場合は「生成」ボタンを表示し、クリック後にダウンロードボタンを出す。
    """
    inv_id   = details["id"]
    ss_key   = f"hist_{fmt}_{inv_id}"
    is_pdf   = fmt == "pdf"
    gen_label  = "📄 PDF を生成する"  if is_pdf else "📝 Word を生成する"
    dl_label   = "⬇️ PDF をダウンロード" if is_pdf else "⬇️ Word をダウンロード"
    mime       = "application/pdf" if is_pdf else (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    btn_type   = "primary" if is_pdf else "secondary"

    # DBに記録済みのパスがあればsession_stateに反映（ページ再起動後も有効）
    existing = details.get(f"{fmt}_path")
    if existing and os.path.exists(existing):
        st.session_state["hist_files"][ss_key] = existing

    file_path = st.session_state["hist_files"].get(ss_key)

    if file_path and os.path.exists(file_path):
        # 生成済み → ダウンロードボタン表示
        with open(file_path, "rb") as f:
            st.download_button(
                dl_label,
                data=f.read(),
                file_name=os.path.basename(file_path),
                mime=mime,
                use_container_width=True,
                type=btn_type,
                key=f"dl_{fmt}_{inv_id}",
            )
        # 再生成オプション（小さなボタン）
        if st.button("🔄 再生成", key=f"regen_{fmt}_{inv_id}",
                     help="ファイルを削除して再生成します"):
            if os.path.exists(file_path):
                os.remove(file_path)
            st.session_state["hist_files"].pop(ss_key, None)
            db.update_invoice_paths(
                inv_id,
                pdf_path=None if is_pdf else details.get("pdf_path"),
                docx_path=None if not is_pdf else details.get("docx_path"),
            )
            st.rerun()
    else:
        # 未生成 → 生成ボタン表示
        if st.button(gen_label, use_container_width=True, type=btn_type,
                     key=f"gen_{fmt}_{inv_id}"):
            with st.spinner("生成しています..."):
                try:
                    from invoice_generator import generate_invoice_pdf, generate_invoice_docx
                    path = generate_invoice_pdf(inv_id) if is_pdf else generate_invoice_docx(inv_id)
                    st.session_state["hist_files"][ss_key] = path
                    st.rerun()
                except Exception as e:
                    st.error(f"生成エラー: {e}")
