# Orchestrator

Implementación del módulo orquestador del proyecto ["Sistema de Votación Electrónica Legislativa"](https://drive.google.com/drive/u/1/folders/1XNMrFrMzC7NgfJXPKUcg4koS6QqJEelR).

## Tech Stack

| Capa | Tecnología |
| --- | --- |
| Lenguaje | Python |
| Framework | FastAPI |
| Servidor | Uvicorn |
| Validación | Pydantic |
| DB | PostgreSQL |
| ORM | SQLAlchemy |
| DB Driver | asyncpg |
| Migraciones | Alembic |

## Requisitos previos

- [uv](https://docs.astral.sh/uv/) - Gestor de paquetes y proyectos de Python
- Python 3.14+
- [Docker](https://docs.docker.com/engine) y [Docker Compose](https://docs.docker.com/compose)

## Ejecución local

### 1. Clonar e instalar dependencias

```bash
git clone https://github.com/Tadedp/legislative-voting.git
cd legislative-voting\orchestrator
uv sync
```

### 2. Iniciar servicios de respaldo (Docker)

```bash
docker compose up -d
```

Esto inicia PostgreSQL en el puerto `5432`.

### 3. Configurar el entorno

```bash
cp .env.example .env
```

Edite el archivo .env y configure el proyecto.

### 4. Ejecutar migraciones de DB

```bash
uv run alembic upgrade head
```

### 5. Iniciar el servidor

```bash
uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

Visite [http://localhost:8000/docs](http://localhost:8000/docs) para acceder a la interfaz de usuario interactiva de Swagger.

## Documentación interactiva

| URL | Descripción |
| --- | --- |
| [GET /docs](http://localhost:8000/docs) | Swagger |
| [GET /redoc](http://localhost:8000/redoc) | ReDoc |
| [GET /openapi.json](http://localhost:8000/openapi.json) | Esquema OpenAPI |
