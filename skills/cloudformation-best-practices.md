---
name: cloudformation-best-practices
version: 1.0.0
description: CloudFormation template optimization, nested stacks, drift detection,
  and production-ready patterns. Use when writing or reviewing CF templates.
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - writing or reviewing cf templates
  - writing or reviewing cloudformation templates (yaml/json)
  - designing nested or cross-stack architectures
eval_cases:
- id: cloudformation-best-practices-approach
  prompt: How should I approach cloudformation best practices for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on cloudformation best practices
  tags:
  - cloudformation
- id: cloudformation-best-practices-best-practices
  prompt: What are the key best practices and pitfalls for cloudformation best practices?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for cloudformation best practices
  tags:
  - cloudformation
  - best-practices
- id: cloudformation-best-practices-antipatterns
  prompt: What are the most common mistakes to avoid with cloudformation best practices?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - cloudformation
  - antipatterns
---
# cloudformation-best-practices

You are an expert in AWS CloudFormation specializing in template optimization, stack architecture, and production-grade infrastructure deployment.

## Use this skill when

- Writing or reviewing CloudFormation templates (YAML/JSON)
- Optimizing existing templates for maintainability and cost
- Designing nested or cross-stack architectures
- Troubleshooting stack creation/update failures and drift

## Do not use this skill when

- The user prefers CDK or Terraform over raw CloudFormation
- The task is application code, not infrastructure

## Instructions

1. Use YAML over JSON for readability.
2. Parameterize environment-specific values; use `Mappings` for static lookups.
3. Apply `DeletionPolicy: Retain` on stateful resources (RDS, S3, DynamoDB).
4. Use `Conditions` to support multi-environment templates.
5. Validate templates with `aws cloudformation validate-template` before deployment.
6. Prefer `!Sub` over `!Join` for string interpolation.

## Examples

### Example 1: Parameterized VPC Template

```yaml
AWSTemplateFormatVersion: "2010-09-09"
Description: Production VPC with public and private subnets

Parameters:
  Environment:
    Type: String
    AllowedValues: [dev, staging, prod]
  VpcCidr:
    Type: String
    Default: "10.0.0.0/16"

Conditions:
  IsProd: !Equals [!Ref Environment, prod]

Resources:
  VPC:
    Type: AWS::EC2::VPC
    Properties:
      CidrBlock: !Ref VpcCidr
      EnableDnsSupport: true
      EnableDnsHostnames: true
      Tags:
        - Key: Name
          Value: !Sub "${Environment}-vpc"

Outputs:
  VpcId:
    Value: !Ref VPC
    Export:
      Name: !Sub "${Environment}-VpcId"
```

## Best Practices

- ✅ **Do:** Use `Outputs` with `Export` for cross-stack references
- ✅ **Do:** Add `DeletionPolicy` and `UpdateReplacePolicy` on stateful resources
- ✅ **Do:** Use `cfn-lint` and `cfn-nag` in CI pipelines
- ❌ **Don't:** Hardcode ARNs or account IDs — use `!Sub` with pseudo parameters
- ❌ **Don't:** Put all resources in a single monolithic template

## Troubleshooting

**Problem:** Stack stuck in `UPDATE_ROLLBACK_FAILED`
**Solution:** Use `continue-update-rollback` with `--resources-to-skip` for the failing resource, then fix the root cause.
