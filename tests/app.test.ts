import { describe, it, expect, beforeEach } from 'vitest';
import { App } from '../src/app';

describe('App', () => {
  let app: App;

  beforeEach(() => {
    app = new App();
  });

  it('should create an instance', () => {
    expect(app).toBeDefined();
  });

  it('should not be initialized by default', () => {
    expect(app.isInitialized()).toBe(false);
  });

  it('should not be running by default', () => {
    expect(app.isRunning()).toBe(false);
  });

  it('should initialize successfully', async () => {
    await app.initialize({});
    expect(app.isInitialized()).toBe(true);
  });

  it('should start after initialization', async () => {
    await app.initialize({});
    app.start();
    expect(app.isRunning()).toBe(true);
  });

  it('should throw when starting without initialization', () => {
    expect(() => app.start()).toThrow('Application must be initialized before starting');
  });

  it('should stop successfully', async () => {
    await app.initialize({});
    app.start();
    app.stop();
    expect(app.isRunning()).toBe(false);
  });
});
