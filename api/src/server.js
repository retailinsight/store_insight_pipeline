// src/server.js
require('dotenv').config();

const express    = require('express');
const cors       = require('cors');
const helmet     = require('helmet');
const morgan     = require('morgan');
const rateLimit  = require('express-rate-limit');

const authRoutes  = require('./routes/auth');
const queryRoutes = require('./routes/query');
const dataRoutes  = require('./routes/data');
const restRoutes  = require('./routes/rest');
const { healthCheck } = require('./config/snowflake');

const app  = express();
const PORT = process.env.PORT || 3001;

// ─── Security Headers ─────────────────────────────────────────────────────────
app.use(helmet());

// ─── CORS ─────────────────────────────────────────────────────────────────────
const allowedOrigins = (process.env.ALLOWED_ORIGINS || 'http://localhost:3000')
  .split(',')
  .map((origin) => origin.trim())
  .filter(Boolean);
app.use(cors({
  origin: (origin, cb) => {
    // Allow requests with no origin (curl, Postman, server-to-server)
    if (!origin || allowedOrigins.includes(origin)) return cb(null, true);
    cb(new Error(`CORS: origin "${origin}" not allowed`));
  },
  credentials: true,
}));

// ─── Rate Limiting ────────────────────────────────────────────────────────────
const limiter = rateLimit({
  windowMs: parseInt(process.env.RATE_LIMIT_WINDOW_MS || '900000', 10),
  max:      parseInt(process.env.RATE_LIMIT_MAX       || '100',    10),
  standardHeaders: true,
  legacyHeaders:   false,
  message: { error: 'Too many requests – please try again later' },
});
app.use(limiter);

// ─── Body Parsing ─────────────────────────────────────────────────────────────
app.use(express.json({ limit: '1mb' }));
app.use(express.urlencoded({ extended: false }));

// ─── Logging ──────────────────────────────────────────────────────────────────
if (process.env.NODE_ENV !== 'test') {
  app.use(morgan(process.env.NODE_ENV === 'production' ? 'combined' : 'dev'));
}

// ─── Health Check ─────────────────────────────────────────────────────────────
app.get('/health', async (_req, res) => {
  const sfOk = await healthCheck();
  const status = sfOk ? 200 : 503;
  return res.status(status).json({
    status:    sfOk ? 'ok' : 'degraded',
    snowflake: sfOk ? 'connected' : 'unreachable',
    uptime:    process.uptime(),
    timestamp: new Date().toISOString(),
  });
});

// ─── Routes ───────────────────────────────────────────────────────────────────
app.use('/auth',  authRoutes);
app.use('/query', queryRoutes);
app.use('/data',  dataRoutes);
app.use('/',      restRoutes);

// ─── 404 ──────────────────────────────────────────────────────────────────────
app.use((_req, res) => res.status(404).json({ error: 'Route not found' }));

// ─── Global Error Handler ─────────────────────────────────────────────────────
// eslint-disable-next-line no-unused-vars
app.use((err, _req, res, _next) => {
  console.error(err);
  res.status(err.status || 500).json({ error: err.message || 'Internal server error' });
});

// ─── Start ────────────────────────────────────────────────────────────────────
if (require.main === module) {
  app.listen(PORT, () => {
    console.log(`✅  Snowflake API listening on http://localhost:${PORT}`);
    console.log(`    Environment : ${process.env.NODE_ENV || 'development'}`);
    console.log(`    Snowflake   : ${process.env.SNOWFLAKE_ACCOUNT}`);
  });
}

module.exports = app; // export for tests
