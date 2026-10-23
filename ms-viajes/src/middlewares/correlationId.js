const { randomUUID } = require('crypto');

module.exports = (req, res, next) => {
  const entrante = req.get('X-Correlation-Id');
  req.correlationId =
    entrante && entrante.trim() !== '' && entrante.length <= 100
      ? entrante.trim()
      : randomUUID();
  res.set('X-Correlation-Id', req.correlationId);
  next();
};