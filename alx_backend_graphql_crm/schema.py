"""Root GraphQL schema composition for the CRM project."""
import graphene

from crm.schema import Mutation as CRMMutation
from crm.schema import Query as CRMQuery


class Query(CRMQuery, graphene.ObjectType):
    pass


class Mutation(CRMMutation, graphene.ObjectType):
    pass


schema = graphene.Schema(query=Query, mutation=Mutation)
