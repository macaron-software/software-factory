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

# 安全政策

## 支持的版本

| 版本 | 支持 |
|---------|----------|
| 2.2.x   | 是       |
| 2.1.x   | 是       |
| < 2.1   | 否        |

## 报告漏洞

如果您发现安全漏洞，请负责任地报告：

1. **不要**打开公开的 GitHub Issue
2. 发送邮件至 **security@macaron-software.com**
3. 包括：
   - 漏洞描述
   - 重现步骤
   - 潜在影响
   - 建议修复（如有）

我们将在 48 小时内确认收到，并在 7 天内提供详细回复。

## 安全措施

### 认证与授权

- 基于 JWT 的认证，支持令牌刷新
- 基于角色的访问控制 (RBAC)：admin, project_manager, developer, viewer
- OAuth 2.0 集成（GitHub, Azure AD）
- 安全 Cookie 会话管理

### 输入验证

- 所有 LLM 输入的提示注入防护
- 所有 API 端点的输入清理
- SQL 参数化查询（无原始 SQL 插值）
- 文件路径遍历保护

### 数据保护

- 代理输出中的秘密清除（API 密钥、密码、令牌）
- 源代码或日志中不存储秘密
- 敏感值的环境变量配置
- SQLite WAL 模式保证数据完整性

### 网络安全

- 内容安全策略 (CSP) 头
- API 端点的 CORS 配置
- 按用户/IP 的速率限制
- 生产环境强制 HTTPS（通过 Nginx）

### 依赖管理

- 通过 `pip-audit` 定期审计依赖
- 使用 bandit 和 semgrep 进行 SAST 扫描
- 每个项目的自动化安全任务（每周扫描）

## 披露政策

我们遵循协调披露。修复发布后：
1. 致谢报告者（除非要求匿名）
2. 在 GitHub 上发布安全公告
3. 更新变更日志中的安全修复
