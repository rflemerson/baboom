import strawberry

from core.graphql.permissions import IsAuthenticatedWithAPIKey
from core.graphql.schema import CoreMutation, CoreQuery


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
):
    pass


schema = strawberry.Schema(query=Query, mutation=Mutation)
