from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional


@dataclass
class CompanyInfo:
    id: Optional[int] = None
    company_name: str = ""
    address: str = ""
    phone: str = ""
    registration_number: str = ""
    bank_name: str = ""
    bank_branch: str = ""
    account_type: str = "普通"
    account_number: str = ""
    account_holder: str = ""
    logo_path: Optional[str] = None
    updated_at: Optional[datetime] = None


@dataclass
class Customer:
    id: Optional[int] = None
    company_name: str = ""
    address: str = ""
    phone: str = ""
    email: str = ""
    contact_person: str = ""
    notes: str = ""
    is_active: int = 1          # 1=有効  0=無効
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class InvoiceItem:
    id: Optional[int] = None
    invoice_id: Optional[int] = None
    item_name: str = ""
    quantity: int = 1
    unit_price: float = 0.0
    tax_rate: int = 10
    amount: float = 0.0


@dataclass
class Invoice:
    id: Optional[int] = None
    invoice_number: str = ""
    customer_id: Optional[int] = None
    issue_date: Optional[date] = None
    due_date: Optional[date] = None
    subtotal: float = 0.0
    tax_10: float = 0.0
    tax_8: float = 0.0
    total: float = 0.0
    notes: str = ""
    pdf_path: Optional[str] = None
    docx_path: Optional[str] = None
    created_at: Optional[datetime] = None
    items: list = field(default_factory=list)
    customer_name: str = ""
