from __future__ import annotations

from pydantic import BaseModel


class ImageDescriptionResult(BaseModel):
    """Output schema for the image describer agent."""

    description: str = ""
    """Concise text description of the image content."""


class VideoAnalysisResult(BaseModel):
    """Output schema for the video analyzer agent."""

    summary: str = ""
    """Concise summary of the video content."""

    key_points: list[str] = []
    """Important points extracted from the video."""

    speakers: list[str] = []
    """Identified speakers and their roles."""

    visual_context: str = ""
    """Description of key visual elements."""

    language: str = ""
    """Primary language spoken in the video."""


class AudioTranscriptionResult(BaseModel):
    """Output schema for the audio analyzer agent."""

    summary: str = ""
    """Concise summary of the audio content."""

    key_points: list[str] = []
    """Important points extracted from the audio."""

    speakers: list[str] = []
    """Identified speakers and their roles."""

    language: str = ""
    """Primary language spoken in the audio."""
