// src/middleware/auth.js
// Verifies the JWT on every protected route.

const jwt = require('jsonwebtoken');

const IS_DEVELOPMENT = (process.env.NODE_ENV || '').toLowerCase() === 'development';

function getAccessSecret() {
  if (process.env.JWT_SECRET) return process.env.JWT_SECRET;
  if (IS_DEVELOPMENT) return 'dev-jwt-secret-change-me';
  throw new Error('JWT_SECRET is required');
}

/**
 * requireAuth – attach decoded token payload to req.user
 * Usage: router.get('/protected', requireAuth, handler)
 */
function requireAuth(req, res, next) {
  const authHeader = req.headers.authorization;

  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return res.status(401).json({
      error: 'You are not signed in. Please log in and try again.',
      code: 'AUTH_HEADER_MISSING',
    });
  }

  const token = authHeader.split(' ')[1];

  try {
    const payload = jwt.verify(token, getAccessSecret());
    req.user = payload;   // { userId, username, role, iat, exp }
    next();
  } catch (err) {
    if (err.name === 'TokenExpiredError') {
      return res.status(401).json({
        error: 'Your session has expired. Please sign in again.',
        code: 'TOKEN_EXPIRED',
      });
    }
    return res.status(401).json({
      error: 'Your session is invalid. Please sign in again.',
      code: 'TOKEN_INVALID',
    });
  }
}

/**
 * requireRole – gate a route to specific roles.
 * Usage: router.delete('/table/:id', requireAuth, requireRole('admin'), handler)
 */
function requireRole(...roles) {
  return (req, res, next) => {
    if (!req.user || !roles.includes(req.user.role)) {
      return res.status(403).json({ error: 'Insufficient permissions' });
    }
    next();
  };
}

module.exports = { requireAuth, requireRole };
