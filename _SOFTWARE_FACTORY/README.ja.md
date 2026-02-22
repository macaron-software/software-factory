<p align="center">
  <a href="README.md">English</a> |
  <a href="README.fr.md">Français</a> |
  <a href="README.zh-CN.md">中文</a> |
  <a href="README.es.md">Español</a> |
  <a href="README.ja.md">日本語</a> |
  <a href="README.pt.md">Português</a> |
  <a href="README.de.md">Deutsch</a> |
  <a href="README.ko.md">한국어</a>
</p>

<div align="center">

# Macaron ソフトウェアファクトリー

**マルチエージェントソフトウェアファクトリー — 自律型 AI エージェントが製品ライフサイクル全体をオーケストレーション**

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)

[機能](#機能) · [クイックスタート](#クイックスタート) · [スクリーンショット](#スクリーンショット) · [アーキテクチャ](#アーキテクチャ) · [コントリビュート](#コントリビュート)

</div>

---

## これは何ですか？

Macaron は、ソフトウェア開発ライフサイクル全体をオーケストレーションする**自律型マルチエージェントプラットフォーム**です——アイデア発想からデプロイまで——協力する専門 AI エージェントを使用します。

94 の AI エージェントが構造化されたワークフローを通じて協力する**バーチャルソフトウェアファクトリー**と考えてください。SAFe 方法論、TDD プラクティス、自動化品質ゲートに従います。

### 主な特徴

- **94 の専門エージェント** — アーキテクト、開発者、テスター、SRE、セキュリティアナリスト、プロダクトオーナー
- **12 のオーケストレーションパターン** — ソロ、並列、階層、ネットワーク、敵対ペア、ヒューマンインザループ
- **SAFe に整合したライフサイクル** — Portfolio → Epic → Feature → Story、PI ケイデンス
- **自己修復** — 自律型インシデント検出、トリアージ、修復
- **セキュリティファースト** — インジェクションガード、RBAC、シークレットスクラビング、コネクションプール
- **DORA メトリクス** — デプロイ頻度、リードタイム、MTTR、変更失敗率

## スクリーンショット

<table>
<tr>
<td width="50%">
<strong>ポートフォリオ — 戦略委員会とガバナンス</strong><br>
<img src="docs/screenshots/ja/portfolio.png" alt="Portfolio" width="100%">
</td>
<td width="50%">
<strong>PI ボード — プログラムインクリメント計画</strong><br>
<img src="docs/screenshots/ja/pi_board.png" alt="PI Board" width="100%">
</td>
</tr>
<tr>
<td width="50%">
<strong>エージェント — 94 の専門 AI エージェント</strong><br>
<img src="docs/screenshots/ja/agents.png" alt="Agents" width="100%">
</td>
<td width="50%">
<strong>アイデアワークショップ — AI ブレーンストーミング</strong><br>
<img src="docs/screenshots/ja/ideation.png" alt="Ideation" width="100%">
</td>
</tr>
<tr>
<td width="50%">
<strong>ミッションコントロール — リアルタイム実行監視</strong><br>
<img src="docs/screenshots/ja/mission_control.png" alt="Mission Control" width="100%">
</td>
<td width="50%">
<strong>モニタリング — システムヘルスとメトリクス</strong><br>
<img src="docs/screenshots/ja/monitoring.png" alt="Monitoring" width="100%">
</td>
</tr>
</table>

## クイックスタート

### 方法 1: Docker（推奨）

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory

make setup
# Edit .env with your LLM API key

make run
```

Open **http://localhost:8090**

### 方法 2: Docker Compose（手動）

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory

cp .env.example .env
# Edit .env with your LLM API key

docker compose up -d
```

### 方法 3: ローカル開発

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory

python3 -m venv .venv
source .venv/bin/activate
pip install -r platform/requirements.txt

export OPENAI_API_KEY=sk-...

make dev
```

### インストールの確認

```bash
curl http://localhost:8090/api/health
```

## コントリビュート

コントリビューションを歓迎します！ガイドラインは [CONTRIBUTING.md](CONTRIBUTING.md) をご覧ください。

## ライセンス

**GNU Affero General Public License v3.0** — [LICENSE](LICENSE)

---

<div align="center">

**Love を込めて構築 by [Macaron Software](https://github.com/macaron-software)**

[バグ報告](https://github.com/macaron-software/software-factory/issues) · [機能リクエスト](https://github.com/macaron-software/software-factory/issues)

</div>
