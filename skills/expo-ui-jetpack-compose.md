---
name: expo-ui-jetpack-compose
version: 1.0.0
description: expo-ui-jetpack-compose
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - when working on expo ui jetpack compose
eval_cases:
- id: expo-ui-jetpack-compose-approach
  prompt: How should I approach expo ui jetpack compose for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on expo ui jetpack compose
  tags:
  - expo
- id: expo-ui-jetpack-compose-best-practices
  prompt: What are the key best practices and pitfalls for expo ui jetpack compose?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for expo ui jetpack compose
  tags:
  - expo
  - best-practices
- id: expo-ui-jetpack-compose-antipatterns
  prompt: What are the most common mistakes to avoid with expo ui jetpack compose?
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
# expo-ui-jetpack-compose

---
name: expo-ui-jetpack-compose
description: `@expo/ui/jetpack-compose` package lets you use Jetpack Compose Views and modifiers in your app.
---

> The instructions in this skill apply to SDK 55 only. For other SDK versions, refer to the Expo UI Jetpack Compose docs for that version for the most accurate information.

## Installation

```bash
npx expo install @expo/ui
```

A native rebuild is required after installation (`npx expo run:android`).

## Instructions

- Expo UI's API mirrors Jetpack Compose's API. Use Jetpack Compose and Material Design 3 knowledge to decide which components or modifiers to use.
- Components are imported from `@expo/ui/jetpack-compose`, modifiers from `@expo/ui/jetpack-compose/modifiers`.
- When about to use a component, fetch its docs to confirm the API - https://docs.expo.dev/versions/v55.0.0/sdk/ui/jetpack-compose/{component-name}/index.md
- When unsure about a modifier's API, refer to the docs - https://docs.expo.dev/versions/v55.0.0/sdk/ui/jetpack-compose/modifiers/index.md
- Every Jetpack Compose tree must be wrapped in `Host`. Use `<Host matchContents>` for intrinsic sizing, or `<Host style={{ flex: 1 }}>` when you need explicit size (e.g. as a parent of `LazyColumn`). Example:

```jsx
import { Host, Column, Button, Text } from "@expo/ui/jetpack-compose";
import { fillMaxWidth, paddingAll } from "@expo/ui/jetpack-compose/modifiers";

<Host matchContents>
  <Column verticalArrangement={{ spacedBy: 8 }} modifiers={[fillMaxWidth(), paddingAll(16)]}>
    <Text style={{ typography: "titleLarge" }}>Hello</Text>
    <Button onPress={() => alert("Pressed!")}>Press me</Button>
  </Column>
</Host>;
```

## Key Components

- **LazyColumn** — Use instead of react-native `ScrollView`/`FlatList` for scrollable lists. Wrap in `<Host style={{ flex: 1 }}>`.
- **Icon** — Use `<Icon source={require('./icon.xml')} size={24} />` with Android XML vector drawables from [Material Symbols](https://fonts.google.com/icons).
