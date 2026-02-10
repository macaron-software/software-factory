# Skill: Codemod Patterns - AST Transformations

## Purpose

Automate code transformations using Abstract Syntax Tree (AST) manipulation.

**When to use codemods:**
- Repetitive transformations (100+ files)
- Syntax changes (e.g., `*ngIf` → `@if`)
- Type annotations (`FormGroup` → `FormGroup<T>`)
- Import rewrites (`@angular/http` → `@angular/common/http`)

**When NOT to use codemods:**
- Architectural changes (e.g., NgModule → Standalone bootstrap)
- Business logic changes
- Complex refactoring requiring human judgment

## Tools

### JavaScript/TypeScript: jscodeshift

```bash
npm install -g jscodeshift
jscodeshift -t codemods/my-transform.ts src/**/*.ts
```

### Python: libcst

```bash
pip install libcst
python codemods/my-transform.py src/
```

### Java: OpenRewrite

```xml
<plugin>
  <groupId>org.openrewrite.maven</groupId>
  <artifactId>rewrite-maven-plugin</artifactId>
</plugin>
```

## Codemod Structure (jscodeshift)

```typescript
import { Transform, FileInfo, API } from 'jscodeshift';

const transform: Transform = (file: FileInfo, api: API) => {
  const j = api.jscodeshift;
  const root = j(file.source);

  // 1. Find nodes to transform
  root.find(j.CallExpression, {
    callee: { property: { name: 'forRoot' } }
  })
    .forEach(path => {
      // 2. Transform node
      // ...
    });

  // 3. Return modified source
  return root.toSource();
};

export default transform;
```

## Common Patterns

### 1. Replace Function Call

**Goal:** `console.log()` → `logger.info()`

```typescript
const transform: Transform = (file, api) => {
  const j = api.jscodeshift;
  const root = j(file.source);

  root.find(j.CallExpression, {
    callee: {
      object: { name: 'console' },
      property: { name: 'log' }
    }
  })
    .replaceWith(path => {
      return j.callExpression(
        j.memberExpression(
          j.identifier('logger'),
          j.identifier('info')
        ),
        path.node.arguments
      );
    });

  return root.toSource();
};
```

### 2. Add Type Parameter

**Goal:** `ModuleWithProviders` → `ModuleWithProviders<AppModule>`

```typescript
const transform: Transform = (file, api) => {
  const j = api.jscodeshift;
  const root = j(file.source);

  // Find class name
  const className = root.find(j.ClassDeclaration).get().node.id.name;

  // Find ModuleWithProviders without type parameter
  root.find(j.TSTypeReference, {
    typeName: { name: 'ModuleWithProviders' }
  })
    .filter(path => !path.node.typeParameters)
    .replaceWith(path => {
      return j.tsTypeReference(
        j.identifier('ModuleWithProviders'),
        j.tsTypeParameterInstantiation([
          j.tsTypeReference(j.identifier(className))
        ])
      );
    });

  return root.toSource();
};
```

### 3. Migrate Template Syntax

**Goal:** `*ngIf` → `@if`

```typescript
const transform: Transform = (file, api) => {
  const j = api.jscodeshift;

  // For HTML templates, use regex (jscodeshift is for JS/TS)
  let content = file.source;

  // *ngIf="condition" → @if (condition) { ... }
  content = content.replace(
    /<(\w+)\s+\*ngIf="([^"]+)"([^>]*)>(.*?)<\/\1>/gs,
    (match, tag, condition, attrs, innerContent) => {
      return `@if (${condition}) {\n  <${tag}${attrs}>${innerContent}</${tag}>\n}`;
    }
  );

  return content;
};
```

### 4. Add Import

**Goal:** Ensure `import { CommonModule } from '@angular/common'`

```typescript
const transform: Transform = (file, api) => {
  const j = api.jscodeshift;
  const root = j(file.source);

  // Check if import already exists
  const existingImport = root.find(j.ImportDeclaration, {
    source: { value: '@angular/common' }
  });

  if (existingImport.length === 0) {
    // Add import at top
    const newImport = j.importDeclaration(
      [j.importSpecifier(j.identifier('CommonModule'))],
      j.literal('@angular/common')
    );

    root.find(j.Program).get('body', 0).insertBefore(newImport);
  }

  return root.toSource();
};
```

### 5. Rename Property

**Goal:** `FormGroup` → `FormGroup<UserForm>`

```typescript
const transform: Transform = (file, api) => {
  const j = api.jscodeshift;
  const root = j(file.source);

  // Find interface for form
  const formInterface = root.find(j.TSInterfaceDeclaration, {
    id: { name: /Form$/ } // Ends with "Form"
  });

  if (formInterface.length === 0) {
    // No interface found, skip
    return root.toSource();
  }

  const interfaceName = formInterface.get().node.id.name;

  // Add type parameter to FormGroup
  root.find(j.TSTypeReference, {
    typeName: { name: 'FormGroup' }
  })
    .replaceWith(path => {
      return j.tsTypeReference(
        j.identifier('FormGroup'),
        j.tsTypeParameterInstantiation([
          j.tsTypeReference(j.identifier(interfaceName))
        ])
      );
    });

  return root.toSource();
};
```

## Testing Codemods

```typescript
// __tests__/my-transform.test.ts
import { describe, it, expect } from '@jest/globals';
import jscodeshift from 'jscodeshift';
import transform from '../my-transform';

describe('my-transform', () => {
  it('transforms console.log to logger.info', () => {
    const input = `console.log('hello');`;
    const expected = `logger.info('hello');`;

    const output = transform(
      { path: 'test.ts', source: input },
      { jscodeshift },
      {}
    );

    expect(output).toBe(expected);
  });

  it('does not change logger.info', () => {
    const input = `logger.info('hello');`;

    const output = transform(
      { path: 'test.ts', source: input },
      { jscodeshift },
      {}
    );

    expect(output).toBe(input); // Unchanged
  });
});
```

## Best Practices

### 1. Dry Run First

```bash
# Show changes without writing
jscodeshift -t transform.ts --dry --print src/**/*.ts
```

### 2. One Transformation Per Codemod

**Good:**
- `standalone-components.ts` (NgModule → Standalone)
- `typed-forms.ts` (FormGroup → FormGroup<T>)

**Bad:**
- `angular-17-all.ts` (everything at once)

**Reason:** Easier to test, debug, rollback.

### 3. Preserve Formatting

```typescript
// Use prettier after transformation
import prettier from 'prettier';

const transform: Transform = (file, api) => {
  // ... transformations

  let output = root.toSource();

  // Format
  output = prettier.format(output, {
    parser: 'typescript',
    singleQuote: true,
    semi: true
  });

  return output;
};
```

### 4. Add Comments

```typescript
// Mark transformed code
j.commentLine(' AUTO-GENERATED by codemod: standalone-components.ts', true);
```

### 5. Skip Generated Files

```typescript
const transform: Transform = (file, api) => {
  // Skip if file contains "@generated"
  if (file.source.includes('@generated')) {
    return file.source;
  }

  // ... transformations
};
```

## Example: Angular Standalone Codemod

```typescript
// codemods/angular/standalone.ts
import { Transform } from 'jscodeshift';

const transform: Transform = (file, api) => {
  const j = api.jscodeshift;
  const root = j(file.source);

  // 1. Find @Component decorator
  const component = root.find(j.Decorator, {
    expression: {
      callee: { name: 'Component' }
    }
  });

  if (component.length === 0) return root.toSource();

  // 2. Add standalone: true
  component.forEach(path => {
    const properties = path.node.expression.arguments[0].properties;

    // Check if standalone already exists
    const hasStandalone = properties.some(
      prop => prop.key.name === 'standalone'
    );

    if (!hasStandalone) {
      properties.push(
        j.property(
          'init',
          j.identifier('standalone'),
          j.literal(true)
        )
      );
    }
  });

  // 3. Add imports: [CommonModule, ...]
  component.forEach(path => {
    const properties = path.node.expression.arguments[0].properties;

    // Find imports property
    const importsProp = properties.find(
      prop => prop.key.name === 'imports'
    );

    if (!importsProp) {
      // Add imports: [CommonModule]
      properties.push(
        j.property(
          'init',
          j.identifier('imports'),
          j.arrayExpression([
            j.identifier('CommonModule')
          ])
        )
      );
    }
  });

  // 4. Add import statement
  const existingImport = root.find(j.ImportDeclaration, {
    source: { value: '@angular/common' }
  });

  if (existingImport.length === 0) {
    const newImport = j.importDeclaration(
      [j.importSpecifier(j.identifier('CommonModule'))],
      j.literal('@angular/common')
    );

    root.find(j.Program).get('body', 0).insertBefore(newImport);
  }

  return root.toSource();
};

export default transform;
```

**Usage:**
```bash
jscodeshift -t codemods/angular/standalone.ts \
  ai08-admin-ihm/src/**/*.component.ts
```

## Anti-Patterns (Adversarial Rejects)

- ❌ Modifying business logic (codemods for syntax only)
- ❌ No tests for codemod
- ❌ No dry-run verification
- ❌ Transforming generated files
- ❌ One giant codemod (hard to debug)
- ❌ No formatting after transformation
- ❌ Ignoring edge cases

## Integration with Transform Worker

```python
class TransformWorker:
    async def execute_transform(self, task: MigrationTask):
        if task.codemod_available:
            # Run codemod
            codemod_path = task.context.get('codemod')
            files_pattern = task.context.get('files_pattern')

            cmd = f"jscodeshift -t {codemod_path} {files_pattern}"
            returncode, output = await run_subprocess(cmd)

            if returncode != 0:
                return TransformResult.FAILED(reason=output)

            # Verify transformation worked
            # ...
        else:
            # Fallback: LLM transformation
            # ...
```

## References

- jscodeshift: https://github.com/facebook/jscodeshift
- AST Explorer: https://astexplorer.net/ (visualize AST)
- libcst (Python): https://libcst.readthedocs.io/
- OpenRewrite (Java): https://docs.openrewrite.org/
- Codemod Patterns: https://github.com/reactjs/react-codemod
