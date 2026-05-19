# 📄 Seikyu — 請求書自動生成ツール

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Streamlit-1.32%2B-FF4B4B?logo=streamlit&logoColor=white" alt="Streamlit">
  <img src="https://img.shields.io/badge/SQLite-3-003B57?logo=sqlite&logoColor=white" alt="SQLite">
  <img src="https://img.shields.io/badge/License-MIT-green" alt="License">
  <img src="https://img.shields.io/badge/Demo-Live-brightgreen" alt="Demo">
</p>

<p align="center">
  小規模事業者向けの日本語請求書作成・管理ツールです。<br>
  顧客管理から請求書の作成・PDF/Word出力・履歴管理まで、ブラウザ上でシンプルに操作できます。
</p>

---

## デモ

> **[▶ Live Demo](https://seikyu.streamlit.app)** ← デプロイ後に URL を更新してください

デモ版はデータがアプリ再起動時にリセットされます。実際の業務データは保存されません。

---

## 主な機能

| 機能 | 説明 |
|------|------|
| 👥 **顧客管理** | 顧客の登録・編集・無効化・削除。無効化で請求書履歴を保持したまま非表示化 |
| 📝 **請求書作成** | 明細入力・自動採番・消費税（10% / 8%軽減税率）の自動計算 |
| 📄 **PDF出力** | A4サイズの日本語PDFを即時生成（fpdf2 使用） |
| 📘 **Word出力** | `.docx` 形式で生成（python-docx 使用） |
| 📋 **請求書履歴** | 検索・絞込・再ダウンロード対応 |
| ⚙️ **設定** | 自社情報・振込先・ロゴ画像（PNG/JPG）の管理 |
| 🧾 **インボイス対応** | 適格請求書発行事業者登録番号の表示 |

---

## スクリーンショット

> ※ デプロイ後にスクリーンショットを追加してください。

| 請求書作成 | 顧客一覧 | 設定 |
|:---:|:---:|:---:|
| *(screenshot)* | *(screenshot)* | *(screenshot)* |

---

## 技術スタック

| カテゴリ | 使用技術 |
|----------|---------|
| フレームワーク | [Streamlit](https://streamlit.io/) |
| データベース | SQLite（通常モード: ファイル / デモモード: インメモリ） |
| PDF生成 | [fpdf2](https://py-pdf.github.io/fpdf2/) |
| Word生成 | [python-docx](https://python-docx.readthedocs.io/) |
| データ処理 | [pandas](https://pandas.pydata.org/) |
| 環境変数管理 | [python-dotenv](https://github.com/theskumar/python-dotenv) |

---

## ローカル環境での起動

### 必要環境

- Python 3.10 以上
- pip

### セットアップ手順

```bash
# 1. リポジトリをクローン
git clone https://github.com/Amuzak7/Seikyu.git
cd Seikyu

# 2. 仮想環境を作成・有効化
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# 3. 依存パッケージをインストール
pip install -r requirements.txt

# 4. 環境変数ファイルを作成
cp .env.example .env

# 5. アプリを起動
streamlit run app.py
```

ブラウザが自動で開きます（`http://localhost:8501`）。

### デモモードで起動する場合

```bash
# .env を編集して DEMO_MODE=true に設定するか、
# 環境変数を直接指定して起動
DEMO_MODE=true streamlit run app.py
```

---

## 初回セットアップ

1. アプリを起動し、左メニューの **⚙️ 設定** を選択
2. **「自社情報」タブ** で会社名・住所・電話番号を入力して保存
3. 任意：**「振込先」タブ** で銀行口座情報を入力
4. 任意：**「ロゴ」タブ** でロゴ画像（PNG/JPG）をアップロード
5. **👥 顧客一覧** から請求先顧客を登録
6. **📝 請求書作成** で請求書を作成・出力

---

## デプロイ（Streamlit Community Cloud）

このアプリは **[Streamlit Community Cloud](https://share.streamlit.io/)** で無料でホスティングできます。

### 手順

1. [share.streamlit.io](https://share.streamlit.io/) にアクセスし、GitHubアカウントでサインイン
2. **「New app」** をクリック
3. リポジトリ `Amuzak7/Seikyu`・ブランチ `main`・メインファイル `app.py` を選択
4. **「Advanced settings」** → **Secrets** に以下を入力：

```toml
DEMO_MODE = "true"
```

5. **「Deploy!」** をクリック

デプロイ完了後（通常 2〜3 分）、公開 URL が発行されます。

### デプロイ後の動作確認

- [ ] トップページが表示される
- [ ] ⚙️ 設定から自社情報を登録できる
- [ ] 👥 顧客一覧から顧客を登録できる
- [ ] 📝 請求書作成から請求書を作成・保存できる
- [ ] PDF / Word ダウンロードが動作する
- [ ] 📋 請求書履歴から過去の請求書が確認できる
- [ ] アプリを再起動するとデータがリセットされる（デモ版確認）

---

## 環境変数

| 変数名 | デフォルト | 説明 |
|--------|-----------|------|
| `DEMO_MODE` | `false` | `true` でデモモード（起動時にDBリセット・インメモリSQLite使用） |
| `DB_PATH` | `seikyu.db` | データベースファイルのパス（通常モードのみ有効） |

`.env.example` をコピーして `.env` を作成してください。`.env` は `.gitignore` で除外済みです。

---

## ファイル構成

```
Seikyu/
├── app.py                  # メインアプリ（ルーティング・サイドバー）
├── database.py             # SQLite データベース層（CRUD・デモモード対応）
├── models.py               # データクラス定義（CompanyInfo, Customer, Invoice）
├── utils.py                # 採番・合計計算ユーティリティ
├── invoice_generator.py    # PDF・Word生成モジュール
├── pages/
│   ├── customers.py        # 顧客管理ページ（無効化・検索対応）
│   ├── invoice_create.py   # 請求書作成ページ
│   ├── invoice_history.py  # 請求書履歴ページ
│   └── settings.py         # 設定ページ（自社情報・振込先・ロゴ）
├── templates/
│   └── invoice_pdf.html    # PDF用HTMLテンプレート（WeasyPrint対応）
├── .streamlit/
│   └── config.toml         # Streamlit テーマ・サーバー設定
├── static/                 # ロゴ画像の保存先（.gitignore除外）
├── invoices/               # 生成ファイルの保存先（.gitignore除外）
├── .env.example            # 環境変数サンプル
├── requirements.txt        # 依存パッケージ
└── USER_GUIDE.md           # ユーザーガイド（非技術者向け）
```

---

## データについて

- 通常モードのデータは `seikyu.db`（SQLiteファイル）に保存されます（`.gitignore` 除外済み）
- デモモードのデータはプロセス内メモリに保存され、**アプリ再起動でリセット**されます
- 生成した PDF/Word は `invoices/` フォルダに、ロゴは `static/logo.png` に保存されます
- `.env` は絶対に Git にコミットしないでください（`.gitignore` 除外済み）

---

## ライセンス

MIT License — © 2025 Amuzak7
