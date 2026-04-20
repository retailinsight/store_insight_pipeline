// src/routes/auth.js
const router = require('express').Router();
const { login, refresh, logout, register } = require('../controllers/authController');
const { validate, schemas } = require('../middleware/validate');
const Joi = require('joi');

const registerSchema = schemas.login.keys({
  role: Joi.string().valid('admin', 'editor', 'viewer').default('viewer'),
});

router.post('/login',    validate(schemas.login), login);
router.post('/register', validate(registerSchema), register);
router.post('/refresh',  refresh);
router.post('/logout',   logout);

module.exports = router;
