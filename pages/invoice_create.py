import os
import streamlit as st
import pandas as pd
from datetime import date, timedelta

import database as db
from models import Invoice, InvoiceItem
from utils import generate_invoice_number, calc_invoice_totals


# ─── 初期化 ─────────────────────────────────────────────────

def _init_state():
    for key, val in [
        ("inv_ver",          0),
        ("inv_success",      None),
        ("inv_last_saved_id", None),
    ]:
        if key not in st.session_state:
            st.session_state[key] = val


def _ensure_invoice_number(ver: int) -> None:
    """バージョンごとに1回だけ請求書番号を採番してsession_stateに格納する。"""
    num_key  = f"inv_num_{ver}"
    init_key = f"inv_num_init_{ver}"
    if not st.session_state.get(init_key):
        st.session_state[num_key] = generate_invoice_number(db.DB_PATH)
        st.session_state[init_key] = True


def _init_items_state(ver: int) -> None:
    """バージョンごとに明細行リストを初期化する。"""
    if f"inv_items_{ver}" not in st.session_state:
        st.session_state[f"inv_items_{ver}"]   = [
            {"id": 0, "品名": "", "数量": 1, "単価": 0, "税率": 10}
        ]
        st.session_state[f"inv_next_id_{ver}"] = 1


# ─── メイン ─────────────────────────────────────────────────

def show():
    _init_state()
    st.header("📝 請求書作成")

    # 保存成功メッセージ＋ダウンロードボタン
    if st.session_state["inv_success"]:
        st.success(st.session_state["inv_success"])
        st.session_state["inv_success"] = None

    if st.session_state["inv_last_saved_id"]:
        _show_download_section(st.session_state["inv_last_saved_id"])
        st.divider()

    customers = db.get_customers()
    if not customers:
        st.warning("顧客が登録されていません。まず「👥 顧客一覧」から顧客を登録してください。")
        return

    ver = st.session_state["inv_ver"]
    _ensure_invoice_number(ver)
    _init_items_state(ver)

    # ─── 基本情報 ────────────────────────────────────────────
    st.subheader("基本情報")

    customer_map = {c.company_name: c.id for c in customers}

    col_cust, col_num = st.columns([3, 2])
    with col_cust:
        selected_name = st.selectbox(
            "請求先 *",
            options=list(customer_map.keys()),
            index=None,
            placeholder="顧客を選択してください...",
            key=f"inv_customer_{ver}",
        )
    with col_num:
        invoice_number = st.text_input(
            "請求書番号",
            key=f"inv_num_{ver}",
            help="自動採番されます。手動で変更することもできます。",
        )

    col_issue, col_due, col_blank = st.columns([2, 2, 3])
    with col_issue:
        issue_date = st.date_input(
            "発行日",
            value=date.today(),
            key=f"inv_issue_{ver}",
        )
    with col_due:
        due_date = st.date_input(
            "支払期限",
            value=date.today() + timedelta(days=30),
            key=f"inv_due_{ver}",
        )

    # ─── 明細入力（手動行管理エディター） ────────────────────
    st.subheader("明細")
    current_rows = _show_items_editor(ver)

    # ─── リアルタイム合計 ─────────────────────────────────────
    valid_rows = _get_valid_rows(current_rows)
    totals     = calc_invoice_totals(valid_rows)
    _show_totals(totals, valid_rows)

    # ─── 備考 ────────────────────────────────────────────────
    st.subheader("備考")
    notes = st.text_area(
        "備考",
        height=80,
        placeholder="例）お振込の際は振込手数料をご負担ください。\n支払期限を過ぎた場合はご連絡ください。",
        label_visibility="collapsed",
        key=f"inv_notes_{ver}",
    )

    # ─── 保存ボタン ──────────────────────────────────────────
    st.divider()

    save_errors = _validate(selected_name, invoice_number, valid_rows)
    if save_errors and selected_name is not None:
        for e in save_errors:
            st.warning(e)

    if st.button(
        "💾 請求書を保存する",
        type="primary",
        use_container_width=True,
        disabled=bool(save_errors),
    ):
        _save(
            selected_name=selected_name,
            invoice_number=invoice_number,
            issue_date=issue_date,
            due_date=due_date,
            notes=notes,
            valid_rows=valid_rows,
            totals=totals,
            customer_map=customer_map,
        )


# ─── 明細エディター（手動行管理） ────────────────────────────
#
# st.data_editor は「Add row時のNone TypeError」「フォーカス固定スクロールバグ」
# の既知問題があるため、session_state + 個別ウィジェットで実装する。
# 各行には安定した一意ID（rid）を割り当て、行追加・削除後もキーが崩れない。

def _show_items_editor(ver: int) -> list[dict]:
    """明細行を表示・編集し、現在の全行データをリストで返す。"""
    items = st.session_state[f"inv_items_{ver}"]

    # ── ヘッダー ──────────────────────────────────────────────
    hc = st.columns([5, 1.5, 2.5, 1.5, 0.8])
    for col, label in zip(hc, ["品名", "数量", "単価（円）", "税率", ""]):
        col.caption(label)

    to_delete: int | None = None

    # ── 明細行 ────────────────────────────────────────────────
    for item in items:
        rid  = item["id"]
        c0, c1, c2, c3, c4 = st.columns([5, 1.5, 2.5, 1.5, 0.8])

        with c0:
            # key が SS に既存の場合は SS 値が優先されるため value は初期値のみ機能する
            st.text_input(
                "品名",
                value=item["品名"],
                placeholder="商品名・サービス名を入力",
                label_visibility="collapsed",
                key=f"iname_{ver}_{rid}",
            )
        with c1:
            st.number_input(
                "数量",
                value=int(item["数量"] or 1),
                min_value=1,
                step=1,
                format="%d",
                label_visibility="collapsed",
                key=f"iqty_{ver}_{rid}",
            )
        with c2:
            st.number_input(
                "単価",
                value=float(item["単価"] or 0),
                min_value=0.0,
                step=100.0,
                format="%.0f",
                label_visibility="collapsed",
                key=f"iprice_{ver}_{rid}",
            )
        with c3:
            st.selectbox(
                "税率",
                options=[10, 8],
                index=0 if (item["税率"] or 10) == 10 else 1,
                format_func=lambda x: f"{x}%",
                label_visibility="collapsed",
                key=f"itax_{ver}_{rid}",
            )
        with c4:
            # 1行しかない場合は削除不可
            if len(items) > 1:
                if st.button("🗑️", key=f"idel_{ver}_{rid}", help="この行を削除"):
                    to_delete = rid

    # ── 行追加ボタン ──────────────────────────────────────────
    col_add, _ = st.columns([2, 8])
    with col_add:
        if st.button("＋ 行を追加", key=f"iadd_{ver}"):
            _sync_items_from_widgets(ver)
            nid = st.session_state[f"inv_next_id_{ver}"]
            st.session_state[f"inv_items_{ver}"].append(
                {"id": nid, "品名": "", "数量": 1, "単価": 0, "税率": 10}
            )
            st.session_state[f"inv_next_id_{ver}"] = nid + 1
            st.rerun()

    # ── 行削除 ────────────────────────────────────────────────
    if to_delete is not None:
        _sync_items_from_widgets(ver)
        st.session_state[f"inv_items_{ver}"] = [
            r for r in st.session_state[f"inv_items_{ver}"]
            if r["id"] != to_delete
        ]
        st.rerun()

    # ── 現在値を返す（SS から読み取り）────────────────────────
    # ウィジェット描画後は st.session_state[key] に最新値が入っている
    result = []
    for item in st.session_state[f"inv_items_{ver}"]:
        rid = item["id"]
        result.append({
            "品名": st.session_state.get(f"iname_{ver}_{rid}", ""),
            "数量": st.session_state.get(f"iqty_{ver}_{rid}", 1),
            "単価": st.session_state.get(f"iprice_{ver}_{rid}", 0),
            "税率": st.session_state.get(f"itax_{ver}_{rid}", 10),
        })
    return result


def _sync_items_from_widgets(ver: int) -> None:
    """ウィジェットの現在値を items リストに同期する（行追加・削除前に必ず呼ぶ）。"""
    for item in st.session_state.get(f"inv_items_{ver}", []):
        rid = item["id"]
        item["品名"] = st.session_state.get(f"iname_{ver}_{rid}", item["品名"])
        item["数量"] = st.session_state.get(f"iqty_{ver}_{rid}", item["数量"])
        item["単価"] = st.session_state.get(f"iprice_{ver}_{rid}", item["単価"])
        item["税率"] = st.session_state.get(f"itax_{ver}_{rid}", item["税率"])


# ─── 補助関数 ────────────────────────────────────────────────

def _show_download_section(invoice_id: int) -> None:
    """保存済み請求書のPDF/Wordダウンロードボタンを表示する。"""
    from invoice_generator import generate_invoice_pdf, generate_invoice_docx

    with st.container(border=True):
        st.caption("📥 保存した請求書をダウンロード")
        col_pdf, col_docx, col_clear = st.columns([2, 2, 1])

        with col_pdf:
            try:
                pdf_path = generate_invoice_pdf(invoice_id)
                with open(pdf_path, "rb") as f:
                    st.download_button(
                        "📄 PDFをダウンロード",
                        data=f.read(),
                        file_name=os.path.basename(pdf_path),
                        mime="application/pdf",
                        use_container_width=True,
                        key=f"dl_pdf_{invoice_id}",
                    )
            except Exception as e:
                st.error(f"PDF生成エラー: {e}")

        with col_docx:
            try:
                docx_path = generate_invoice_docx(invoice_id)
                with open(docx_path, "rb") as f:
                    st.download_button(
                        "📝 Wordをダウンロード",
                        data=f.read(),
                        file_name=os.path.basename(docx_path),
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        use_container_width=True,
                        key=f"dl_docx_{invoice_id}",
                    )
            except Exception as e:
                st.error(f"Word生成エラー: {e}")

        with col_clear:
            if st.button("✕", help="このパネルを閉じる", use_container_width=True):
                st.session_state["inv_last_saved_id"] = None
                st.rerun()


def _get_valid_rows(rows: list[dict]) -> list[dict]:
    """品名が入力されている行だけを返す。None 値はデフォルトに置換する。"""
    result = []
    for row in rows:
        name = str(row.get("品名") or "").strip()
        if not name:
            continue
        # None / 空文字 / 0 を安全にデフォルト値へ変換
        qty   = int(row.get("数量")   or 1)
        price = float(row.get("単価") or 0)
        rate  = int(row.get("税率")   or 10)
        result.append({
            "item_name":  name,
            "quantity":   max(qty, 1),
            "unit_price": max(price, 0.0),
            "tax_rate":   rate if rate in (8, 10) else 10,
        })
    return result


def _validate(selected_name, invoice_number: str, valid_rows: list) -> list[str]:
    errors = []
    if not selected_name:
        errors.append("請求先（顧客）を選択してください。")
    if not invoice_number.strip():
        errors.append("請求書番号を入力してください。")
    if not valid_rows:
        errors.append("品名を入力した明細行を1件以上追加してください。")
    return errors


def _show_totals(totals: dict, valid_rows: list) -> None:
    """明細プレビューと合計金額をセクション表示する。"""
    st.divider()

    if not valid_rows:
        st.caption("明細に品名を入力すると合計が自動計算されます。")
        return

    col_items, col_summary = st.columns([3, 2])

    # 左：明細プレビュー
    with col_items:
        st.caption("明細プレビュー")
        preview_df = pd.DataFrame([
            {
                "品名":      r["item_name"],
                "数量":      r["quantity"],
                "単価（円）": r["unit_price"],
                "金額（円）": r["quantity"] * r["unit_price"],
                "税率":      f"{r['tax_rate']}%",
            }
            for r in valid_rows
        ])
        st.dataframe(
            preview_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "単価（円）": st.column_config.NumberColumn(format="¥%d"),
                "金額（円）": st.column_config.NumberColumn(format="¥%d"),
            },
        )

    # 右：合計サマリー
    with col_summary:
        st.caption("合計")
        st.markdown(f"**小計（税抜）：** ¥ {totals['subtotal']:,.0f}")
        if totals["tax_10"] > 0:
            st.markdown(f"**消費税（10%）：** ¥ {totals['tax_10']:,.0f}")
        if totals["tax_8"] > 0:
            st.markdown(f"**消費税（8% 軽減）：** ¥ {totals['tax_8']:,.0f}")
        st.markdown("---")
        st.markdown(f"### ¥ {totals['total']:,.0f}")
        st.caption("合計（税込）")


def _save(
    selected_name: str,
    invoice_number: str,
    issue_date: date,
    due_date: date,
    notes: str,
    valid_rows: list,
    totals: dict,
    customer_map: dict,
) -> None:
    inv = Invoice(
        invoice_number=invoice_number.strip(),
        customer_id=customer_map[selected_name],
        issue_date=issue_date,
        due_date=due_date,
        notes=notes.strip(),
        subtotal=totals["subtotal"],
        tax_10=totals["tax_10"],
        tax_8=totals["tax_8"],
        total=totals["total"],
    )
    inv_items = [
        InvoiceItem(
            item_name=r["item_name"],
            quantity=r["quantity"],
            unit_price=r["unit_price"],
            tax_rate=r["tax_rate"],
            amount=r["quantity"] * r["unit_price"],
        )
        for r in valid_rows
    ]

    try:
        invoice_id = db.create_invoice(inv, inv_items)
    except Exception as e:
        if "UNIQUE constraint" in str(e):
            st.error(
                f"請求書番号「{invoice_number.strip()}」は既に使用されています。"
                "別の番号に変更してください。"
            )
        else:
            st.error(f"保存に失敗しました: {e}")
        return

    # 成功 → inv_ver を上げてフォームをリセット
    st.session_state["inv_last_saved_id"] = invoice_id
    st.session_state["inv_ver"]    += 1
    st.session_state["inv_success"] = (
        f"✅ 請求書 **{invoice_number.strip()}** を保存しました。"
        f"（合計: ¥{totals['total']:,.0f}）"
    )
    st.rerun()
