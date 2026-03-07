---
name: terraform-aws-modules
version: 1.0.0
description: Terraform module creation for AWS — reusable modules, state management,
  and HCL best practices. Use when building or reviewing Terraform AWS infrastructure.
metadata:
  category: ops
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - building or reviewing terraform aws infrastructure
  - creating reusable terraform modules for aws resources
  - reviewing terraform code for best practices and security
  - designing remote state and workspace strategies
eval_cases:
- id: terraform-aws-modules-approach
  prompt: How should I approach terraform aws modules for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on terraform aws modules
  tags:
  - terraform
- id: terraform-aws-modules-best-practices
  prompt: What are the key best practices and pitfalls for terraform aws modules?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for terraform aws modules
  tags:
  - terraform
  - best-practices
- id: terraform-aws-modules-antipatterns
  prompt: What are the most common mistakes to avoid with terraform aws modules?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - terraform
  - antipatterns
---
# terraform-aws-modules

You are an expert in Terraform for AWS specializing in reusable module design, state management, and production-grade HCL patterns.

## Use this skill when

- Creating reusable Terraform modules for AWS resources
- Reviewing Terraform code for best practices and security
- Designing remote state and workspace strategies
- Migrating from CloudFormation or manual setup to Terraform

## Do not use this skill when

- The user needs AWS CDK or CloudFormation, not Terraform
- The infrastructure is on a non-AWS provider

## Instructions

1. Structure modules with clear `variables.tf`, `outputs.tf`, `main.tf`, and `versions.tf`.
2. Pin provider and module versions to avoid breaking changes.
3. Use remote state (S3 + DynamoDB locking) for team environments.
4. Apply `terraform fmt` and `terraform validate` before commits.
5. Use `for_each` over `count` for resources that need stable identity.
6. Tag all resources consistently using a `default_tags` block in the provider.

## Examples

### Example 1: Reusable VPC Module

```hcl
# modules/vpc/variables.tf
variable "name" { type = string }
variable "cidr" { type = string, default = "10.0.0.0/16" }
variable "azs" { type = list(string) }

# modules/vpc/main.tf
resource "aws_vpc" "this" {
  cidr_block           = var.cidr
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags = { Name = var.name }
}

# modules/vpc/outputs.tf
output "vpc_id" { value = aws_vpc.this.id }
```

### Example 2: Remote State Backend

```hcl
terraform {
  backend "s3" {
    bucket         = "my-tf-state"
    key            = "prod/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "tf-lock"
    encrypt        = true
  }
}
```

## Best Practices

- ✅ **Do:** Pin provider versions in `versions.tf`
- ✅ **Do:** Use `terraform plan` output in PR reviews
- ✅ **Do:** Store state in S3 with DynamoDB locking and encryption
- ❌ **Don't:** Use `count` when resource identity matters — use `for_each`
- ❌ **Don't:** Commit `.tfstate` files to version control

## Troubleshooting

**Problem:** State lock not released after a failed apply
**Solution:** Run `terraform force-unlock <LOCK_ID>` after confirming no other operations are running.
