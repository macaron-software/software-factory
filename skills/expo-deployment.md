---
name: expo-deployment
version: 1.0.0
description: Deploy Expo apps to production
metadata:
  category: ops
  source: 'antigravity-awesome-skills (MIT) — source: https://github.com/expo/skills/tree/main/plugins/expo-deployment'
  triggers:
  - setting up over-the-air (ota) updates
eval_cases:
- id: expo-deployment-approach
  prompt: How should I approach expo deployment for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on expo deployment
  tags:
  - expo
- id: expo-deployment-best-practices
  prompt: What are the key best practices and pitfalls for expo deployment?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for expo deployment
  tags:
  - expo
  - best-practices
- id: expo-deployment-antipatterns
  prompt: What are the most common mistakes to avoid with expo deployment?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - expo
  - antipatterns
---
# expo-deployment

# Expo Deployment

## Overview

Deploy Expo applications to production environments, including app stores and over-the-air updates.

## When to Use This Skill

Use this skill when you need to deploy Expo apps to production.

Use this skill when:
- Deploying Expo apps to production
- Publishing to app stores (iOS App Store, Google Play)
- Setting up over-the-air (OTA) updates
- Configuring production build settings
- Managing release channels and versions

## Instructions

This skill provides guidance for deploying Expo apps:

1. **Build Configuration**: Set up production build settings
2. **App Store Submission**: Prepare and submit to app stores
3. **OTA Updates**: Configure over-the-air update channels
4. **Release Management**: Manage versions and release channels
5. **Production Optimization**: Optimize apps for production

## Deployment Workflow

### Pre-Deployment

1. Ensure all tests pass
2. Update version numbers
3. Configure production environment variables
4. Review and optimize app bundle size
5. Test production builds locally

### App Store Deployment

1. Build production binaries (iOS/Android)
2. Configure app store metadata
3. Submit to App Store Connect / Google Play Console
4. Manage app store listings and screenshots
5. Handle app review process

### OTA Updates

1. Configure update channels (production, staging, etc.)
2. Build and publish updates
3. Manage rollout strategies
4. Monitor update adoption
5. Handle rollbacks if needed

## Best Practices

- Use EAS Build for reliable production builds
- Test production builds before submission
- Implement proper error tracking and analytics
- Use release channels for staged rollouts
- Keep app store metadata up to date
- Monitor app performance in production

## Resources

For more information, see the [source repository](https://github.com/expo/skills/tree/main/plugins/expo-deployment).
