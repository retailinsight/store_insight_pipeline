// src/controllers/authController.js
// Handles login, token refresh, and logout.
//
// NOTE: This example stores a "users" table in Snowflake.
// Schema assumed:
//   CREATE TABLE users (
//     id          VARCHAR PRIMARY KEY,
//     username    VARCHAR UNIQUE NOT NULL,
//     password    VARCHAR NOT NULL,   -- bcrypt hash
//     role        VARCHAR DEFAULT 'viewer',
//     created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
//   );

const jwt     = require('jsonwebtoken');
const storesData = require('../data/stores.json');
const dummyUsersData = require('../data/dummyUsers.json');

const IS_DEVELOPMENT = (process.env.NODE_ENV || '').toLowerCase() === 'development';
const AUTH_SOURCE = (process.env.AUTH_SOURCE || 'dummy').toLowerCase();

const DUMMY_USERS = Array.isArray(dummyUsersData?.users) ? dummyUsersData.users : [];

// In-memory refresh token store (swap for Redis / DB in production)
const refreshTokens = new Set();

function getAccessSecret() {
  if (process.env.JWT_SECRET) return process.env.JWT_SECRET;
  if (IS_DEVELOPMENT) return 'dev-jwt-secret-change-me';
  throw new Error('JWT_SECRET is required');
}

function getRefreshSecret() {
  if (process.env.REFRESH_TOKEN_SECRET) return process.env.REFRESH_TOKEN_SECRET;
  if (IS_DEVELOPMENT) return 'dev-refresh-secret-change-me';
  throw new Error('REFRESH_TOKEN_SECRET is required');
}

function signAccess(payload) {
  return jwt.sign(payload, getAccessSecret(), {
    expiresIn: process.env.JWT_EXPIRES_IN || '8h',
  });
}

function signRefresh(payload) {
  return jwt.sign(payload, getRefreshSecret(), {
    expiresIn: process.env.REFRESH_TOKEN_EXPIRES_IN || '7d',
  });
}

function getStoreContextForUser(storeId) {
  const stores = Array.isArray(storesData?.stores) ? storesData.stores : [];

  if (storeId === 'all') {
    return { stores };
  }

  const numericStoreId = Number(storeId);
  const matchedStore = stores.find((s) => Number(s.id) === numericStoreId) || null;
  return { stores: matchedStore ? [matchedStore] : [] };
}

function getAuthorizationRole(user) {
  if (Number(user.roleId) === 1) return 'admin';
  if (Number(user.roleId) === 2) return 'editor';

  const normalizedRole = String(user.role || '').toLowerCase();
  if (['admin', 'editor', 'viewer'].includes(normalizedRole)) return normalizedRole;
  return 'viewer';
}

function getRoleName(user) {
  return user.roleName || user.role || 'viewer';
}

function findDummyUserByUsername(username) {
  const normalizedUsername = String(username || '').trim().toLowerCase();
  return DUMMY_USERS.find((u) => String(u.username || '').toLowerCase() === normalizedUsername) || null;
}

// ─── POST /auth/login ─────────────────────────────────────────────────────────
async function login(req, res) {
  try {
    const { username, password } = req.body;

    if (!username || !password) {
      return res.status(400).json({
        error: 'Please provide both username and password.',
        code: 'MISSING_CREDENTIALS',
      });
    }

    if (AUTH_SOURCE !== 'dummy') {
      return res.status(503).json({
        error: 'Authentication provider is not configured.',
        code: 'AUTH_PROVIDER_UNAVAILABLE',
      });
    }

    const dummyUser = findDummyUserByUsername(username);

    if (dummyUser) {
      if (password !== dummyUser.password) {
        return res.status(401).json({
          error: 'Incorrect username or password. Please try again.',
          code: 'INVALID_CREDENTIALS',
        });
      }

      const tokenPayload = {
        userId: dummyUser.id,
        username: dummyUser.username,
        role: getAuthorizationRole(dummyUser),
        roleId: dummyUser.roleId,
        roleName: getRoleName(dummyUser),
        storeId: dummyUser.storeId,
      };
      const accessToken = signAccess(tokenPayload);
      const refreshToken = signRefresh(tokenPayload);

      refreshTokens.add(refreshToken);

      const storeContext = getStoreContextForUser(dummyUser.storeId);

      return res.json({
        accessToken,
        refreshToken,
        user: {
          id: dummyUser.id,
          username: dummyUser.username,
          role: getAuthorizationRole(dummyUser),
          roleId: dummyUser.roleId,
          roleName: getRoleName(dummyUser),
          storeId: dummyUser.storeId,
          ...storeContext,
        },
      });
    }

    return res.status(401).json({
      error: 'Incorrect username or password. Please try again.',
      code: 'INVALID_CREDENTIALS',
    });
  } catch (err) {
    console.error('[login]', err);
    return res.status(500).json({
      error: 'We could not sign you in right now. Please try again shortly.',
      code: 'AUTHENTICATION_FAILED',
    });
  }
}

// ─── POST /auth/refresh ───────────────────────────────────────────────────────
async function refresh(req, res) {
  const { refreshToken } = req.body;

  if (!refreshToken || !refreshTokens.has(refreshToken)) {
    return res.status(401).json({ error: 'Invalid refresh token' });
  }

  try {
    const payload = jwt.verify(refreshToken, getRefreshSecret());
    const { userId, username, role } = payload;

    if (AUTH_SOURCE === 'dummy') {
      const activeUser = findDummyUserByUsername(username);
      if (!activeUser || activeUser.id !== userId) {
        refreshTokens.delete(refreshToken);
        return res.status(401).json({ error: 'Refresh token expired or invalid' });
      }
    }

    const newAccess  = signAccess({ userId, username, role });
    const newRefresh = signRefresh({ userId, username, role });

    refreshTokens.delete(refreshToken);
    refreshTokens.add(newRefresh);

    return res.json({ accessToken: newAccess, refreshToken: newRefresh });
  } catch {
    return res.status(401).json({ error: 'Refresh token expired or invalid' });
  }
}

// ─── POST /auth/logout ────────────────────────────────────────────────────────
function logout(req, res) {
  const { refreshToken } = req.body;
  if (refreshToken) refreshTokens.delete(refreshToken);
  return res.json({ message: 'Logged out successfully' });
}

// ─── POST /auth/register (optional – remove if not needed) ───────────────────
async function register(req, res) {
  return res.status(403).json({
    error: 'Registration is disabled in this environment.',
    code: 'REGISTRATION_DISABLED',
  });
}

module.exports = { login, refresh, logout, register };
