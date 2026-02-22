# Security Remediation — Secure Coding Patterns & Patch Writing

## TDD Security Cycle

```
1. RED:    Write test that REPRODUCES the exploit (must FAIL = vuln exists)
2. GREEN:  Write minimal fix that makes the test PASS
3. REFACTOR: Clean up without changing security behavior
4. VERIFY: Run full test suite — zero regressions
5. RESCAN: Run SAST — finding must disappear
```

## Fix Patterns by Vulnerability Type

### SQL Injection → Parameterized Queries
```python
# ❌ VULNERABLE
cursor.execute(f"SELECT * FROM users WHERE id = '{user_id}'")

# ✅ FIXED
cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
```

### XSS → Output Encoding + CSP
```python
# ❌ VULNERABLE (Jinja2)
{{ user_input }}

# ✅ FIXED (auto-escaping enabled)
{{ user_input | e }}
# + CSP header: Content-Security-Policy: default-src 'self'; script-src 'nonce-xxx'
```

### SSRF → URL Allowlist
```python
# ❌ VULNERABLE
response = requests.get(user_url)

# ✅ FIXED
from urllib.parse import urlparse
ALLOWED_HOSTS = {"api.example.com", "cdn.example.com"}
parsed = urlparse(user_url)
if parsed.hostname not in ALLOWED_HOSTS:
    raise ValueError("URL not allowed")
if parsed.scheme not in ("http", "https"):
    raise ValueError("Scheme not allowed")
# Block private IPs
import ipaddress
ip = ipaddress.ip_address(socket.gethostbyname(parsed.hostname))
if ip.is_private or ip.is_loopback:
    raise ValueError("Private IP not allowed")
response = requests.get(user_url)
```

### Auth Bypass → Centralized Middleware
```python
# ❌ VULNERABLE (auth check in each route)
@app.get("/api/admin/users")
async def list_users(request):
    # forgot auth check!
    return users

# ✅ FIXED (centralized middleware)
@app.middleware("http")
async def auth_middleware(request, call_next):
    if request.url.path.startswith("/api/"):
        token = request.headers.get("Authorization")
        if not verify_token(token):
            return JSONResponse(status_code=401)
    return await call_next(request)
```

### IDOR → Authorization Before Data Access
```python
# ❌ VULNERABLE
@app.get("/api/orders/{order_id}")
async def get_order(order_id: int):
    return db.get_order(order_id)  # any user can access any order

# ✅ FIXED
@app.get("/api/orders/{order_id}")
async def get_order(order_id: int, user = Depends(get_current_user)):
    order = db.get_order(order_id)
    if order.user_id != user.id:
        raise HTTPException(403, "Not your order")
    return order
```

### CSRF → SameSite + Token
```python
# ✅ Cookie config
response.set_cookie("session", value, samesite="strict", secure=True, httponly=True)

# ✅ CSRF token in forms
<input type="hidden" name="csrf_token" value="{{ csrf_token }}">
```

### Command Injection → Subprocess with List
```python
# ❌ VULNERABLE
os.system(f"git log {user_input}")

# ✅ FIXED
subprocess.run(["git", "log", user_input], check=True, capture_output=True)
```

### Path Traversal → Canonicalize + Validate
```python
# ❌ VULNERABLE
with open(os.path.join(upload_dir, filename)) as f: ...

# ✅ FIXED
import pathlib
safe_path = pathlib.Path(upload_dir).resolve() / filename
if not str(safe_path.resolve()).startswith(str(pathlib.Path(upload_dir).resolve())):
    raise ValueError("Path traversal detected")
```

## PR Template

```markdown
## Security Fix: [Finding ID] — [Title]

### Vulnerability
- Type: [SQLi/XSS/SSRF/...]
- CVSS: X.X
- File: [path]
- Line: [number]

### Root Cause
[Brief explanation of WHY the code was vulnerable]

### Fix
[Description of the fix approach]

### Test
- [x] Test reproduces exploit (fails without fix)
- [x] Test passes with fix
- [x] Full test suite passes (no regressions)
- [x] SAST scan clean

### Checklist
- [ ] Atomic change (security fix only, no features)
- [ ] Documented in security changelog
- [ ] Reviewed by Security Dev Lead
```

## Anti-Patterns (REJECT)
- Fix that disables the feature instead of securing it
- Regex-only input validation (use proper parsing)
- Client-side validation without server-side
- Blacklist instead of whitelist for URL/path validation
- `# nosec` / `# noqa` annotations to silence scanners
- Catch-all exception hiding security errors
