"""EA (Executive Assistant) agent: Sultan's single interface to the system."""

from vizier.core.agents.ea.factory import create_ea_runtime
from vizier.core.agents.ea.prompts import EAPromptAssembler

__all__ = [
    "EAPromptAssembler",
    "create_ea_runtime",
]
