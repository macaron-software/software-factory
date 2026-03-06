/**
 * TDD Phase: RED - Tests first
 * File: tests/metrics-export.test.js
 */

const request = require('supertest');
const app = require('../src/app');

// Mock metrics service
jest.mock('../src/services/metricsService', () => ({
  getBatchMetrics: jest.fn()
}));

const metricsService = require('../src/services/metricsService');

describe('GET /api/v1/metrics/batch-export', () => {
  
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Happy path', () => {
    it('should return 200 with CSV content', async () => {
      metricsService.getBatchMetrics.mockResolvedValue([
        { timestamp: '2024-01-01T00:00:00Z', metric_name: 'cpu_usage', value: 45.2 },
        { timestamp: '2024-01-01T00:01:00Z', metric_name: 'memory_usage', value: 72.8 }
      ]);

      const response = await request(app)
        .get('/api/v1/metrics/batch-export')
        .expect(200);

      expect(response.headers['content-type']).toContain('text/csv');
      expect(response.headers['content-disposition']).toContain('attachment');
      expect(response.text).toContain('timestamp,metric_name,value');
    });

    it('should filter by date range', async () => {
      metricsService.getBatchMetrics.mockResolvedValue([]);

      await request(app)
        .get('/api/v1/metrics/batch-export?from=2024-01-01&to=2024-01-31')
        .expect(200);

      expect(metricsService.getBatchMetrics).toHaveBeenCalledWith({
        from: '2024-01-01',
        to: '2024-01-31'
      });
    });
  });

  describe('Validation errors', () => {
    it('should return 400 if from parameter is invalid', async () => {
      const response = await request(app)
        .get('/api/v1/metrics/batch-export?from=not-a-date')
        .expect(400);

      expect(response.body.error).toContain('from');
    });

    it('should return 400 if to parameter is invalid', async () => {
      const response = await request(app)
        .get('/api/v1/metrics/batch-export?to=invalid')
        .expect(400);

      expect(response.body.error).toContain('to');
    });

    it('should return 400 if from > to', async () => {
      const response = await request(app)
        .get('/api/v1/metrics/batch-export?from=2024-02-01&to=2024-01-01')
        .expect(400);

      expect(response.body.error).toContain('from');
    });
  });

  describe('Error handling', () => {
    it('should return 500 if metricsService throws', async () => {
      metricsService.getBatchMetrics.mockRejectedValue(
        new Error('Database connection failed')
      );

      const response = await request(app)
        .get('/api/v1/metrics/batch-export')
        .expect(500);

      expect(response.body.error).toContain('Erreur interne');
    });

    it('should handle empty dataset', async () => {
      metricsService.getBatchMetrics.mockResolvedValue([]);

      const response = await request(app)
        .get('/api/v1/metrics/batch-export')
        .expect(200);

      expect(response.text).toContain('timestamp,metric_name,value');
    });
  });
});