"""Custom exception hierarchy for the competitor intelligence engine."""


class AppError(Exception):
    """Base exception for all application errors."""

    def __init__(self, message: str, details: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ConfigError(AppError):
    """Configuration or settings error."""


class DatabaseError(AppError):
    """Database operation error."""


class AuthenticationError(AppError):
    """Authentication or authorization error."""


class ValidationError(AppError):
    """Input validation error."""


class FetchError(AppError):
    """HTTP fetching error."""


class SSRFError(FetchError):
    """SSRF protection blocked the request."""


class DNSResolutionError(FetchError):
    """DNS resolution failed."""


class ParseError(AppError):
    """HTML/content parsing error."""


class CollectionError(AppError):
    """Data collection error."""


class CompetitorNotFoundError(AppError):
    """Competitor not found in database."""

    def __init__(self, competitor_id: int) -> None:
        super().__init__(
            f"Competitor {competitor_id} not found",
            details={"competitor_id": competitor_id},
        )
        self.competitor_id = competitor_id


class ModuleError(AppError):
    """Unknown collection module."""

    def __init__(self, module: str) -> None:
        super().__init__(
            f"Unknown module: {module}",
            details={"module": module},
        )
        self.module = module
