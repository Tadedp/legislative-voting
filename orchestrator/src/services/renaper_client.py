import asyncio

from structlog import get_logger

log = get_logger(__name__)

class RenaperClient:
    async def verify_identity(
        self,
        national_id: str,
        biometric_payload: str,
    ) -> bool:
        log.info(
            "renaper.verify_identity",
            national_id=national_id,
            payload_length=len(biometric_payload),
        )

        await asyncio.sleep(1)

        log.info(
            "renaper.verify_identity.success",
            national_id=national_id,
        )
        return True

renaper_client = RenaperClient()
