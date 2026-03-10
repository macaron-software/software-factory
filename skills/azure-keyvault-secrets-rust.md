---
name: azure-keyvault-secrets-rust
version: 1.0.0
description: 'Azure Key Vault Secrets SDK for Rust. Use for storing and retrieving
  secrets, passwords, and API keys. Triggers: "keyvault secrets rust", "SecretClient
  rust", "get secret rust", "set secret rust".'
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - when working on azure keyvault secrets rust
eval_cases:
- id: azure-keyvault-secrets-rust-approach
  prompt: How should I approach azure keyvault secrets rust for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on azure keyvault secrets rust
  tags:
  - azure
- id: azure-keyvault-secrets-rust-best-practices
  prompt: What are the key best practices and pitfalls for azure keyvault secrets
    rust?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for azure keyvault secrets rust
  tags:
  - azure
  - best-practices
- id: azure-keyvault-secrets-rust-antipatterns
  prompt: What are the most common mistakes to avoid with azure keyvault secrets rust?
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
# azure-keyvault-secrets-rust

# Azure Key Vault Secrets SDK for Rust

Client library for Azure Key Vault Secrets — secure storage for passwords, API keys, and other secrets.

## Installation

```sh
cargo add azure_security_keyvault_secrets azure_identity
```

## Environment Variables

```bash
AZURE_KEYVAULT_URL=https://<vault-name>.vault.azure.net/
```

## Authentication

```rust
use azure_identity::DeveloperToolsCredential;
use azure_security_keyvault_secrets::SecretClient;

let credential = DeveloperToolsCredential::new(None)?;
let client = SecretClient::new(
    "https://<vault-name>.vault.azure.net/",
    credential.clone(),
    None,
)?;
```

## Core Operations

### Get Secret

```rust
let secret = client
    .get_secret("secret-name", None)
    .await?
    .into_model()?;

println!("Secret value: {:?}", secret.value);
```

### Set Secret

```rust
use azure_security_keyvault_secrets::models::SetSecretParameters;

let params = SetSecretParameters {
    value: Some("secret-value".into()),
    ..Default::default()
};

let secret = client
    .set_secret("secret-name", params.try_into()?, None)
    .await?
    .into_model()?;
```

### Update Secret Properties

```rust
use azure_security_keyvault_secrets::models::UpdateSecretPropertiesParameters;
use std::collections::HashMap;

let params = UpdateSecretPropertiesParameters {
    content_type: Some("text/plain".into()),
    tags: Some(HashMap::from([("env".into(), "prod".into())])),
    ..Default::default()
};

client
    .update_secret_properties("secret-name", params.try_into()?, None)
    .await?;
```

### Delete Secret

```rust
client.delete_secret("secret-name", None).await?;
```

### List Secrets

```rust
use azure_security_keyvault_secrets::ResourceExt;
use futures::TryStreamExt;

let mut pager = client.list_secret_properties(None)?.into_stream();
while let Some(secret) = pager.try_next().await? {
    let name = secret.resource_id()?.name;
    println!("Secret: {}", name);
}
```

### Get Specific Version

```rust
use azure_security_keyvault_secrets::models::SecretClientGetSecretOptions;

let options = SecretClientGetSecretOptions {
    secret_version: Some("version-id".into()),
    ..Default::default()
};

let secret = client
    .get_secret("secret-name", Some(options))
    .await?
    .into_model()?;
```

## Best Practices

1. **Use Entra ID auth** — `DeveloperToolsCredential` for dev, `ManagedIdentityCredential` for production
2. **Use `into_model()?`** — to deserialize responses
3. **Use `ResourceExt` trait** — for extracting names from IDs
4. **Handle soft delete** — deleted secrets can be recovered within retention period
5. **Set content type** — helps identify secret format
6. **Use tags** — for organizing and filtering secrets
7. **Version secrets** — new values create new versions automatically

## RBAC Permissions

Assign these Key Vault roles:
- `Key Vault Secrets User` — get and list
- `Key Vault Secrets Officer` — full CRUD

## Reference Links

| Resource | Link |
|----------|------|
| API Reference | https://docs.rs/azure_security_keyvault_secrets |
| Source Code | https://github.com/Azure/azure-sdk-for-rust/tree/main/sdk/keyvault/azure_security_keyvault_secrets |
| crates.io | https://crates.io/crates/azure_security_keyvault_secrets |

## When to Use
This skill is applicable to execute the workflow or actions described in the overview.
