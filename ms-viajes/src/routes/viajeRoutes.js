const { Router } = require('express');
const asyncHandler = require('../utils/asyncHandler');
const autenticar = require('../middlewares/auth');
const validarServiceKey = require('../middlewares/serviceKey');
const c = require('../controllers/viajeController');

const router = Router();

// Solo entre servicios (Reservas -> Viajes): X-Service-Key, sin JWT.
// Va ANTES de router.use(autenticar) a propósito.
router.put('/:viajeId/ocupacion', validarServiceKey, asyncHandler(c.ocupacion));

// Todo lo demás exige JWT
router.use(autenticar);

router.post('/', asyncHandler(c.crear));
router.get('/', asyncHandler(c.buscar));
router.get('/:viajeId', asyncHandler(c.consultar));
router.patch('/:viajeId', asyncHandler(c.modificar));
router.delete('/:viajeId', asyncHandler(c.cancelar));
router.post('/:viajeId/finalizar', asyncHandler(c.finalizar));

module.exports = router;