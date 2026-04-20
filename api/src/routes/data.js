// src/routes/data.js
const router = require('express').Router();
const crud   = require('../controllers/crudController');
const { requireAuth, requireRole } = require('../middleware/auth');

// All data routes require authentication
router.use(requireAuth);

// Read – any authenticated user
router.get('/:table',     crud.list);
router.get('/:table/:id', crud.getById);

// Write – editor or admin only
router.post('/:table',        requireRole('admin', 'editor'), crud.create);
router.put('/:table/:id',     requireRole('admin', 'editor'), crud.update);
router.delete('/:table/:id',  requireRole('admin'),           crud.remove);

module.exports = router;
