from datetime import date


def generate_invoice_number(db_path: str = "") -> str:
    """請求書番号を採番して返す（INV-YYYYMMDD-XXX 形式）。
    db_path 引数は後方互換のために残しているが、内部では database.get_conn() を使用する。
    デモモードではインメモリDBのシングルトン接続を正しく参照する。
    """
    from database import get_conn, _release_conn

    today  = date.today().strftime("%Y%m%d")
    prefix = f"INV-{today}-"

    conn = get_conn()
    try:
        cursor = conn.execute(
            "SELECT invoice_number FROM invoices "
            "WHERE invoice_number LIKE ? ORDER BY invoice_number DESC LIMIT 1",
            (f"{prefix}%",),
        )
        row = cursor.fetchone()
        seq = int(row[0].split("-")[-1]) + 1 if row else 1
    finally:
        _release_conn(conn)

    return f"{prefix}{seq:03d}"


def calc_invoice_totals(items: list[dict]) -> dict:
    subtotal = 0.0
    tax_10   = 0.0
    tax_8    = 0.0

    for item in items:
        amount = item.get("quantity", 0) * item.get("unit_price", 0.0)
        rate   = item.get("tax_rate", 10)
        subtotal += amount
        if rate == 10:
            tax_10 += amount * 0.10
        elif rate == 8:
            tax_8  += amount * 0.08

    return {
        "subtotal": round(subtotal, 0),
        "tax_10":   round(tax_10,   0),
        "tax_8":    round(tax_8,    0),
        "total":    round(subtotal + tax_10 + tax_8, 0),
    }
