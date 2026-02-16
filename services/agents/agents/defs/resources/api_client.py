"""Dagster resource for API client access."""

from dagster import ConfigurableResource

from ...client import AgentClient


class AgentClientResource(ConfigurableResource):
    """Dagster resource for AgentClient."""

    def get_client(self) -> AgentClient:
        """Return the authenticated API client instance."""
        return AgentClient()
