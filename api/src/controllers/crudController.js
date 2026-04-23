// src/controllers/crudController.js
// Generic CRUD operations against any Snowflake table.
// All table names are validated against an allowlist to prevent injection.

const fs = require('fs/promises');
const path = require('path');
const { v4: uuidv4 } = require('uuid');
const { executeQuery } = require('../config/snowflake');

const IS_DEVELOPMENT = (process.env.NODE_ENV || '').toLowerCase() === 'development';
const LOCAL_DATA_FILE = process.env.LOCAL_DATA_FILE || path.join(__dirname, '..', 'data', 'kpiData.json');

async function readLocalData() {
  const file = await fs.readFile(LOCAL_DATA_FILE, 'utf8');
  return JSON.parse(file);
}

function getRowsForTable(data, table) {
  const tableVariants = [table, table.toLowerCase(), table.toUpperCase()];
  const key = tableVariants.find((name) => Array.isArray(data?.[name]));
  return key ? data[key] : [];
}

function getValueCaseInsensitive(obj, key) {
  const requested = String(key).toLowerCase();
  const matchedKey = Object.keys(obj || {}).find((k) => k.toLowerCase() === requested);
  return matchedKey ? obj[matchedKey] : undefined;
}

function applyLocalFilters(rows, filter = {}) {
  const filterEntries = Object.entries(filter || {});
  if (!filterEntries.length) return rows;

  return rows.filter((row) => {
    return filterEntries.every(([column, value]) => {
      const rowValue = getValueCaseInsensitive(row, column);
      return String(rowValue) === String(value);
    });
  });
}

// ─── Allowlist ─────────────────────────────────────────────────────────────
// Add every table name your React app is allowed to access directly.
function getAllowedTables() {
  return new Set(
    (process.env.ALLOWED_TABLES || '').split(',').map((t) => t.trim().toUpperCase()).filter(Boolean)
  );
}

function assertTableAllowed(table) {
  const allowedTables = getAllowedTables();
  if (!allowedTables.has(table.toUpperCase())) {
    const err = new Error(`Table "${table}" is not in the allowed list`);
    err.status = 403;
    throw err;
  }
}

// ─── GET /data/:table ─────────────────────────────────────────────────────────
async function list(req, res) {
  try {
    const table = req.params.table;
    assertTableAllowed(table);

    const parsedLimit = parseInt(req.query.limit || '100', 10);
    const limit  = Math.min(Number.isNaN(parsedLimit) ? 100 : parsedLimit, 1000);
    const parsedOffset = parseInt(req.query.offset || '0', 10);
    const offset = Number.isNaN(parsedOffset) ? 0 : parsedOffset;

    if (IS_DEVELOPMENT) {
      const data = await readLocalData();
      const tableRows = getRowsForTable(data, table);
      const filteredRows = applyLocalFilters(tableRows, req.query.filter);
      const pagedRows = filteredRows.slice(offset, offset + limit);

      res.setHeader('X-Total-Count', filteredRows.length);
      return res.json({ data: pagedRows, meta: { limit, offset, total: filteredRows.length } });
    }

    // Optional simple filter: ?filter[column]=value
    const filterEntries = Object.entries(req.query.filter || {});
    const whereClauses  = filterEntries.map(([col]) => `${col} = ?`);
    const binds         = filterEntries.map(([, v]) => v);

    const where = whereClauses.length ? `WHERE ${whereClauses.join(' AND ')}` : '';
    const sql   = `SELECT * FROM ${table} ${where} LIMIT ? OFFSET ?`;

    const rows = await executeQuery(sql, [...binds, limit, offset]);

    // Get total count for pagination headers
    const countSql  = `SELECT COUNT(*) AS total FROM ${table} ${where}`;
    const countRows = await executeQuery(countSql, binds);
    const total     = countRows[0]?.TOTAL ?? 0;

    res.setHeader('X-Total-Count', total);
    return res.json({ data: rows, meta: { limit, offset, total } });
  } catch (err) {
    return res.status(err.status || 500).json({ error: err.message });
  }
}

// ─── GET /data/:table/:id ─────────────────────────────────────────────────────
async function getById(req, res) {
  try {
    const { table, id } = req.params;
    assertTableAllowed(table);

    if (IS_DEVELOPMENT) {
      const data = await readLocalData();
      const tableRows = getRowsForTable(data, table);
      const row = tableRows.find((record) => String(getValueCaseInsensitive(record, 'id')) === String(id));

      if (!row) return res.status(404).json({ error: 'Record not found' });
      return res.json({ data: row });
    }

    const rows = await executeQuery(`SELECT * FROM ${table} WHERE id = ? LIMIT 1`, [id]);

    if (!rows.length) return res.status(404).json({ error: 'Record not found' });
    return res.json({ data: rows[0] });
  } catch (err) {
    return res.status(err.status || 500).json({ error: err.message });
  }
}

// ─── POST /data/:table ────────────────────────────────────────────────────────
async function create(req, res) {
  try {
    const { table } = req.params;
    assertTableAllowed(table);

    const body = req.body;
    if (!body || !Object.keys(body).length) {
      return res.status(400).json({ error: 'Request body is empty' });
    }

    const columns     = Object.keys(body);
    const values      = Object.values(body);
    const placeholders = columns.map(() => '?').join(', ');

    await executeQuery(
      `INSERT INTO ${table} (${columns.join(', ')}) VALUES (${placeholders})`,
      values
    );

    return res.status(201).json({ message: 'Record created' });
  } catch (err) {
    return res.status(err.status || 500).json({ error: err.message });
  }
}

// ─── PUT /data/:table/:id ─────────────────────────────────────────────────────
async function update(req, res) {
  try {
    const { table, id } = req.params;
    assertTableAllowed(table);

    const body = req.body;
    if (!body || !Object.keys(body).length) {
      return res.status(400).json({ error: 'Request body is empty' });
    }

    const setClauses = Object.keys(body).map((col) => `${col} = ?`).join(', ');
    const values     = [...Object.values(body), id];

    const result = await executeQuery(
      `UPDATE ${table} SET ${setClauses} WHERE id = ?`,
      values
    );

    return res.json({ message: 'Record updated' });
  } catch (err) {
    return res.status(err.status || 500).json({ error: err.message });
  }
}

// ─── DELETE /data/:table/:id ──────────────────────────────────────────────────
async function remove(req, res) {
  try {
    const { table, id } = req.params;
    assertTableAllowed(table);

    await executeQuery(`DELETE FROM ${table} WHERE id = ?`, [id]);

    return res.json({ message: 'Record deleted' });
  } catch (err) {
    return res.status(err.status || 500).json({ error: err.message });
  }
}

// ─── POST /actions/:id/reminder ──────────────────────────────────────────────
async function createActionReminder(req, res) {
  try {
    const { id } = req.params;
    const { message = 'Reminder', remindAt = null } = req.body || {};

    if (IS_DEVELOPMENT) {
      const data = await readLocalData();
      const actions = getRowsForTable(data, 'actions');
      const action = actions.find((record) => String(getValueCaseInsensitive(record, 'id')) === String(id));

      if (!action) return res.status(404).json({ error: 'Action not found' });

      const reminder = {
        id: uuidv4(),
        message,
        remindAt,
        createdAt: new Date().toISOString(),
      };

      if (!Array.isArray(action.reminders)) action.reminders = [];
      action.reminders.push(reminder);

      await fs.writeFile(LOCAL_DATA_FILE, JSON.stringify(data, null, 2));

      return res.status(201).json({ message: 'Reminder created', data: reminder });
    }

    await executeQuery(
      'INSERT INTO action_reminders (id, action_id, message, remind_at) VALUES (?, ?, ?, ?)',
      [uuidv4(), id, message, remindAt]
    );

    return res.status(201).json({ message: 'Reminder created' });
  } catch (err) {
    return res.status(err.status || 500).json({ error: err.message });
  }
}

// ─── POST /actions/:id/complete ──────────────────────────────────────
async function completeAction(req, res) {
  try {
    const { id } = req.params;
    const { opinion, feedback = '' } = req.body || {};
    const userId = req.user?.userId;

    // Validate opinion
    if (!opinion || !['positive', 'negative'].includes(opinion)) {
      return res.status(400).json({ error: 'Opinion must be "positive" or "negative"' });
    }

    if (IS_DEVELOPMENT) {
      const data = await readLocalData();
      const actions = getRowsForTable(data, 'actions');
      const action = actions.find((record) => String(getValueCaseInsensitive(record, 'id')) === String(id));

      if (!action) return res.status(404).json({ error: 'Action not found' });

      const completion = {
        id: uuidv4(),
        actionId: id,
        userId,
        opinion,
        feedback,
        completedAt: new Date().toISOString(),
      };

      if (!Array.isArray(action.completions)) action.completions = [];
      action.completions.push(completion);

      // Mark action as completed
      action.status = 'completed';
      action.completedAt = new Date().toISOString();

      await fs.writeFile(LOCAL_DATA_FILE, JSON.stringify(data, null, 2));

      return res.status(201).json({ message: 'Action completed', data: completion });
    }

    // Store completion with feedback
    const completionId = uuidv4();
    await executeQuery(
      'INSERT INTO action_completions (id, action_id, user_id, opinion, feedback, completed_at) VALUES (?, ?, ?, ?, ?, ?)',
      [completionId, id, userId, opinion, feedback, new Date().toISOString()]
    );

    // Update action status
    await executeQuery(
      'UPDATE actions SET status = ?, completed_at = ? WHERE id = ?',
      ['completed', new Date().toISOString(), id]
    );

    return res.status(201).json({ message: 'Action completed', data: { id: completionId, opinion, feedback } });
  } catch (err) {
    return res.status(err.status || 500).json({ error: err.message });
  }
}

module.exports = { list, getById, create, update, remove, createActionReminder, completeAction };
