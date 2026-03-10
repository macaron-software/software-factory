<p align="center">
  <a href="SECURITY.md">English</a> |
  <a href="SECURITY.fr.md">Français</a> |
  <a href="SECURITY.zh-CN.md">中文</a> |
  <a href="SECURITY.es.md">Español</a> |
  <a href="SECURITY.ja.md">日本語</a> |
  <a href="SECURITY.pt.md">Português</a> |
  <a href="SECURITY.de.md">Deutsch</a> |
  <a href="SECURITY.ko.md">한국어</a>
</p>

# セキュリティポリシー

## サポートバージョン

| バージョン | サポート |
|---------|----------|
| 2.2.x   | はい       |
| 2.1.x   | はい       |
| < 2.1   | いいえ        |

## 脆弱性の報告

セキュリティ脆弱性を発見した場合は、責任を持って報告してください：

1. 公開の GitHub Issue を**作成しないでください**
2. **security@macaron-software.com** にメールを送信してください
3. 含めるもの：
   - 脆弱性の説明
   - 再現手順
   - 潜在的な影響
   - 提案された修正（ある場合）

48 時間以内に受領確認を行い、7 日以内に詳細な回答を提供します。

## セキュリティ対策

### 認証と認可

- トークンリフレッシュ付き JWT 認証
- ロールベースアクセス制御 (RBAC)：admin, project_manager, developer, viewer
- OAuth 2.0 統合（GitHub, Azure AD）
- セキュアな Cookie によるセッション管理

### 入力検証

- すべての LLM 入力に対するプロンプトインジェクション防護
- すべての API エンドポイントでの入力サニタイズ
- パラメータ化 SQL クエリ（生の SQL 補間なし）
- ファイルパストラバーサル保護

### データ保護

- エージェント出力でのシークレット除去（API キー、パスワード、トークン）
- ソースコードやログにシークレットを保存しない
- 機密値の環境ベース設定
- データ整合性のための SQLite WAL モード

### ネットワークセキュリティ

- Content Security Policy (CSP) ヘッダー
- API エンドポイントの CORS 設定
- ユーザー/IP ごとのレート制限
- 本番環境での HTTPS 強制（Nginx 経由）

### 依存関係管理

- `pip-audit` による定期的な依存関係監査
- bandit と semgrep による SAST スキャン
- プロジェクトごとの自動セキュリティミッション（週次スキャン）

## 開示ポリシー

協調的開示に従います。修正がリリースされた後：
1. 報告者へのクレジット（匿名を希望しない限り）
2. GitHub でのセキュリティアドバイザリ公開
3. セキュリティ修正のチェンジログ更新
