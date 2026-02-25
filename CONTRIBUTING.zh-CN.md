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

# Software Factory 贡献指南

感谢您有兴趣为 Software Factory 做出贡献！本文档提供贡献的指南和说明。

## 行为准则

参与即表示您同意遵守我们的[行为准则](CODE_OF_CONDUCT.zh-CN.md)。

## 如何贡献

### 报告错误

1. 查看[现有 Issues](https://github.com/macaron-software/software-factory/issues) 以避免重复
2. 使用[错误报告模板](.github/ISSUE_TEMPLATE/bug_report.md)
3. 包括：重现步骤、预期行为与实际行为、环境详情

### 建议功能

1. 使用[功能请求模板](.github/ISSUE_TEMPLATE/feature_request.md)打开一个 Issue
2. 描述用例和预期行为
3. 解释为什么这对其他用户有用

### Pull Requests

1. Fork 仓库
2. 创建功能分支：`git checkout -b feature/my-feature`
3. 按照以下编码标准进行更改
4. 编写或更新测试
5. 运行测试：`make test`
6. 使用清晰的消息提交（见下方约定）
7. 推送并打开 Pull Request

## 开发环境设置

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory
cp .env.example .env
python3 -m venv .venv && source .venv/bin/activate
pip install -r platform/requirements.txt
make test
make dev
```

## 编码标准

### Python

- **风格**：PEP 8，由 `ruff` 强制执行
- **类型提示**：公共 API 必须使用
- **文档字符串**：模块、类、公共函数使用 Google 风格
- **导入**：所有文件中使用 `from __future__ import annotations`

### 提交消息

遵循 [Conventional Commits](https://www.conventionalcommits.org/)：

```
feat: 添加 WebSocket 实时通道
fix: 修复任务 API 路由顺序
refactor: 将 api.py 拆分为子模块
docs: 更新架构图
test: 添加工作队列测试
```

### 测试

- 单元测试在 `tests/` 中，使用 `pytest`
- 异步测试使用 `pytest-asyncio`
- E2E 测试在 `platform/tests/e2e/` 中，使用 Playwright
- 所有新功能必须有测试

### 架构规则

- **LLM 生成，确定性工具验证** — AI 用于创造性任务，脚本/编译器用于验证
- **无巨型文件** — 超过 500 行的模块拆分为子包
- **SQLite 持久化** — 无外部数据库依赖
- **多提供商 LLM** — 不硬编码单一提供商
- **向后兼容** — 新功能不得破坏现有 API

## 许可证

通过贡献，您同意您的贡献将在 [AGPL v3 许可证](LICENSE) 下授权。
