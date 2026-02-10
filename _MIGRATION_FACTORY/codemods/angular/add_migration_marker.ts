/**
 * Codemod: Add Migration Markers
 *
 * Adds migration markers (comments) to migrated files to track status.
 *
 * Usage:
 *   jscodeshift -t add_migration_marker.ts src/ \
 *     --task-id=standalone-auth-001 \
 *     --phase=standalone
 *
 * Output:
 *   /**
 *    * MIGRATION: Angular 16 → 17
 *    * Phase: standalone
 *    * Date: 2026-02-10
 *    * Task: standalone-auth-001
 *    * Status: MIGRATED ✅
 *    *\/
 *   @Component({ ... })
 */

import type { Transform, FileInfo, API, Options } from 'jscodeshift';

const transform: Transform = (file: FileInfo, api: API, options: Options) => {
  const j = api.jscodeshift;
  const root = j(file.source);

  // Get options
  const taskId = options.taskId || process.env.TASK_ID || 'unknown';
  const phase = options.phase || process.env.MIGRATION_PHASE || 'unknown';
  const date = new Date().toISOString().split('T')[0];
  const status = options.status || 'MIGRATED ✅';

  // Migration marker template
  const markerText = `
MIGRATION: Angular 16 → 17
Phase: ${phase}
Date: ${date}
Task: ${taskId}
Status: ${status}
  `.trim();

  // Find standalone components (migrated from NgModule)
  root.find(j.Decorator, {
    expression: {
      callee: { name: 'Component' }
    }
  })
  .filter((path) => {
    // Only add marker if standalone: true
    const args = path.value.expression.arguments;
    if (args.length === 0) return false;

    const config = args[0];
    if (config.type !== 'ObjectExpression') return false;

    const standaloneProp = config.properties.find(
      (prop: any) => prop.key?.name === 'standalone'
    );

    return standaloneProp?.value?.value === true;
  })
  .forEach((path) => {
    // Add migration marker comment
    const marker = j.commentBlock(`*\n * ${markerText.split('\n').join('\n * ')}\n `, false, true);

    // Check if marker already exists
    const existingComments = path.value.comments || [];
    const hasMarker = existingComments.some(
      (comment: any) => comment.value.includes('MIGRATION:')
    );

    if (!hasMarker) {
      path.value.comments = [marker, ...(path.value.comments || [])];
    }
  });

  // Find typed forms (migrated from untyped)
  root.find(j.VariableDeclarator, {
    init: {
      callee: {
        object: { name: 'FormBuilder' },
        property: { name: 'group' }
      }
    }
  })
  .filter((path) => {
    // Check if TypeScript generic is present (typed form)
    const init = path.value.init;
    return init && 'typeParameters' in init && init.typeParameters;
  })
  .forEach((path) => {
    const marker = j.commentBlock(` ${markerText} `, false, false);

    const parent = path.parent;
    if (parent && parent.value) {
      const hasMarker = (parent.value.comments || []).some(
        (comment: any) => comment.value.includes('MIGRATION:')
      );

      if (!hasMarker) {
        parent.value.comments = [marker, ...(parent.value.comments || [])];
      }
    }
  });

  return root.toSource({ quote: 'single' });
};

export default transform;
