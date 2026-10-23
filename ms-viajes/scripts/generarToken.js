require('dotenv').config();
const jwt = require('jsonwebtoken');

const conductorId = process.argv[2] || '1';

const token = jwt.sign({}, process.env.JWT_SECRET, {
  algorithm: 'HS256',
  subject: String(conductorId),
  expiresIn: 3600,
});

console.log(token);