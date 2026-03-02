import { HallucinationDetector } from '../src/validation/hallucination_detector';
import { ToolResult } from '../src/types/agent';

describe('HallucinationDetector', () => {
  let detector: HallucinationDetector;

  beforeEach(() => {
    detector = new HallucinationDetector();
  });

  it('should detect contradiction when agent claims file does not exist but list_files shows it exists', async () => {
    const agentClaim = 'The backend folder does not exist in the project';
    const toolResults: ToolResult[] = [
      {
        tool: 'list_files',
        output: JSON.stringify(['src/backend/app.module.ts', 'src/backend/main.ts']),
        success: true,
      },
    ];

    const result = await detector.detect(agentClaim, toolResults);

    expect(result.isValid).toBe(false);
    expect(result.confidence).toBeLessThan(0.5);
    expect(result.contradictions).toHaveLength(1);
    expect(result.contradictions[0].severity).toBe('critical');
  });

  it('should pass when agent claim matches evidence', async () => {
    const agentClaim = 'I found the backend folder with app.module.ts';
    const toolResults: ToolResult[] = [
      {
        tool: 'list_files',
        output: JSON.stringify(['src/backend/app.module.ts', 'src/backend/main.ts']),
        success: true,
      },
    ];

    const result = await detector.detect(agentClaim, toolResults);

    expect(result.isValid).toBe(true);
    expect(result.confidence).toBeGreaterThan(0.8);
  });

  it('should handle empty tool results gracefully', async () => {
    const agentClaim = 'I created the file successfully';
    const toolResults: ToolResult[] = [];

    const result = await detector.detect(agentClaim, toolResults);

    expect(result.isValid).toBe(true);
    expect(result.contradictions).toHaveLength(0);
  });
});