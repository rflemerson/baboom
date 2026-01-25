import strawberry

from core.graphql.permissions import IsAuthenticatedWithAPIKey
from core.graphql.schema import CoreMutation, CoreQuery
from scrapers.graphql.schema import ScrapersMutation


@strawberry.type
class Query(
    CoreQuery,
):
    @strawberry.field(permission_classes=[IsAuthenticatedWithAPIKey])
    def hello(self) -> str:
        return "Baboom GraphQL API is Online"


@strawberry.type
class Mutation(
    CoreMutation,
    ScrapersMutation,
):
    pass


schema = strawberry.Schema(query=Query, mutation=Mutation)
