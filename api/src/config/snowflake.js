// src/config/snowflake.js
// Manages the Snowflake connection pool and exposes helper utilities.

const snowflake = require('snowflake-sdk');

snowflake.configure({ logLevel: process.env.NODE_ENV === 'development' ? 'WARN' : 'ERROR' });

// ─── Connection Pool ──────────────────────────────────────────────────────────

const pool = snowflake.createPool(
  {
    account:   process.env.SNOWFLAKE_ACCOUNT,
    username:  process.env.SNOWFLAKE_USERNAME,
    password:  process.env.SNOWFLAKE_PASSWORD,
    database:  process.env.SNOWFLAKE_DATABASE,
    schema:    process.env.SNOWFLAKE_SCHEMA   || 'PUBLIC',
    warehouse: process.env.SNOWFLAKE_WAREHOUSE,
    role:      process.env.SNOWFLAKE_ROLE     || undefined,
  },
  {
    max: 10,   // max connections in pool
    min: 1,    // keep at least 1 alive
  }
);

// ─── Helpers ─────────────────────────────────────────────────────────────────

/**
 * Execute a SQL statement and return all rows as an array.
 * @param {string} sqlText  - Parameterised SQL (use ? placeholders)
 * @param {Array}  binds    - Bind values for placeholders
 * @returns {Promise<Array>}
 */
async function executeQuery(sqlText, binds = []) {
  return new Promise((resolve, reject) => {
    pool.use(async (clientConnection) => {
      clientConnection.execute({
        sqlText,
        binds,
        complete: (err, _stmt, rows) => {
          if (err) return reject(err);
          resolve(rows);
        },
      });
    });
  });
}

/**
 * Execute a SQL statement and stream rows back via an async generator.
 * Ideal for large result sets where you don't want to buffer everything.
 * @param {string} sqlText
 * @param {Array}  binds
 * @yields {Object} row
 */
async function* streamQuery(sqlText, binds = []) {
  const stream = await new Promise((resolve, reject) => {
    pool.use(async (clientConnection) => {
      const stmt = clientConnection.execute({
        sqlText,
        binds,
        streamResult: true,
        complete: (err, statement) => {
          if (err) return reject(err);
          resolve(statement.streamRows());
        },
      });
    });
  });

  for await (const row of stream) {
    yield row;
  }
}

/**
 * Lightweight health-check – runs a trivial query and resolves true/false.
 */
async function healthCheck() {
  try {
    await executeQuery('SELECT 1 AS ok');
    return true;
  } catch {
    return false;
  }
}

module.exports = { pool, executeQuery, streamQuery, healthCheck };
