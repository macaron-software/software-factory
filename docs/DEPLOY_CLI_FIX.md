# Deploy CLI Fix to Azure Production

## Issue Fixed
Fixed CLI commands in `/toolbox` throwing "Unknown error" when executing commands like `sf$ platform status`.

## Root Causes Fixed
1. **Wrong API endpoint paths**: CLI routes were missing `/api` prefix
   - Changed `/cli/execute` → `/api/cli/execute`
   - Changed `/cli/commands` → `/api/cli/commands`

2. **Missing PATH environment**: System commands like `pwd`, `ls`, `git` couldn't be found
   - Added proper PATH: `/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin`

3. **Wrong directory context**: Hardcoded `/app` for Docker but needed to support local dev
   - Auto-detect: Use `/app` if exists, otherwise `os.getcwd()`

4. **Wrong mission attributes**: Code used `mission.title` but model has `mission.name`
   - Added safe attribute access with `getattr()` and `hasattr()`

## Files Changed
- `platform/web/routes/cli.py`: Fixed API paths, PATH environment, directory context
- `platform/web/routes/sf_commands.py`: Fixed mission attributes, linting issues

## Deployment Steps

### 1. Verify Local Fix
```bash
# Test locally (already working on localhost:8099)
curl -s -X POST http://localhost:8099/api/sf/execute \
  -H "Content-Type: application/json" \
  --data '{"command":"platform status","args":[]}' | python3 -m json.tool

# Expected: success: true with platform stats
```

### 2. Deploy to Azure VM

#### Option A: Git Pull (Recommended)
```bash
# SSH into Azure VM
ssh appuser@4.233.64.30

# Navigate to platform directory inside container
docker exec -it deploy-platform-1 bash

# Pull latest changes
cd /app
git pull origin master

# Restart container to pick up changes
exit
docker restart deploy-platform-1

# Wait for startup (30s)
sleep 30
```

#### Option B: Manual File Copy (If SSH works)
```bash
# From local machine
cd /Users/sylvain/_MACARON-SOFTWARE/_SOFTWARE_FACTORY

# Copy files to Azure VM
scp platform/web/routes/cli.py \
    appuser@4.233.64.30:/tmp/cli.py

scp platform/web/routes/sf_commands.py \
    appuser@4.233.64.30:/tmp/sf_commands.py

# SSH into VM and move files into container
ssh appuser@4.233.64.30

docker cp /tmp/cli.py deploy-platform-1:/app/platform/web/routes/cli.py
docker cp /tmp/sf_commands.py deploy-platform-1:/app/platform/web/routes/sf_commands.py

# Fix permissions
docker exec -u root deploy-platform-1 chown -R appuser:appuser /app/platform/web/routes/

# Restart container
docker restart deploy-platform-1
```

### 3. Verify Production Fix
```bash
# Test platform status command
curl -s -X POST http://4.233.64.30/api/sf/execute \
  -H "Content-Type: application/json" \
  --data '{"command":"platform status","args":[]}' | python3 -m json.tool

# Should return success: true with platform stats

# Test system command
curl -s -X POST http://4.233.64.30/api/cli/execute \
  -H "Content-Type: application/json" \
  --data '{"command":"whoami","args":[]}' | python3 -m json.tool

# Should return success: true with username
```

### 4. Test in Browser
1. Navigate to http://4.233.64.30/toolbox
2. Click on "CLI" tab
3. Type: `platform status` and press Enter
4. Should see platform statistics (no "Unknown error")
5. Type: `missions list` and press Enter
6. Should see missions table

## Troubleshooting

### If "Unknown error" persists
1. Check container logs:
   ```bash
   docker logs deploy-platform-1 --tail 100
   ```

2. Check if server restarted:
   ```bash
   docker ps | grep deploy-platform-1
   # Should show "Up X seconds" after restart
   ```

3. Check if files were copied:
   ```bash
   docker exec deploy-platform-1 cat /app/platform/web/routes/cli.py | grep "api/cli/execute"
   # Should contain "/api/cli/execute" (with /api prefix)
   ```

### If import errors occur
Production has a naming conflict where `platform/` directory conflicts with Python's stdlib `platform` module. This is a known issue that doesn't affect CLI functionality but causes import warnings. The CLI endpoints don't import the problematic modules.

### If SSH authentication fails
As noted in previous deployments, SSH keys may not work. Try:
1. Password authentication (if configured)
2. Azure Portal web console
3. Azure CLI: `az vm run-command invoke`

## Commit Details
- Commit: `30a6f3cd` 
- Branch: `master`
- Pushed: 2026-02-23
- Files changed: 2 (cli.py, sf_commands.py)
- Lines changed: +28 -19

## Expected Outcome
✅ CLI tab commands work without errors  
✅ `platform status` shows platform stats  
✅ `missions list` shows missions table  
✅ `whoami`, `pwd`, `ls` system commands work  
✅ No more "Unknown error" messages

## Rollback (If Needed)
```bash
# SSH into VM
ssh appuser@4.233.64.30

# Inside container, revert to previous commit
docker exec -it deploy-platform-1 bash
cd /app
git reset --hard efcf80a6  # Previous commit before CLI fix
exit

docker restart deploy-platform-1
```
