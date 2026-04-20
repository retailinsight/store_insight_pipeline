# Snowflake API — Express + React

A production-ready REST API that connects your React app to Snowflake with **JWT auth**, **CRUD operations**, **ad-hoc query execution**, and **SSE result streaming**.

---

## Project Structure

```
snowflake-api/
├── src/
│   ├── server.js                  # Express app entry point
│   ├── config/
│   │   └── snowflake.js           # Connection pool + helpers
│   ├── middleware/
│   │   ├── auth.js                # JWT verification
│   │   └── validate.js            # Joi request validation
│   ├── controllers/
│   │   ├── authController.js      # Login / register / refresh / logout
│   │   ├── queryController.js     # Execute SQL + SSE streaming
│   │   └── crudController.js      # Generic table CRUD
│   ├── data/
│   │   └── localData.json         # Local dev data source for GET /data/*
│   └── routes/
│       ├── auth.js
│       ├── query.js
│       └── data.js
├── react-client/
│   └── snowflakeClient.js         # Drop into your React app
├── tests/
│   └── api.test.js
├── .env.example
└── package.json
```

---

## Quick Start

### 1. Install

```bash
npm install
```

### 2. Configure Environment

```bash
cp .env.example .env
# Fill in your Snowflake credentials and JWT secrets
```

### 3. Create the Users Table in Snowflake

```sql
CREATE TABLE users (
  id          VARCHAR(36)  PRIMARY KEY,
  username    VARCHAR(128) UNIQUE NOT NULL,
  password    VARCHAR(256) NOT NULL,
  role        VARCHAR(20)  DEFAULT 'viewer',
  created_at  TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
);
```

### 4. Set Allowed Tables

In `.env`, list the Snowflake tables your React app may read/write:

```
ALLOWED_TABLES=products,orders,customers
```

### 5. Run

```bash
npm run dev     # development (nodemon)
npm start       # production
npm test        # run tests (no live DB required)
```

### Development Local Data Mode

When `NODE_ENV=development`, `GET /data/:table` and `GET /data/:table/:id` read from `src/data/kpiData.json` instead of Snowflake.

Authentication is also mocked in development:

- `POST /auth/login` returns JWTs without querying Snowflake users.
- `POST /auth/login` accepts an empty body in development (defaults to a mock user).
- `POST /auth/register` returns a mocked created response.
- Role defaults to `admin` and can be overridden with `MOCK_AUTH_ROLE=viewer|editor|admin`.

You can override this path with:

```
LOCAL_DATA_FILE=/absolute/path/to/your/data.json
```

JSON format is table-name keys mapped to row arrays:

```json
{
  "products": [
    { "id": "1", "name": "Sample Product", "price": 19.99 }
  ],
  "orders": []
}
```

---

## API Reference

### Health

| Method | Path      | Auth | Description          |
|--------|-----------|------|----------------------|
| GET    | `/health` | –    | Snowflake ping + uptime |

---

### Auth

| Method | Path              | Auth | Description           |
|--------|-------------------|------|-----------------------|
| POST   | `/auth/register`  | –    | Create a new user     |
| POST   | `/auth/login`     | –    | Login → access + refresh tokens |
| POST   | `/auth/refresh`   | –    | Rotate tokens         |
| POST   | `/auth/logout`    | –    | Invalidate refresh token |

**Login request:**
```json
{ "username": "alice", "password": "secret" }
```

**Login response:**
```json
{
  "accessToken": "eyJ...",
  "refreshToken": "eyJ...",
  "user": { "id": "...", "username": "alice", "role": "admin" }
}
```

---

### Query Execution

All query routes require `Authorization: Bearer <accessToken>`.

| Method | Path              | Description                     |
|--------|-------------------|---------------------------------|
| POST   | `/query/execute`  | Run SQL → returns all rows      |
| POST   | `/query/stream`   | Run SQL → SSE stream of rows    |

**Request body:**
```json
{ "sql": "SELECT * FROM products WHERE price > ?", "binds": [10] }
```

**`/query/stream` — Server-Sent Events:**
Each row arrives as an SSE `data:` event, followed by a final `done` event:
```
data: {"ID":"1","NAME":"Widget","PRICE":19.99}
data: {"ID":"2","NAME":"Gadget","PRICE":29.99}
event: done
data: {"rowCount":2}
```

> Non-admin users may only run `SELECT / WITH / SHOW / DESCRIBE` statements.

---

### CRUD

All data routes require `Authorization: Bearer <accessToken>`.

| Method | Path                | Roles           | Description          |
|--------|---------------------|-----------------|----------------------|
| GET    | `/data/:table`      | any             | List rows            |
| GET    | `/data/:table/:id`  | any             | Get single row       |
| POST   | `/data/:table`      | editor, admin   | Create row           |
| PUT    | `/data/:table/:id`  | editor, admin   | Update row           |
| DELETE | `/data/:table/:id`  | admin only      | Delete row           |

**List with pagination + filtering:**
```
GET /data/products?limit=20&offset=40&filter[category]=electronics
```

### REST Resources

All routes require `Authorization: Bearer <accessToken>`.

| Method | Path                    | Roles          | Description                     |
|--------|-------------------------|----------------|---------------------------------|
| GET    | `/kpis`                 | any            | List KPI records                |
| GET    | `/successes`            | any            | List success records            |
| GET    | `/actions`              | any            | List action records             |
| POST   | `/actions/:id/reminder` | editor, admin  | Create reminder for an action   |

---

## React Integration

Copy `react-client/snowflakeClient.js` into your React project, then:

```jsx
import { auth, query, data } from './api/snowflakeClient';

// Login
const user = await auth.login('alice', 'secret');

// Run a query
const { rows } = await query.execute('SELECT * FROM products LIMIT 10');

// Stream a large result
const cancel = query.stream(
  'SELECT * FROM orders',
  [],
  {
    onRow:  (row)  => setRows(r => [...r, row]),
    onDone: (meta) => console.log(`Streamed ${meta.rowCount} rows`),
  }
);
// cancel() to abort early

// CRUD
const { data: products } = await data.list('products', { limit: 50 });
await data.create('products', { id: uuid(), name: 'New Item', price: 9.99 });
await data.update('products', '123', { price: 14.99 });
await data.remove('products', '123');

// Logout
await auth.logout();
```

---

## Roles

| Role     | Read | Write | Delete | Run any SQL |
|----------|------|-------|--------|-------------|
| `viewer` | ✅   | ❌    | ❌     | ❌ (SELECT only) |
| `editor` | ✅   | ✅    | ❌     | ❌ (SELECT only) |
| `admin`  | ✅   | ✅    | ✅     | ✅ |

---

## Security Notes

- **Parameterised queries only** — no string interpolation of user input.
- **Table allowlist** — set `ALLOWED_TABLES` in `.env`; any unlisted table returns 403.
- **Rate limiting** — 100 req / 15 min per IP by default (configure via env vars).
- **Helmet** — sets secure HTTP headers automatically.
- **Refresh tokens** are stored in memory — swap the `refreshTokens` Set in `authController.js` for Redis or a DB table in production.
