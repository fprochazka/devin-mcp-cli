"""Configuration management for Devin MCP CLI.

The config holds several named accounts (aliases) in one YAML file. An account
alias (like ``work`` or ``personal``) is a local nickname you pick. It is
separate from the Devin ``org_id``, which is the Devin organization UUID sent as
the ``X-Org-Id`` header for key types that need it.
"""

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

# Devin MCP Server URL
DEVIN_MCP_URL = "https://mcp.devin.ai/mcp"


class ConfigError(Exception):
    """Configuration or account-resolution error."""


class OrgConfig(BaseModel):
    """Credentials for a single named account.

    ``name`` is the local alias. ``org_id`` is the Devin organization UUID and is
    optional. It is sent as ``X-Org-Id`` only when present.
    """

    name: str
    api_key: str
    org_id: str | None = None


class McpServerConfig(BaseModel):
    """MCP Server configuration."""

    timeout: int = Field(default=30, description="HTTP request timeout in seconds")
    sse_read_timeout: int = Field(default=300, description="SSE read timeout in seconds")


def _env_org() -> OrgConfig | None:
    """Build an ad-hoc account from environment variables, or None if unset.

    ``DEVIN_API_KEY`` alone yields an account named ``env``. ``DEVIN_ORG_ID``
    fills the optional org UUID.
    """
    api_key = os.getenv("DEVIN_API_KEY")
    if not api_key:
        return None
    org_id = os.getenv("DEVIN_ORG_ID") or None
    return OrgConfig(name="env", api_key=api_key, org_id=org_id)


class Config(BaseModel):
    """Main configuration for Devin MCP CLI."""

    orgs: dict[str, OrgConfig] = Field(default_factory=dict)
    default_org: str | None = None
    mcp_server: McpServerConfig = Field(default_factory=McpServerConfig)

    def get_org(self, name: str | None = None) -> OrgConfig:
        """Resolve the account to use, following the selection precedence.

        Order:
        1. Explicit ``name`` (from ``--org`` / ``DEVIN_ORG``).
        2. ``default_org`` from the config file.
        3. The sole configured account, if exactly one exists.
        4. Environment fallback (``DEVIN_API_KEY`` [+ ``DEVIN_ORG_ID``]).
        5. Error listing the available accounts.

        Raises:
            ConfigError: If the account cannot be resolved.
        """
        # 1. Explicit selection wins. It never falls through to the env fallback.
        if name:
            if name not in self.orgs:
                raise ConfigError(f"Account '{name}' not found. Available: {self._available()}")
            return self.orgs[name]

        # 2. default_org pointer.
        if self.default_org:
            if self.default_org not in self.orgs:
                raise ConfigError(
                    f"default_org '{self.default_org}' does not match any account. Available: {self._available()}"
                )
            return self.orgs[self.default_org]

        # 3. Sole configured account.
        if len(self.orgs) == 1:
            return next(iter(self.orgs.values()))

        # 4. Environment fallback preserves "works from env vars alone".
        env_org = _env_org()
        if env_org is not None:
            return env_org

        # 5. Nothing resolved.
        if self.orgs:
            raise ConfigError(
                f"No account selected and no default set. Use --org=<name> (available: {self._available()}) "
                "or run 'devin-mcp org use <name>'."
            )
        raise ConfigError(
            "No accounts configured. Run 'devin-mcp org add <name>' to add one, or set DEVIN_API_KEY "
            "(and optionally DEVIN_ORG_ID) in your environment."
        )

    def _available(self) -> str:
        return ", ".join(sorted(self.orgs)) if self.orgs else "(none)"


def get_config_path() -> Path:
    """Get the configuration file path.

    A ``./.devin-mcp.yaml`` in the current directory wins over the user config.
    """
    local_config = Path.cwd() / ".devin-mcp.yaml"
    if local_config.exists():
        return local_config

    config_dir = Path.home() / ".config" / "devin-mcp"
    return config_dir / "config.yaml"


def read_config_dict(config_path: Path | None = None) -> dict:
    """Read the raw config YAML into a dict, or an empty dict if absent."""
    if config_path is None:
        config_path = get_config_path()
    if not config_path.exists():
        return {}
    with open(config_path) as f:
        return yaml.safe_load(f) or {}


def load_config(config_path: Path | None = None) -> Config:
    """Load configuration from a YAML file.

    A missing file yields an empty config. Account resolution and its errors live
    in ``Config.get_org``, so callers that only inspect config never hard-fail.

    Raises:
        ConfigError: If an account entry has no ``api_key``.
    """
    data = read_config_dict(config_path)

    orgs: dict[str, OrgConfig] = {}
    orgs_data = data.get("orgs", {}) or {}
    for org_name, org_data in orgs_data.items():
        if not isinstance(org_data, dict):
            raise ConfigError(f"Invalid account config for '{org_name}': expected a mapping")
        api_key = org_data.get("api_key")
        if not api_key:
            raise ConfigError(f"Missing 'api_key' for account '{org_name}'")
        orgs[org_name] = OrgConfig(
            name=org_name,
            api_key=api_key,
            org_id=org_data.get("org_id") or None,
        )

    mcp_server_data = data.get("mcp_server", {}) or {}

    return Config(
        orgs=orgs,
        default_org=data.get("default_org"),
        mcp_server=McpServerConfig(**mcp_server_data),
    )


def save_config(config_path: Path, data: dict) -> None:
    """Write the config dict to YAML and lock the file to the owner.

    The file holds plaintext secrets, so the mode is set to 0600.
    """
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w") as f:
        yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)
    config_path.chmod(0o600)
