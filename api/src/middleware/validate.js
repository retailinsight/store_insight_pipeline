// src/middleware/validate.js
// Generic Joi schema validator for request body / query / params.

const Joi = require('joi');

/**
 * validate(schema, target?)
 *   schema – Joi schema object
 *   target – 'body' | 'query' | 'params'  (default: 'body')
 */
function validate(schema, target = 'body') {
  return (req, res, next) => {
    const { error, value } = schema.validate(req[target], { abortEarly: false, stripUnknown: true });

    if (error) {
      const details = error.details.map((d) => d.message);
      return res.status(400).json({ error: 'Validation failed', details });
    }

    req[target] = value; // replace with sanitised value
    next();
  };
}

// ─── Shared Schemas ──────────────────────────────────────────────────────────

const schemas = {
  login: Joi.object({
    username: Joi.string().min(1).max(128).required(),
    password: Joi.string().min(1).required(),
  }),

  query: Joi.object({
    sql:   Joi.string().min(1).max(10_000).required(),
    binds: Joi.array().items(Joi.alternatives().try(Joi.string(), Joi.number(), Joi.boolean(), Joi.allow(null))).default([]),
  }),

  pagination: Joi.object({
    limit:  Joi.number().integer().min(1).max(1000).default(100),
    offset: Joi.number().integer().min(0).default(0),
  }),
};

module.exports = { validate, schemas };
