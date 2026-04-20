// src/controllers/queryController.js
// Handles ad-hoc SQL execution and SSE streaming for large result sets.

const { executeQuery, streamQuery } = require('../config/snowflake');

// Allowlist of SQL operations permitted for non-admin users.
const READ_ONLY_PATTERN = /^\s*(SELECT|WITH|SHOW|DESCRIBE|DESC)\b/i;

// ─── POST /query/execute ──────────────────────────────────────────────────────
// Runs a SQL statement and returns all rows (suitable for small-medium results).
async function execute(req, res) {
  try {
    const { sql, binds = [] } = req.body;

    // Non-admins may only run read queries
    if (req.user.role !== 'admin' && !READ_ONLY_PATTERN.test(sql)) {
      return res.status(403).json({ error: 'Only SELECT statements are permitted for your role' });
    }

    const startMs = Date.now();
    const rows    = await executeQuery(sql, binds);

    return res.json({
      rows,
      meta: {
        rowCount:  rows.length,
        elapsedMs: Date.now() - startMs,
      },
    });
  } catch (err) {
    console.error('[execute]', err);
    return res.status(500).json({ error: err.message || 'Query failed' });
  }
}

// ─── POST /query/stream ───────────────────────────────────────────────────────
// Streams rows via Server-Sent Events (SSE) for large result sets.
// React client should use EventSource or a fetch() with ReadableStream.
async function stream(req, res) {
  try {
    const { sql, binds = [] } = req.body;

    if (req.user.role !== 'admin' && !READ_ONLY_PATTERN.test(sql)) {
      return res.status(403).json({ error: 'Only SELECT statements are permitted for your role' });
    }

    // Set up SSE headers
    res.setHeader('Content-Type',  'text/event-stream');
    res.setHeader('Cache-Control', 'no-cache');
    res.setHeader('Connection',    'keep-alive');
    res.setHeader('X-Accel-Buffering', 'no'); // disable Nginx buffering

    let rowCount = 0;

    for await (const row of streamQuery(sql, binds)) {
      rowCount++;
      res.write(`data: ${JSON.stringify(row)}\n\n`);
    }

    // Send a final "done" event with summary
    res.write(`event: done\ndata: ${JSON.stringify({ rowCount })}\n\n`);
    res.end();
  } catch (err) {
    console.error('[stream]', err);
    res.write(`event: error\ndata: ${JSON.stringify({ error: err.message })}\n\n`);
    res.end();
  }
}

module.exports = { execute, stream };
