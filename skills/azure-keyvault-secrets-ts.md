---
name: azure-keyvault-secrets-ts
version: 1.0.0
description: Manage secrets using Azure Key Vault Secrets SDK for JavaScript (@azure/keyvault-secrets).
  Use when storing and retrieving application secrets or configuration values.
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - storing and retrieving application secrets or configuration values
eval_cases:
- id: azure-keyvault-secrets-ts-approach
  prompt: How should I approach azure keyvault secrets ts for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on azure keyvault secrets ts
  tags:
  - azure
- id: azure-keyvault-secrets-ts-best-practices
  prompt: What are the key best practices and pitfalls for azure keyvault secrets
    ts?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for azure keyvault secrets ts
  tags:
  - azure
  - best-practices
- id: azure-keyvault-secrets-ts-antipatterns
  prompt: What are the most common mistakes to avoid with azure keyvault secrets ts?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - azure
  - antipatterns
---
# azure-keyvault-secrets-ts

# Azure Key Vault Secrets SDK for TypeScript

Manage secrets with Azure Key Vault.

## Installation

```bash
# Secrets SDK
npm install @azure/keyvault-secrets @azure/identity
```

## Environment Variables

```bash
KEY_VAULT_URL=https://<vault-name>.vault.azure.net
# Or
AZURE_KEYVAULT_NAME=<vault-name>
```

## Authentication

```typescript
import { DefaultAzureCredential } from "@azure/identity";
import { SecretClient } from "@azure/keyvault-secrets";

const credential = new DefaultAzureCredential();
const vaultUrl = `https://${process.env.AZURE_KEYVAULT_NAME}.vault.azure.net`;

const keyClient = new KeyClient(vaultUrl, credential);
const secretClient = new SecretClient(vaultUrl, credential);
```

## Secrets Operations

### Create/Set Secret

```typescript
const secret = await secretClient.setSecret("MySecret", "secret-value");

// With attributes
const secretWithAttrs = await secretClient.setSecret("MySecret", "value", {
  enabled: true,
  expiresOn: new Date("2025-12-31"),
  contentType: "application/json",
  tags: { environment: "production" }
});
```

### Get Secret

```typescript
// Get latest version
const secret = await secretClient.getSecret("MySecret");
console.log(secret.value);

// Get specific version
const specificSecret = await secretClient.getSecret("MySecret", {
  version: secret.properties.version
});
```

### List Secrets

```typescript
for await (const secretProperties of secretClient.listPropertiesOfSecrets()) {
  console.log(secretProperties.name);
}

// List versions
for await (const version of secretClient.listPropertiesOfSecretVersions("MySecret")) {
  console.log(version.version);
}
```

### Delete Secret

```typescript
// Soft delete
const deletePoller = await secretClient.beginDeleteSecret("MySecret");
await deletePoller.pollUntilDone();

// Purge (permanent)
await secretClient.purgeDeletedSecret("MySecret");

// Recover
const recoverPoller = await secretClient.beginRecoverDeletedSecret("MySecret");
await recoverPoller.pollUntilDone();
```

## Keys Operations

### Create Keys

```typescript
// Generic key
const key = await keyClient.createKey("MyKey", "RSA");

// RSA key with size
const rsaKey = await keyClient.createRsaKey("MyRsaKey", { keySize: 2048 });

// Elliptic Curve key
const ecKey = await keyClient.createEcKey("MyEcKey", { curve: "P-256" });

// With attributes
const keyWithAttrs = await keyClient.createKey("MyKey", "RSA", {
  enabled: true,
  expiresOn: new Date("2025-12-31"),
  tags: { purpose: "encryption" },
  keyOps: ["encrypt", "decrypt", "sign", "verify"]
});
```

### Get Key

```typescript
const key = await keyClient.getKey("MyKey");
console.log(key.name, key.keyType);
```

### List Keys

```typescript
for await (const keyProperties of keyClient.listPropertiesOfKeys()) {
  console.log(keyProperties.name);
}
```

### Rotate Key

```typescript
// Manual rotation
const rotatedKey = await keyClient.rotateKey("MyKey");

// Set rotation policy
await keyClient.updateKeyRotationPolicy("MyKey", {
  lifetimeActions: [{ action: "Rotate", timeBeforeExpiry: "P30D" }],
  expiresIn: "P90D"
});
```

### Delete Key

```typescript
const deletePoller = await keyClient.beginDeleteKey("MyKey");
await deletePoller.pollUntilDone();

// Purge
await keyClient.purgeDeletedKey("MyKey");
```

## Cryptographic Operations

### Create CryptographyClient

```typescript
import { CryptographyClient } from "@azure/keyvault-keys";

// From key object
const cryptoClient = new CryptographyClient(key, credential);

// From key ID
const cryptoClient = new CryptographyClient(key.id!, credential);
```

### Encrypt/Decrypt

```typescript
// Encrypt
const encryptResult = await cryptoClient.encrypt({
  algorithm: "RSA-OAEP",
  plaintext: Buffer.from("My secret message")
});

// Decrypt
const decryptResult = await cryptoClient.decrypt({
  algorithm: "RSA-OAEP",
  ciphertext: encryptResult.result
});

console.log(decryptResult.result.toString());
```

### Sign/Verify

```typescript
import { createHash } from "node:crypto";

// Create digest
const hash = createHash("sha256").update("My message").digest();

// Sign
const signResult = await cryptoClient.sign("RS256", hash);

// Verify
const verifyResult = await cryptoClient.verify("RS256", hash, signResult.result);
console.log("Valid:", verifyResult.result);
```

### Wrap/Unwrap Keys

```typescript
// Wrap a key (encrypt it for storage)
const wrapResult = await cryptoClient.wrapKey("RSA-OAEP", Buffer.from("key-material"));

// Unwrap
const unwrapResult = await cryptoClient.unwrapKey("RSA-OAEP", wrapResult.result);
```

## Backup and Restore

```typescript
// Backup
const keyBackup = await keyClient.backupKey("MyKey");
const secretBackup = await secretClient.backupSecret("MySecret");

// Restore (can restore to different vault)
const restoredKey = await keyClient.restoreKeyBackup(keyBackup!);
const restoredSecret = await secretClient.restoreSecretBackup(secretBackup!);
```

## Key Types

```typescript
import {
  KeyClient,
  KeyVaultKey,
  KeyProperties,
  DeletedKey,
  CryptographyClient,
  KnownEncryptionAlgorithms,
  KnownSignatureAlgorithms
} from "@azure/keyvault-keys";

import {
  SecretClient,
  KeyVaultSecret,
  SecretProperties,
  DeletedSecret
} from "@azure/keyvault-secrets";
```

## Error Handling

```typescript
try {
  const secret = await secretClient.getSecret("NonExistent");
} catch (error: any) {
  if (error.code === "SecretNotFound") {
    console.log("Secret does not exist");
  } else {
    throw error;
  }
}
```

## Best Practices

1. **Use DefaultAzureCredential** - Works across dev and production
2. **Enable soft-delete** - Required for production vaults
3. **Set expiration dates** - On both keys and secrets
4. **Use key rotation policies** - Automate key rotation
5. **Limit key operations** - Only grant needed operations (encrypt, sign, etc.)
6. **Browser not supported** - These SDKs are Node.js only

## When to Use
This skill is applicable to execute the workflow or actions described in the overview.
