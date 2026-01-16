# AUDIT MISSION: Fix Broken gRPC Endpoints & User Journeys

## CRITICAL ERROR IN PRODUCTION
```
gRPC Error (INVALID_ARGUMENT): Invalid tenant_id: invalid length: expected length 32 for simple format, found 0
```

## SYMPTOMS
1. **tenant_id is EMPTY** (length 0 instead of 32 UUID) - context not passed
2. **NO user journey works** - user, admin, owner all broken
3. **Buttons/links lead to unimplemented actions or pages**

## YOUR MISSION
Audit the entire codebase to find:

### 1. TENANT_ID PROPAGATION ISSUES
- Where is tenant_id supposed to be set?
- Where is it missing in the gRPC call chain?
- Check: interceptors, middleware, frontend API clients

### 2. BROKEN gRPC ENDPOINTS
- List ALL gRPC services and their endpoints
- For each endpoint: is it implemented or stub?
- For each endpoint: is tenant_id properly extracted?

### 3. UNIMPLEMENTED USER JOURNEYS
For each role (user, admin, owner):
- List ALL buttons/links in the UI
- Check if backend handler exists
- Check if handler is connected (not stub)

### 4. FRONTEND-BACKEND DISCONNECTS
- Frontend components calling non-existent endpoints
- Wrong proto service/method names
- Missing gRPC-Web proxy routes

## OUTPUT FORMAT
Generate tasks/T*.md files for EACH fix needed:
- One task per broken endpoint
- One task per missing journey step
- Priority: P0 for tenant_id fix, P1 for core journeys

## TOOLS AVAILABLE
- veligo_rag_query: Search codebase semantically
- veligo_grep: Grep for patterns
- veligo_ao_search: Search AO requirements

## START
Begin by:
1. Finding where tenant_id SHOULD be set in gRPC interceptors
2. Tracing the error from frontend to backend
3. Listing all .svelte files with gRPC calls
