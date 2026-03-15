from enum import Enum

import strawberry


@strawberry.enum
class PackagingEnum(Enum):
    """Packaging type enumeration."""

    REFILL = "REFILL"
    CONTAINER = "CONTAINER"
    BAR = "BAR"
    OTHER = "OTHER"


@strawberry.enum
class StockStatusEnum(Enum):
    """Stock status enumeration."""

    AVAILABLE = "A"
    LAST_UNITS = "L"
    OUT_OF_STOCK = "O"
