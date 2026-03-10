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

# Politica de Seguranca

## Versoes Suportadas

| Versao | Suportada |
|---------|----------|
| 2.2.x   | Sim       |
| 2.1.x   | Sim       |
| < 2.1   | Nao        |

## Reportar uma Vulnerabilidade

Se voce descobrir uma vulnerabilidade de seguranca, reporte de forma responsavel:

1. **Nao** abra uma issue publica no GitHub
2. Envie um email para **security@macaron-software.com**
3. Inclua:
   - Descricao da vulnerabilidade
   - Passos para reproduzir
   - Impacto potencial
   - Correcao sugerida (se houver)

Confirmaremos o recebimento em 48 horas e forneceremos uma resposta detalhada em 7 dias.

## Medidas de Seguranca

### Autenticacao e Autorizacao

- Autenticacao JWT com renovacao de token
- Controle de acesso baseado em funcoes (RBAC): admin, project_manager, developer, viewer
- Integracao OAuth 2.0 (GitHub, Azure AD)
- Gerenciamento de sessao com cookies seguros

### Validacao de Entrada

- Protecao contra injecao de prompt em todas as entradas LLM
- Sanitizacao de entrada em todos os endpoints API
- Consultas SQL parametrizadas (sem interpolacao SQL direta)
- Protecao contra travessia de caminho de arquivo

### Protecao de Dados

- Limpeza de segredos nas saidas dos agentes (chaves API, senhas, tokens)
- Sem segredos armazenados no codigo fonte ou logs
- Configuracao baseada em ambiente para valores sensiveis
- Modo WAL do SQLite para integridade de dados

### Seguranca de Rede

- Cabecalhos Content Security Policy (CSP)
- Configuracao CORS para endpoints API
- Limitacao de taxa por usuario/IP
- HTTPS obrigatorio em producao (via Nginx)

### Gerenciamento de Dependencias

- Auditorias regulares de dependencias via `pip-audit`
- Varredura SAST com bandit e semgrep
- Missoes de seguranca automatizadas por projeto (varreduras semanais)

## Politica de Divulgacao

Seguimos a divulgacao coordenada. Apos a publicacao de uma correcao:
1. Credito ao relator (a menos que anonimato seja solicitado)
2. Publicacao de um aviso de seguranca no GitHub
3. Atualizacao do changelog com correcoes de seguranca
