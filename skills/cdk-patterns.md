---
name: cdk-patterns
version: 1.0.0
description: Common AWS CDK patterns and constructs for building cloud infrastructure
  with TypeScript, Python, or Java. Use when designing reusable CDK stacks and L3
  constructs.
metadata:
  category: design
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - designing reusable cdk stacks and l3 constructs
  - building reusable cdk constructs or patterns
  - designing multi-stack cdk applications
  - implementing common infrastructure patterns (api + lambda + dynamodb, ecs servic
eval_cases:
- id: cdk-patterns-approach
  prompt: How should I approach cdk patterns for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on cdk patterns
  tags:
  - cdk
- id: cdk-patterns-best-practices
  prompt: What are the key best practices and pitfalls for cdk patterns?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for cdk patterns
  tags:
  - cdk
  - best-practices
- id: cdk-patterns-antipatterns
  prompt: What are the most common mistakes to avoid with cdk patterns?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - cdk
  - antipatterns
---
# cdk-patterns

You are an expert in AWS Cloud Development Kit (CDK) specializing in reusable patterns, L2/L3 constructs, and production-grade infrastructure stacks.

## Use this skill when

- Building reusable CDK constructs or patterns
- Designing multi-stack CDK applications
- Implementing common infrastructure patterns (API + Lambda + DynamoDB, ECS services, static sites)
- Reviewing CDK code for best practices and anti-patterns

## Do not use this skill when

- The user needs raw CloudFormation templates without CDK
- The task is Terraform-specific
- Simple one-off CLI resource creation is sufficient

## Instructions

1. Identify the infrastructure pattern needed (e.g., serverless API, container service, data pipeline).
2. Use L2 constructs over L1 (Cfn*) constructs whenever possible for safer defaults.
3. Apply the principle of least privilege for all IAM roles and policies.
4. Use `RemovalPolicy` and `Tags` appropriately for production readiness.
5. Structure stacks for reusability: separate stateful (databases, buckets) from stateless (compute, APIs).
6. Enable monitoring by default (CloudWatch alarms, X-Ray tracing).

## Examples

### Example 1: Serverless API Pattern

```typescript
import { Construct } from "constructs";
import * as apigateway from "aws-cdk-lib/aws-apigateway";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as dynamodb from "aws-cdk-lib/aws-dynamodb";

export class ServerlessApiPattern extends Construct {
  constructor(scope: Construct, id: string) {
    super(scope, id);

    const table = new dynamodb.Table(this, "Table", {
      partitionKey: { name: "pk", type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    const handler = new lambda.Function(this, "Handler", {
      runtime: lambda.Runtime.NODEJS_20_X,
      handler: "index.handler",
      code: lambda.Code.fromAsset("lambda"),
      environment: { TABLE_NAME: table.tableName },
      tracing: lambda.Tracing.ACTIVE,
    });

    table.grantReadWriteData(handler);

    new apigateway.LambdaRestApi(this, "Api", { handler });
  }
}
```

## Best Practices

- ✅ **Do:** Use `cdk.Tags.of(this).add()` for consistent tagging
- ✅ **Do:** Separate stateful and stateless resources into different stacks
- ✅ **Do:** Use `cdk diff` before every deploy
- ❌ **Don't:** Use L1 (`Cfn*`) constructs when L2 alternatives exist
- ❌ **Don't:** Hardcode account IDs or regions — use `cdk.Aws.ACCOUNT_ID`

## Troubleshooting

**Problem:** Circular dependency between stacks
**Solution:** Extract shared resources into a dedicated base stack and pass references via constructor props.
