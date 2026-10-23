class AppError extends Error {
  constructor(status, error, message, detalles) {
    super(message);
    this.status = status;
    this.error = error;
    this.detalles = detalles;
  }
}

module.exports = { AppError };