// tests/api.test.js
// Run with: npm test
// These are integration smoke-tests – they mock Snowflake so no live DB needed.

jest.mock('../src/config/snowflake', () => ({
  executeQuery: jest.fn(),
  streamQuery:  jest.fn(),
  healthCheck:  jest.fn().mockResolvedValue(true),
}));

const request    = require('supertest');
const app        = require('../src/server');
const { executeQuery } = require('../src/config/snowflake');
const jwt        = require('jsonwebtoken');

process.env.JWT_SECRET             = 'test-secret-at-least-32-chars!!!';
process.env.REFRESH_TOKEN_SECRET   = 'refresh-test-secret-at-least-32!!';
process.env.ALLOWED_TABLES         = 'products,orders';

// Helper: create a signed test token
function makeToken(overrides = {}) {
  return jwt.sign({ userId: 'u1', username: 'tester', role: 'admin', ...overrides }, process.env.JWT_SECRET, { expiresIn: '1h' });
}

// ─── Health ───────────────────────────────────────────────────────────────────
describe('GET /health', () => {
  it('returns 200 when Snowflake is reachable', async () => {
    const res = await request(app).get('/health');
    expect(res.status).toBe(200);
    expect(res.body.status).toBe('ok');
  });
});

// ─── Auth ─────────────────────────────────────────────────────────────────────
describe('POST /auth/login', () => {
  it('returns 401 for unknown user', async () => {
    const res = await request(app).post('/auth/login').send({ username: 'nobody', password: 'x' });
    expect(res.status).toBe(401);
  });

  it('returns tokens for valid dummy user credentials', async () => {
    const res = await request(app)
      .post('/auth/login')
      .send({ username: 'manager@storeinsight.io', password: 'manager123' });
    expect(res.status).toBe(200);
    expect(res.body).toHaveProperty('accessToken');
    expect(res.body).toHaveProperty('refreshToken');
  });

  it('blocks registration endpoint', async () => {
    const res = await request(app)
      .post('/auth/register')
      .send({ username: 'new@storeinsight.io', password: 'test123', role: 'viewer' });
    expect(res.status).toBe(403);
    expect(res.body.code).toBe('REGISTRATION_DISABLED');
  });
});

// ─── Query ────────────────────────────────────────────────────────────────────
describe('POST /query/execute', () => {
  it('requires auth', async () => {
    const res = await request(app).post('/query/execute').send({ sql: 'SELECT 1' });
    expect(res.status).toBe(401);
  });

  it('executes a SELECT and returns rows', async () => {
    executeQuery.mockResolvedValueOnce([{ VAL: 1 }]);
    const res = await request(app)
      .post('/query/execute')
      .set('Authorization', `Bearer ${makeToken()}`)
      .send({ sql: 'SELECT 1 AS val' });
    expect(res.status).toBe(200);
    expect(res.body.rows).toHaveLength(1);
  });

  it('blocks non-SELECT for non-admin', async () => {
    const res = await request(app)
      .post('/query/execute')
      .set('Authorization', `Bearer ${makeToken({ role: 'viewer' })}`)
      .send({ sql: 'DROP TABLE foo' });
    expect(res.status).toBe(403);
  });
});

// ─── CRUD ─────────────────────────────────────────────────────────────────────
describe('CRUD /data/:table', () => {
  it('GET /data/products lists rows', async () => {
    executeQuery
      .mockResolvedValueOnce([{ ID: '1', NAME: 'Widget' }]) // data rows
      .mockResolvedValueOnce([{ TOTAL: 1 }]);               // count
    const res = await request(app)
      .get('/data/products')
      .set('Authorization', `Bearer ${makeToken()}`);
    expect(res.status).toBe(200);
    expect(res.body.data).toHaveLength(1);
  });

  it('GET /data/secrets blocks non-allowed table', async () => {
    const res = await request(app)
      .get('/data/secrets')
      .set('Authorization', `Bearer ${makeToken()}`);
    expect(res.status).toBe(403);
  });

  it('POST /data/products creates a record', async () => {
    executeQuery.mockResolvedValueOnce([]);
    const res = await request(app)
      .post('/data/products')
      .set('Authorization', `Bearer ${makeToken()}`)
      .send({ id: 'p1', name: 'Gadget', price: 9.99 });
    expect(res.status).toBe(201);
  });
});
