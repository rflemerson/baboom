import strawberry

from core.graphql.schema import CoreMutation, CoreQuery


@strawberry.type
class Query(
    CoreQuery,
):
    @strawberry.field
    def hello(self) -> str:
        return "Baboom GraphQL API is Online"


@strawberry.type
class Mutation(
    CoreMutation,
):
    pass


schema = strawberry.Schema(query=Query, mutation=Mutation)
