"""Importing this package registers every scenario. To add one, create a module and import it here."""
from . import competitor, harmful, injection, resource, sensitive, sysprompt  # noqa: F401
from .base import CATEGORIES, REGISTRY, Ctx, Ledger, Scenario  # noqa: F401
