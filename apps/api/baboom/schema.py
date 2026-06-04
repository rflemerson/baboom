"""Root Strawberry schema for the Baboom API."""

import strawberry

from core.graphql.permissions import IsAuthenticatedWithAPIKey
from scrapers.graphql.schema import ScrapersMutation


@strawberry.type
class Query:
    """Root GraphQL Query."""

    @strawberry.field(permission_classes=[IsAuthenticatedWithAPIKey])
    def agent_api(self) -> str:
        """Return the agent GraphQL API status."""
        return "ok"


@strawberry.type
class Mutation(ScrapersMutation):
    """Root GraphQL Mutation."""


schema = strawberry.Schema(query=Query, mutation=Mutation)
