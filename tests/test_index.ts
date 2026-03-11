import { describe, it, expect } from 'vitest';
import { someFunction } from '../src/index';

describe('someFunction', () => {
  it('should return expected value', () => {
    expect(someFunction()).toBe('expected');
  });
});
