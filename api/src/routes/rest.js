const router = require('express').Router();
const crud = require('../controllers/crudController');
const { requireAuth, requireRole } = require('../middleware/auth');

function withTable(table, handler) {
  return (req, res, next) => {
    req.params = { ...req.params, table };
    return handler(req, res, next);
  };
}

router.get('/kpis', requireAuth, withTable('kpis', crud.list));
router.get('/successes', requireAuth, withTable('successes', crud.list));
router.get('/actions', requireAuth, withTable('actions', crud.list));
router.post('/actions/:id/reminder', requireAuth, requireRole('admin', 'editor'), crud.createActionReminder);
router.post('/actions/:id/complete', requireAuth, crud.completeAction);

module.exports = router;
