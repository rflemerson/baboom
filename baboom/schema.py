import strawberry

from core.graphql.permissions import IsAuthenticatedWithAPIKey
from core.graphql.schema import CoreMutation, CoreQuery
from scrapers.graphql.schema import ScrapersMutation


@strawberry.type
class Query(
    CoreQuery,
):
    """Root GraphQL Query."""

    @strawberry.field(permission_classes=[IsAuthenticatedWithAPIKey])
    def hello(self) -> str:
        """Simple health check field."""
        return "Baboom GraphQL API is Online"


@strawberry.type
class Mutation(
    CoreMutation,
    ScrapersMutation,
):
    """Root GraphQL Mutation."""

    pass


schema = strawberry.Schema(query=Query, mutation=Mutation)
