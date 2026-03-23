"""Terminal-specific configuration.

Configuration options for connecting to the shared OpenTerminal deployment.

Reference: https://github.com/open-webui/open-terminal
"""
from dataclasses import dataclass
import os


@dataclass
class TerminalConfig:
    """Configuration for static terminal connection.

    The terminal is deployed via Terraform as a single shared instance.
    All settings can be overridden via environment variables.

    Attributes:
        url: URL of the terminal API (e.g., "http://open-terminal:7681")
        api_key: API key for authentication
    """

    url: str = "http://open-terminal:7681"
    api_key: str = ""

    @classmethod
    def from_env(cls) -> "TerminalConfig":
        """Load configuration from environment variables.

        Environment variables:
            TERMINAL_URL: URL of the terminal API
            TERMINAL_API_KEY: API key for authentication

        Returns:
            TerminalConfig instance with values from environment
        """
        return cls(
            url=os.getenv("TERMINAL_URL", cls.url),
            api_key=os.getenv("TERMINAL_API_KEY", cls.api_key),
        )
