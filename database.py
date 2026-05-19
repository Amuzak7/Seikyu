import os
import sqlite3
from datetime import datetime, date
from typing import Optional
from models import CompanyInfo, Customer, Invoice, InvoiceItem

# ─── 環境変数ロード ──────────────────────────────────────────
# python-dotenv がインストール済みなら .env を自動読み込み
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # 未インストール時は os.environ の既存値をそのまま使用

# ─── モード設定 ──────────────────────────────────────────────
# DEMO_MODE=true  : 起動時にDBリセット・インメモリ（再起動でデータ消去）
# DEMO_MODE=false : 通常の永続化モード（デフォルト）
DEMO_MODE: bool = os.getenv("DEMO_MODE", "false").lower() == "true"
DB_PATH:   str  = os.getenv("DB_PATH", "seikyu.db")

# ─── デモモード：プロセス内シングルトン接続 ──────────────────
# sqlite3.connect(":memory:") は呼ぶたびに別のDBを作るため、
# デモモードでは1つの接続をプロセス全体で共有する。
_demo_conn: sqlite3.Connection | None = None


def _get_demo_conn() -> sqlite3.Connection:
    global _demo_conn
    if _demo_conn is None:
        _demo_conn = sqlite3.connect(":memory:", check_same_thread=False)
        _demo_conn.row_factory = sqlite3.Row
        _demo_conn.execute("PRAGMA foreign_keys = ON")
    return _demo_conn


def get_conn() -> sqlite3.Connection:
    if DEMO_MODE:
        return _get_demo_conn()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _release_conn(conn: sqlite3.Connection) -> None:
    """接続を解放する。デモモードではシングルトンを閉じない。"""
    if not DEMO_MODE:
        conn.close()


# ─── DB初期化 ────────────────────────────────────────────────

def init_db() -> None:
    conn = get_conn()
    try:
        if DEMO_MODE:
            # デモモード：毎回テーブルを DROP → CREATE で完全リセット
            conn.executescript("""
                DROP TABLE IF EXISTS invoice_items;
                DROP TABLE IF EXISTS invoices;
                DROP TABLE IF EXISTS customers;
                DROP TABLE IF EXISTS companies;
            """)

        conn.executescript("""
            CREATE TABLE IF NOT EXISTS companies (
                id                  INTEGER PRIMARY KEY,
                company_name        TEXT,
                address             TEXT,
                phone               TEXT,
                registration_number TEXT,
                bank_name           TEXT,
                bank_branch         TEXT,
                account_type        TEXT,
                account_number      TEXT,
                account_holder      TEXT,
                logo_path           TEXT,
                updated_at          DATETIME
            );

            CREATE TABLE IF NOT EXISTS customers (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name   TEXT NOT NULL,
                address        TEXT,
                phone          TEXT,
                email          TEXT,
                contact_person TEXT,
                notes          TEXT,
                is_active      INTEGER NOT NULL DEFAULT 1,
                created_at     DATETIME,
                updated_at     DATETIME
            );

            CREATE TABLE IF NOT EXISTS invoices (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_number TEXT UNIQUE NOT NULL,
                customer_id    INTEGER,
                issue_date     DATE,
                due_date       DATE,
                subtotal       REAL,
                tax_10         REAL,
                tax_8          REAL,
                total          REAL,
                notes          TEXT,
                pdf_path       TEXT,
                docx_path      TEXT,
                created_at     DATETIME,
                FOREIGN KEY (customer_id) REFERENCES customers(id)
            );

            CREATE TABLE IF NOT EXISTS invoice_items (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id  INTEGER NOT NULL,
                item_name   TEXT NOT NULL,
                quantity    INTEGER,
                unit_price  REAL,
                tax_rate    INTEGER,
                amount      REAL,
                FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE
            );
        """)
        conn.commit()

        if not DEMO_MODE:
            # 本番モードのみ: 既存DBへの is_active カラム追加マイグレーション
            try:
                conn.execute(
                    "ALTER TABLE customers ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1"
                )
                conn.commit()
            except sqlite3.OperationalError:
                pass  # カラムが既に存在する場合は無視

    finally:
        _release_conn(conn)


# ─── 自社情報 ────────────────────────────────────────────────

def get_company_info() -> Optional[CompanyInfo]:
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM companies LIMIT 1").fetchone()
        if row is None:
            return None
        return CompanyInfo(**dict(row))
    finally:
        _release_conn(conn)


def save_company_info(info: CompanyInfo) -> None:
    now = datetime.now().isoformat()
    conn = get_conn()
    try:
        existing = conn.execute("SELECT id FROM companies LIMIT 1").fetchone()
        if existing:
            conn.execute("""
                UPDATE companies SET
                    company_name=?, address=?, phone=?, registration_number=?,
                    bank_name=?, bank_branch=?, account_type=?, account_number=?,
                    account_holder=?, logo_path=?, updated_at=?
                WHERE id=?
            """, (
                info.company_name, info.address, info.phone, info.registration_number,
                info.bank_name, info.bank_branch, info.account_type, info.account_number,
                info.account_holder, info.logo_path, now, existing["id"],
            ))
        else:
            conn.execute("""
                INSERT INTO companies
                    (company_name, address, phone, registration_number,
                     bank_name, bank_branch, account_type, account_number,
                     account_holder, logo_path, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (
                info.company_name, info.address, info.phone, info.registration_number,
                info.bank_name, info.bank_branch, info.account_type, info.account_number,
                info.account_holder, info.logo_path, now,
            ))
        conn.commit()
    finally:
        _release_conn(conn)


# ─── 顧客マスタ ──────────────────────────────────────────────

def add_customer(c: Customer) -> int:
    now = datetime.now().isoformat()
    conn = get_conn()
    try:
        cur = conn.execute("""
            INSERT INTO customers
                (company_name, address, phone, email, contact_person, notes, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?)
        """, (c.company_name, c.address, c.phone, c.email, c.contact_person, c.notes, now, now))
        conn.commit()
        return cur.lastrowid
    finally:
        _release_conn(conn)


def get_customers(search: str = "", active_only: bool = True) -> list[Customer]:
    """顧客一覧を返す。
    active_only=True  : is_active=1 の顧客のみ（デフォルト）
    active_only=False : 有効・無効すべての顧客を返す
    """
    conn = get_conn()
    try:
        conditions: list[str] = []
        params: list = []

        if search:
            conditions.append("(company_name LIKE ? OR contact_person LIKE ?)")
            params += [f"%{search}%", f"%{search}%"]
        if active_only:
            conditions.append("is_active = 1")

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"SELECT * FROM customers {where} ORDER BY company_name"
        rows = conn.execute(sql, params).fetchall()
        return [Customer(**dict(r)) for r in rows]
    finally:
        _release_conn(conn)


def deactivate_customer(customer_id: int) -> None:
    """顧客を無効化する（is_active=0）。"""
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE customers SET is_active=0, updated_at=? WHERE id=?",
            (datetime.now().isoformat(), customer_id),
        )
        conn.commit()
    finally:
        _release_conn(conn)


def activate_customer(customer_id: int) -> None:
    """顧客を有効化する（is_active=1）。"""
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE customers SET is_active=1, updated_at=? WHERE id=?",
            (datetime.now().isoformat(), customer_id),
        )
        conn.commit()
    finally:
        _release_conn(conn)


def get_customer(customer_id: int) -> Optional[Customer]:
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM customers WHERE id=?", (customer_id,)).fetchone()
        return Customer(**dict(row)) if row else None
    finally:
        _release_conn(conn)


def update_customer(c: Customer) -> None:
    now = datetime.now().isoformat()
    conn = get_conn()
    try:
        conn.execute("""
            UPDATE customers SET
                company_name=?, address=?, phone=?, email=?,
                contact_person=?, notes=?, updated_at=?
            WHERE id=?
        """, (c.company_name, c.address, c.phone, c.email,
              c.contact_person, c.notes, now, c.id))
        conn.commit()
    finally:
        _release_conn(conn)


def get_invoice_count_by_customer(customer_id: int) -> int:
    """指定顧客に紐づく請求書の件数を返す。"""
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM invoices WHERE customer_id=?", (customer_id,)
        ).fetchone()
        return row["cnt"] if row else 0
    finally:
        _release_conn(conn)


def delete_customer(customer_id: int) -> None:
    conn = get_conn()
    try:
        conn.execute("DELETE FROM customers WHERE id=?", (customer_id,))
        conn.commit()
    finally:
        _release_conn(conn)


# ─── 請求書 ──────────────────────────────────────────────────

def create_invoice(inv: Invoice, items: list[InvoiceItem]) -> int:
    now = datetime.now().isoformat()
    conn = get_conn()
    try:
        cur = conn.execute("""
            INSERT INTO invoices
                (invoice_number, customer_id, issue_date, due_date,
                 subtotal, tax_10, tax_8, total, notes, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (
            inv.invoice_number, inv.customer_id,
            inv.issue_date.isoformat() if inv.issue_date else None,
            inv.due_date.isoformat() if inv.due_date else None,
            inv.subtotal, inv.tax_10, inv.tax_8, inv.total,
            inv.notes, now,
        ))
        invoice_id = cur.lastrowid
        for item in items:
            conn.execute("""
                INSERT INTO invoice_items
                    (invoice_id, item_name, quantity, unit_price, tax_rate, amount)
                VALUES (?,?,?,?,?,?)
            """, (invoice_id, item.item_name, item.quantity,
                  item.unit_price, item.tax_rate, item.amount))
        conn.commit()
        return invoice_id
    finally:
        _release_conn(conn)


def get_invoices(search: str = "") -> list[dict]:
    conn = get_conn()
    try:
        sql = """
            SELECT i.*,
                   c.company_name AS customer_name,
                   c.is_active    AS customer_is_active
            FROM invoices i
            LEFT JOIN customers c ON i.customer_id = c.id
            WHERE 1=1
        """
        params: list = []
        if search:
            sql += " AND (c.company_name LIKE ? OR i.invoice_number LIKE ?)"
            params += [f"%{search}%", f"%{search}%"]
        sql += " ORDER BY i.created_at DESC"
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        _release_conn(conn)


def get_invoice_details(invoice_id: int) -> Optional[dict]:
    conn = get_conn()
    try:
        inv_row = conn.execute("""
            SELECT i.*,
                   c.company_name AS customer_name,
                   c.address      AS customer_address,
                   c.is_active    AS customer_is_active
            FROM invoices i
            LEFT JOIN customers c ON i.customer_id = c.id
            WHERE i.id=?
        """, (invoice_id,)).fetchone()
        if inv_row is None:
            return None
        result = dict(inv_row)
        items = conn.execute(
            "SELECT * FROM invoice_items WHERE invoice_id=? ORDER BY id", (invoice_id,)
        ).fetchall()
        result["items"] = [dict(r) for r in items]
        return result
    finally:
        _release_conn(conn)


def update_invoice_paths(invoice_id: int, pdf_path: str = None, docx_path: str = None) -> None:
    conn = get_conn()
    try:
        if pdf_path is not None:
            conn.execute("UPDATE invoices SET pdf_path=? WHERE id=?", (pdf_path, invoice_id))
        if docx_path is not None:
            conn.execute("UPDATE invoices SET docx_path=? WHERE id=?", (docx_path, invoice_id))
        conn.commit()
    finally:
        _release_conn(conn)
