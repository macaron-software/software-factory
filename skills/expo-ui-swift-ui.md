---
name: expo-ui-swift-ui
version: 1.0.0
description: expo-ui-swift-ui
metadata:
  category: design
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - when working on expo ui swift ui
eval_cases:
- id: expo-ui-swift-ui-approach
  prompt: How should I approach expo ui swift ui for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on expo ui swift ui
  tags:
  - expo
- id: expo-ui-swift-ui-best-practices
  prompt: What are the key best practices and pitfalls for expo ui swift ui?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for expo ui swift ui
  tags:
  - expo
  - best-practices
- id: expo-ui-swift-ui-antipatterns
  prompt: What are the most common mistakes to avoid with expo ui swift ui?
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
# expo-ui-swift-ui

---
name: expo-ui-swift-ui
description: `@expo/ui/swift-ui` package lets you use SwiftUI Views and modifiers in your app.
---

> The instructions in this skill apply to SDK 55 only. For other SDK versions, refer to the Expo UI SwiftUI docs for that version for the most accurate information.

## Installation

```bash
npx expo install @expo/ui
```

A native rebuild is required after installation (`npx expo run:ios`).

## Instructions

- Expo UI's API mirrors SwiftUI's API. Use SwiftUI knowledge to decide which components or modifiers to use.
- Components are imported from `@expo/ui/swift-ui`, modifiers from `@expo/ui/swift-ui/modifiers`.
- When about to use a component, fetch its docs to confirm the API - https://docs.expo.dev/versions/v55.0.0/sdk/ui/swift-ui/{component-name}/index.md
- When unsure about a modifier's API, refer to the docs - https://docs.expo.dev/versions/v55.0.0/sdk/ui/swift-ui/modifiers/index.md
- Every SwiftUI tree must be wrapped in `Host`.
- `RNHostView` is specifically for embedding RN components inside a SwiftUI tree. Example:

```jsx
import { Host, VStack, RNHostView } from "@expo-ui/swift-ui";
import { Pressable } from "react-native";

<Host matchContents>
  <VStack>
    <RNHostView matchContents>
      // Here, `Pressable` is an RN component so it is wrapped in `RNHostView`.
      <Pressable />
    </RNHostView>
  </VStack>
</Host>;
```

- If a required modifier or View is missing in Expo UI, it can be extended via a local Expo module. See: https://docs.expo.dev/guides/expo-ui-swift-ui/extending/index.md. Confirm with the user before extending.
