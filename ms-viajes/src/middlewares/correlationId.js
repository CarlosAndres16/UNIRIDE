const { randomUUID } = require('crypto');

module.exports = (req, res, next) => {
  const entrante = req.get('X-Correlation-Id');
  req.correlationId =
    typeof entrante === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(entrante.trim())
      ? entrante.trim()
      : randomUUID();
  res.set('X-Correlation-Id', req.correlationId);
  next();
};
