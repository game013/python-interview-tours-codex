# Tour Scheduling API

Servicio HTTP en FastAPI para agendar visitas a propiedades que cubre creación, consulta, listado y cancelación de tours con reglas de negocio clave (validaciones, idempotencia, rate limiting y manejo de solapes) sobre almacenamiento en memoria thread-safe.

## Requisitos previos

- Python 3.10+
- (Opcional) Entorno virtual recomendado: `python -m venv .venv && source .venv/bin/activate`
- Instalar dependencias: `pip install -e .[dev]`

## Ejecución

```bash
uvicorn app.main:app --reload
```

El servicio expone los endpoints bajo `/v1/tours` y cuenta con documentación interactiva en `/docs`.

## Pruebas

```bash
pytest
```

Las pruebas cubren:
- Prevención de solape en la misma propiedad.
- Idempotencia vía `Idempotency-Key` devolviendo el mismo tour (201/200).
- Límite diario de creación por cliente.

## Diseño y decisiones

- **Capas separadas:** controladores (FastAPI), servicio (`TourService`) y almacenamiento (`InMemoryTourStorage`) para mantener responsabilidades claras.
- **Almacenamiento en memoria thread-safe:** uso de `RLock` para agrupar operaciones críticas (idempotencia, rate limit y validación de solapes) evitando condiciones de carrera.
- **Idempotencia:** se guarda el `fingerprint` de la solicitud junto al tour creado por 24h; solicitudes repetidas devuelven el mismo tour y no consumen el rate limit.
- **Rate limiting diario:** contador por `customer_id` y fecha UTC; sólo incrementa en creaciones efectivas.
- **Validaciones:** fechas en UTC, `start_at < end_at`, paginación acotada, ordenación por `start_at` (asc/desc).
- **Logging:** eventos `INFO` para creación/cancelación y `WARNING` para errores funcionales.

## Escalabilidad y siguientes pasos

- Sustituir el storage en memoria por una base de datos (p.ej. Postgres) con índices por `property_id` y `start_at` para búsquedas y solapes eficientes.
- Usar locking a nivel de registro (p.ej. `SELECT ... FOR UPDATE`) o bloqueos optimistas para minimizar contención.
- Externalizar idempotencia y rate limiting a un store compartido (Redis) con expiraciones nativas.
- Agregar cache por propiedad/fecha para listados de alto volumen y paginación basada en cursores.
- Extender métricas y tracing para observabilidad.

## Preguntas y comentarios para el entrevistador

1. ¿Los tours cancelados deberían seguir bloqueando solapes futuros en la misma ventana horaria?
2. ¿Cómo esperan que se maneje la expiración de claves de idempotencia en un entorno distribuido?
3. ¿El rate limit diario se basa en la fecha de creación o en la fecha del tour? ¿Debe resetearse a medianoche del cliente o UTC?
4. ¿Es necesario auditar cambios de estado (BOOKED → CANCELLED) o basta con el estado actual?
5. ¿Existe alguna policy de reprogramación (modificar `start_at`/`end_at`) que debamos soportar en el futuro?

## Lógica de implementación

1. **Entrada y validaciones**: Pydantic parsea la carga útil, se normalizan las fechas a UTC y se valida `start_at < end_at`.
2. **Servicio**: Coordina idempotencia, rate limiting y validación de solapes dentro de una sección crítica para evitar race conditions.
3. **Almacenamiento**: Guarda tours, contadores y claves de idempotencia (con expiración en 24h) usando estructuras en memoria protegidas por `RLock`.
4. **Respuesta HTTP**: Los handlers convierten el dominio a esquemas de respuesta, controlan los códigos 201/200 y devuelven errores estandarizados.
5. **Cancelación**: Marca el tour como `CANCELLED`, persiste el cambio y registra en logs; la operación es idempotente.
