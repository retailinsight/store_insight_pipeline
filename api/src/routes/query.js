// src/routes/query.js
const router = require('express').Router();
const { execute, stream } = require('../controllers/queryController');
const { requireAuth } = require('../middleware/auth');
const { validate, schemas } = require('../middleware/validate');

// All query routes require a valid JWT
router.use(requireAuth);

router.post('/execute', validate(schemas.query), execute);
router.post('/stream',  validate(schemas.query), stream);

module.exports = router;
