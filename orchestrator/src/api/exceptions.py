from http import HTTPStatus

from fastapi import HTTPException, status

class DetailedHTTPException(HTTPException):
    def __init__(
        self,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail: str | None = None,
    ) -> None:
        if detail is None:
            detail = HTTPStatus(status_code).description
        super().__init__(status_code=status_code, detail=detail)

class BadRequestException(DetailedHTTPException):
    """400 — Request payload failed schema or business-rule validation."""
    def __init__(
        self, 
        detail: str | None = None,
    ) -> None:
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=detail,
        )

class UnauthorizedException(DetailedHTTPException):
    """401 — Missing or invalid authentication credentials."""
    def __init__(
        self, 
        detail: str | None = None,
    ) -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail=detail,
        )

class ForbiddenException(DetailedHTTPException):
    """403 — Authenticated principal lacks permission for the resource."""
    def __init__(
        self, 
        detail: str | None = None,
    ) -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail=detail,
        )

class NotFoundException(DetailedHTTPException):
    """404 — Requested resource does not exist (or is soft-deleted)."""
    def __init__(
        self, 
        detail: str | None = None,
    ) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=detail,
        )

class ConflictException(DetailedHTTPException):
    """409 — Resource already exists or a conflicting state was detected."""
    def __init__(
        self, 
        detail: str | None = None,
    ) -> None:
        super().__init__(
            status_code=status.HTTP_409_CONFLICT, 
            detail=detail,
        )
        
class UnprocessableContentException(DetailedHTTPException):
    """422 — Request payload is syntactically correct but semantically invalid."""
    def __init__(
        self, 
        detail: str | None = None,
    ) -> None:
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, 
            detail=detail,
        )
        
class RateLimitException(DetailedHTTPException):
    """429 — Request rate limit exceeded."""
    def __init__(
        self, 
        detail: str | None = None,
    ) -> None:
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, 
            detail=detail,
        )     

class InternalServerException(DetailedHTTPException):
    """500 — Unexpected internal server error."""
    def __init__(
        self, 
        detail: str | None = None,
    ) -> None:
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=detail,
        )  

class ServiceUnavailableException(DetailedHTTPException):
    """503 — A required downstream dependency is unavailable."""
    def __init__(
        self, 
        detail: str | None = None,
    ) -> None:
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
            detail=detail,
        )  