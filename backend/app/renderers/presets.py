"""Tweet card presets — predefined style combinations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Preset:
    """A predefined combination of tweet card styles."""
    name: str
    theme: str
    background: str
    background_color: str | None = None
    background_gradient: list[str] | None = None
    radius: int = 16
    shadow: str = "medium"
    padding: str = "medium"


PRESETS: dict[str, Preset] = {
    "minimal": Preset(
        name="Minimal",
        theme="light",
        background="solid",
        background_color="#ffffff",
        radius=12,
        shadow="soft",
        padding="medium",
    ),
    "midnight": Preset(
        name="Midnight",
        theme="dark",
        background="gradient",
        background_gradient=["#0f0c29", "#302b63", "#24243e"],
        radius=16,
        shadow="strong",
        padding="medium",
    ),
    "paper": Preset(
        name="Paper",
        theme="light",
        background="solid",
        background_color="#f5f0e8",
        radius=4,
        shadow="soft",
        padding="large",
    ),
    "glass": Preset(
        name="Glass",
        theme="glass",
        background="gradient",
        background_gradient=["#667eea", "#764ba2"],
        radius=20,
        shadow="medium",
        padding="medium",
    ),
    "gradient": Preset(
        name="Gradient",
        theme="dark",
        background="gradient",
        background_gradient=["#fc466b", "#3f5efb"],
        radius=16,
        shadow="strong",
        padding="medium",
    ),
    "terminal": Preset(
        name="Terminal",
        theme="terminal",
        background="solid",
        background_color="#0d1117",
        radius=8,
        shadow="none",
        padding="medium",
    ),
}
