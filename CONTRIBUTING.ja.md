<p align="center">
  <a href="CONTRIBUTING.md">English</a> |
  <a href="CONTRIBUTING.fr.md">Français</a> |
  <a href="CONTRIBUTING.zh-CN.md">中文</a> |
  <a href="CONTRIBUTING.es.md">Español</a> |
  <a href="CONTRIBUTING.ja.md">日本語</a> |
  <a href="CONTRIBUTING.pt.md">Português</a> |
  <a href="CONTRIBUTING.de.md">Deutsch</a> |
  <a href="CONTRIBUTING.ko.md">한국어</a>
</p>

# Software Factory への貢献

Software Factory への貢献に興味をお持ちいただきありがとうございます。このドキュメントでは、貢献のためのガイドラインと手順を説明します。

## 行動規範

参加することにより、[行動規範](CODE_OF_CONDUCT.ja.md)に従うことに同意します。

## 貢献方法

### バグの報告

1. 重複を避けるため、[既存の Issue](https://github.com/macaron-software/software-factory/issues) を確認してください
2. [バグ報告テンプレート](.github/ISSUE_TEMPLATE/bug_report.md)を使用してください
3. 含めるもの：再現手順、期待される動作と実際の動作、環境の詳細

### 機能の提案

1. [機能リクエストテンプレート](.github/ISSUE_TEMPLATE/feature_request.md)を使用して Issue を作成してください
2. ユースケースと期待される動作を説明してください
3. なぜ他のユーザーに役立つかを説明してください

### Pull Requests

1. リポジトリをフォーク
2. フィーチャーブランチを作成：`git checkout -b feature/my-feature`
3. 以下のコーディング標準に従って変更を加える
4. テストを書くか更新する
5. テストを実行：`make test`
6. 明確なメッセージでコミット（下記の規約を参照）
7. プッシュして Pull Request を作成

## 開発環境のセットアップ

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory
cp .env.example .env
python3 -m venv .venv && source .venv/bin/activate
pip install -r platform/requirements.txt
make test
make dev
```

## コーディング標準

### Python

- **スタイル**：PEP 8、`ruff` で強制
- **型ヒント**：パブリック API に必須
- **ドキュメント文字列**：モジュール、クラス、パブリック関数に Google スタイル
- **インポート**：すべてのファイルで `from __future__ import annotations`

### コミットメッセージ

[Conventional Commits](https://www.conventionalcommits.org/) に従ってください：

```
feat: WebSocket リアルタイムチャネルを追加
fix: ミッション API のルート順序を修正
refactor: api.py をサブモジュールに分割
docs: アーキテクチャ図を更新
test: ワーカーキューテストを追加
```

### テスト

- `tests/` のユニットテスト（`pytest` 使用）
- 非同期テスト（`pytest-asyncio` 使用）
- `platform/tests/e2e/` の E2E テスト（Playwright 使用）
- すべての新機能にテストが必要

### アーキテクチャルール

- **LLM が生成し、決定論的ツールが検証** — 創造的タスクに AI、検証にスクリプト/コンパイラ
- **巨大ファイル禁止** — 500 行超のモジュールはサブパッケージに分割
- **SQLite で永続化** — 外部データベース依存なし
- **マルチプロバイダー LLM** — 単一プロバイダーをハードコードしない
- **後方互換性** — 新機能は既存 API を壊してはならない

## ライセンス

貢献することにより、あなたの貢献が [AGPL v3 ライセンス](LICENSE) の下でライセンスされることに同意します。
