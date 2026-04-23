from src.core.config import settings
from src.core.logging import configure_logging
from src.core.setup import create_app

configure_logging(
    log_level=settings.logging.LEVEL.value,
    service_name=settings.logging.SERVICE_NAME,
)

app = create_app()
