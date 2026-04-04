"""Media extractor registry and extractors for multimodal content.

Provides a registry-based dispatch system for media file processing,
replacing hardcoded if/else branches. Each extractor handles specific
MIME types and returns extracted text content.
"""

from __future__ import annotations

import asyncio
import io
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import httpx

from beever_atlas.infra.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class MediaContent:
    """Result of media extraction."""
    text: str = ""
    media_urls: list[str] = field(default_factory=list)
    media_type: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class MediaExtractor(ABC):
    """Base class for media extractors."""

    @property
    @abstractmethod
    def supported_mime_types(self) -> list[str]:
        """MIME types this extractor handles."""

    @property
    @abstractmethod
    def supported_extensions(self) -> list[str]:
        """File extensions this extractor handles (without dot)."""

    @abstractmethod
    async def extract(
        self, data: bytes, filename: str, metadata: dict[str, Any] | None = None
    ) -> MediaContent:
        """Extract content from file bytes."""


class MediaExtractorRegistry:
    """Registry that dispatches file processing to the appropriate extractor."""

    def __init__(self) -> None:
        self._mime_map: dict[str, MediaExtractor] = {}
        self._ext_map: dict[str, MediaExtractor] = {}

    def register(self, extractor: MediaExtractor) -> None:
        """Register an extractor for its supported MIME types and extensions."""
        for mime in extractor.supported_mime_types:
            self._mime_map[mime.lower()] = extractor
        for ext in extractor.supported_extensions:
            self._ext_map[ext.lower()] = extractor

    def get_extractor(
        self, mimetype: str = "", filename: str = ""
    ) -> MediaExtractor | None:
        """Find an extractor by MIME type or file extension."""
        if mimetype:
            extractor = self._mime_map.get(mimetype.lower())
            if extractor:
                return extractor
        if filename and "." in filename:
            ext = filename.rsplit(".", 1)[-1].lower()
            return self._ext_map.get(ext)
        return None

    async def extract(
        self,
        data: bytes,
        filename: str,
        mimetype: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> MediaContent:
        """Dispatch to the appropriate extractor, or return metadata-only fallback."""
        extractor = self.get_extractor(mimetype, filename)
        if extractor is None:
            ext = filename.rsplit(".", 1)[-1] if "." in filename else "unknown"
            return MediaContent(
                text=f"[Attachment: {filename} ({ext})]",
                media_type=ext,
                metadata={"fallback": True},
            )
        return await extractor.extract(data, filename, metadata)


# ── Concrete Extractors ────────────────────────────────────────────────


class PdfExtractor(MediaExtractor):
    """Extract text from PDF files using pypdf."""

    MAX_CHARS = 5000

    @property
    def supported_mime_types(self) -> list[str]:
        return ["application/pdf"]

    @property
    def supported_extensions(self) -> list[str]:
        return ["pdf"]

    async def extract(
        self, data: bytes, filename: str, metadata: dict[str, Any] | None = None
    ) -> MediaContent:
        text = await asyncio.to_thread(self._extract_text, data)
        size_kb = len(data) // 1024
        if text.strip():
            desc = (
                f"[Attachment: {filename} (PDF, {size_kb} kB)]\n"
                f"[Document text: {text[:self.MAX_CHARS]}]"
            )
        else:
            desc = f"[Attachment: {filename} (PDF, {size_kb} kB, no extractable text)]"
        return MediaContent(text=desc, media_type="pdf")

    @staticmethod
    def _extract_text(data: bytes) -> str:
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data))
            pages: list[str] = []
            char_count = 0
            for page in reader.pages:
                page_text = page.extract_text() or ""
                if page_text.strip():
                    pages.append(page_text.strip())
                    char_count += len(page_text.strip())
                    if char_count >= PdfExtractor.MAX_CHARS:
                        break
            result = "\n\n".join(pages)
            if char_count >= PdfExtractor.MAX_CHARS:
                result = result[:PdfExtractor.MAX_CHARS]
                result += "\n[...truncated]"
            return result
        except Exception:
            logger.warning("PdfExtractor: text extraction failed", exc_info=True)
            return ""


class ImageExtractor(MediaExtractor):
    """Describe images using Gemini vision API."""

    # Patterns suggesting visual content worth describing
    _VISUAL_RE = re.compile(
        r"screenshot|diagram|chart|graph|whiteboard|mockup|wireframe|design|sketch",
        re.IGNORECASE,
    )
    _ATTACHMENT_REF_RE = re.compile(
        r"see attached|check this|look at this|attached|screenshot|see above|here'?s the",
        re.IGNORECASE,
    )

    @property
    def supported_mime_types(self) -> list[str]:
        return [
            "image/png", "image/jpeg", "image/jpg", "image/gif", "image/webp",
        ]

    @property
    def supported_extensions(self) -> list[str]:
        return ["png", "jpg", "jpeg", "gif", "webp"]

    async def extract(
        self, data: bytes, filename: str, metadata: dict[str, Any] | None = None
    ) -> MediaContent:
        message_text = (metadata or {}).get("message_text", "")
        size_kb = len(data) // 1024

        if not self._should_use_vision(message_text, filename):
            return MediaContent(
                text=f"[Attachment: {filename} (image)]",
                media_type="image",
            )

        description = await self._describe_image(data, message_text)
        if description:
            desc = (
                f"[Attachment: {filename} (image, {size_kb} kB)]\n"
                f"[Image description: {description}]"
            )
        else:
            desc = f"[Attachment: {filename} (image, {size_kb} kB)]"
        return MediaContent(text=desc, media_type="image")

    def _should_use_vision(self, message_text: str, filename: str) -> bool:
        text = (message_text or "").strip()
        if len(text) < 50:
            return True
        if self._ATTACHMENT_REF_RE.search(text):
            return True
        if filename and self._VISUAL_RE.search(filename):
            return True
        return False

    async def _describe_image(self, data: bytes, message_context: str) -> str:
        try:
            from google import genai
            from google.genai import types as genai_types
            settings = get_settings()
            client = genai.Client(api_key=settings.google_api_key)

            prompt = (
                "Describe this image concisely for a knowledge extraction system. "
                "Focus on: key data points, text visible in the image, chart/graph values, "
                "names, dates, and any actionable information. "
                "Keep the description under 200 words."
            )
            if message_context:
                prompt += f"\n\nMessage context: {message_context[:200]}"

            response = await client.aio.models.generate_content(
                model=settings.media_vision_model,
                contents=[
                    genai_types.Content(
                        role="user",
                        parts=[
                            genai_types.Part.from_bytes(data=data, mime_type="image/png"),
                            genai_types.Part.from_text(text=prompt),
                        ],
                    )
                ],
            )
            return response.text or ""
        except Exception:
            logger.warning("ImageExtractor: vision description failed", exc_info=True)
            return ""


class OfficeExtractor(MediaExtractor):
    """Extract text from Office documents (docx, xlsx, pptx)."""

    @property
    def supported_mime_types(self) -> list[str]:
        return [
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "application/msword",
            "application/vnd.ms-excel",
            "application/vnd.ms-powerpoint",
        ]

    @property
    def supported_extensions(self) -> list[str]:
        return ["docx", "xlsx", "pptx", "doc", "xls", "ppt"]

    async def extract(
        self, data: bytes, filename: str, metadata: dict[str, Any] | None = None
    ) -> MediaContent:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        settings = get_settings()
        max_chars = settings.media_office_max_chars
        size_kb = len(data) // 1024

        text = await asyncio.to_thread(self._extract_text, data, ext, max_chars)

        if text.strip():
            desc = (
                f"[Attachment: {filename} ({ext.upper()}, {size_kb} kB)]\n"
                f"[Document text: {text}]"
            )
        else:
            desc = f"[Attachment: {filename} ({ext.upper()}, {size_kb} kB, no extractable text)]"

        return MediaContent(text=desc, media_type=ext)

    @staticmethod
    def _extract_text(data: bytes, ext: str, max_chars: int) -> str:
        try:
            if ext in ("docx", "doc"):
                return OfficeExtractor._extract_docx(data, max_chars)
            elif ext in ("xlsx", "xls"):
                return OfficeExtractor._extract_xlsx(data, max_chars)
            elif ext in ("pptx", "ppt"):
                return OfficeExtractor._extract_pptx(data, max_chars)
        except Exception:
            logger.warning("OfficeExtractor: extraction failed for .%s", ext, exc_info=True)
        return ""

    @staticmethod
    def _extract_docx(data: bytes, max_chars: int) -> str:
        from docx import Document
        doc = Document(io.BytesIO(data))
        parts: list[str] = []
        char_count = 0
        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue
            if para.style and para.style.name and para.style.name.startswith("Heading"):
                parts.append(f"## {text}")
            else:
                parts.append(text)
            char_count += len(text)
            if char_count >= max_chars:
                parts.append("[...truncated]")
                break
        return "\n".join(parts)

    @staticmethod
    def _extract_xlsx(data: bytes, max_chars: int) -> str:
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        parts: list[str] = []
        char_count = 0
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            parts.append(f"Sheet: {sheet_name}")
            for row in ws.iter_rows(values_only=True):
                cells = [str(c) if c is not None else "" for c in row]
                if any(cells):
                    line = " | ".join(cells)
                    parts.append(line)
                    char_count += len(line)
                    if char_count >= max_chars:
                        parts.append("[...truncated]")
                        break
            if char_count >= max_chars:
                break
        wb.close()
        return "\n".join(parts)

    @staticmethod
    def _extract_pptx(data: bytes, max_chars: int) -> str:
        from pptx import Presentation
        prs = Presentation(io.BytesIO(data))
        parts: list[str] = []
        char_count = 0
        for i, slide in enumerate(prs.slides, 1):
            slide_text: list[str] = []
            for shape in slide.shapes:
                if shape.has_text_frame:
                    for para in shape.text_frame.paragraphs:
                        text = para.text.strip()
                        if text:
                            slide_text.append(text)
            notes = ""
            if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
                notes = slide.notes_slide.notes_text_frame.text.strip()

            content = f"Slide {i}: " + " ".join(slide_text)
            if notes:
                content += f"\nNotes: {notes}"
            parts.append(content)
            char_count += len(content)
            if char_count >= max_chars:
                parts.append("[...truncated]")
                break
        return "\n".join(parts)


class VideoExtractor(MediaExtractor):
    """Extract content from video files via keyframe extraction + audio transcription."""

    @property
    def supported_mime_types(self) -> list[str]:
        return ["video/mp4", "video/quicktime", "video/x-msvideo", "video/webm", "video/mpeg"]

    @property
    def supported_extensions(self) -> list[str]:
        return ["mp4", "mov", "avi", "webm", "mpeg", "mkv"]

    async def extract(
        self, data: bytes, filename: str, metadata: dict[str, Any] | None = None
    ) -> MediaContent:
        settings = get_settings()
        size_mb = len(data) / (1024 * 1024)
        max_size = settings.media_video_max_size_mb

        if size_mb > max_size:
            return MediaContent(
                text=f"[Attachment: {filename} (video, {size_mb:.1f} MB — exceeds {max_size} MB limit)]",
                media_type="video",
            )

        parts: list[str] = []
        parts.append(f"[Attachment: {filename} (video, {size_mb:.1f} MB)]")

        # Attempt audio transcription
        transcript = await self._transcribe_audio(data, filename)
        if transcript:
            parts.append(f"[Video transcript: {transcript}]")

        # Attempt keyframe description (simplified — extract first frame)
        keyframe_desc = await self._describe_keyframes(data, metadata)
        if keyframe_desc:
            parts.append(f"[Keyframe descriptions: {keyframe_desc}]")

        return MediaContent(
            text="\n".join(parts),
            media_type="video",
        )

    async def _transcribe_audio(self, data: bytes, filename: str) -> str:
        """Transcribe video audio track via Gemini Flash."""
        settings = get_settings()
        if not settings.google_api_key:
            logger.debug("VideoExtractor: no Google API key, skipping transcription")
            return ""

        try:
            from google import genai
            from google.genai import types as genai_types

            client = genai.Client(api_key=settings.google_api_key)

            # Determine MIME type from filename
            ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "mp4"
            mime_map = {"mp4": "video/mp4", "mov": "video/quicktime", "webm": "video/webm", "avi": "video/x-msvideo"}
            mime_type = mime_map.get(ext, "video/mp4")

            response = await client.aio.models.generate_content(
                model=settings.media_vision_model,
                contents=[
                    genai_types.Content(
                        role="user",
                        parts=[
                            genai_types.Part.from_bytes(data=data, mime_type=mime_type),
                            genai_types.Part.from_text(
                                text="Transcribe all speech in this video. Return only the transcript text, no timestamps or speaker labels. If there is no speech, return an empty string."
                            ),
                        ],
                    )
                ],
            )
            return response.text or ""
        except Exception:
            logger.warning("VideoExtractor: Gemini transcription failed", exc_info=True)
            return ""

    async def _describe_keyframes(
        self, data: bytes, metadata: dict[str, Any] | None
    ) -> str:
        """Extract and describe keyframes. Currently returns empty — requires ffmpeg."""
        # Full implementation requires ffmpeg for keyframe extraction
        # This is a placeholder that can be enhanced when ffmpeg is available
        return ""


class AudioExtractor(MediaExtractor):
    """Transcribe audio files using Whisper API."""

    @property
    def supported_mime_types(self) -> list[str]:
        return [
            "audio/mpeg", "audio/mp3", "audio/wav", "audio/x-wav",
            "audio/mp4", "audio/m4a", "audio/ogg", "audio/x-m4a",
        ]

    @property
    def supported_extensions(self) -> list[str]:
        return ["mp3", "wav", "m4a", "ogg", "flac", "aac"]

    async def extract(
        self, data: bytes, filename: str, metadata: dict[str, Any] | None = None
    ) -> MediaContent:
        settings = get_settings()
        size_mb = len(data) / (1024 * 1024)

        parts: list[str] = [f"[Attachment: {filename} (audio, {size_mb:.1f} MB)]"]

        if not settings.google_api_key:
            return MediaContent(text="\n".join(parts), media_type="audio")

        try:
            from google import genai
            from google.genai import types as genai_types

            client = genai.Client(api_key=settings.google_api_key)

            # Determine MIME type from filename
            ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "mp3"
            mime_map = {"mp3": "audio/mpeg", "wav": "audio/wav", "m4a": "audio/mp4", "ogg": "audio/ogg", "flac": "audio/flac"}
            mime_type = mime_map.get(ext, "audio/mpeg")

            response = await client.aio.models.generate_content(
                model=settings.media_vision_model,
                contents=[
                    genai_types.Content(
                        role="user",
                        parts=[
                            genai_types.Part.from_bytes(data=data, mime_type=mime_type),
                            genai_types.Part.from_text(
                                text="Transcribe all speech in this audio. Return only the transcript text. If there is no speech, return an empty string."
                            ),
                        ],
                    )
                ],
            )
            transcript = response.text or ""
            if transcript:
                parts.append(f"[Audio transcript: {transcript}]")
        except Exception:
            logger.warning("AudioExtractor: Gemini transcription failed", exc_info=True)

        return MediaContent(text="\n".join(parts), media_type="audio")


def create_default_registry() -> MediaExtractorRegistry:
    """Create a registry with all default extractors registered."""
    registry = MediaExtractorRegistry()
    registry.register(PdfExtractor())
    registry.register(ImageExtractor())
    registry.register(OfficeExtractor())
    registry.register(VideoExtractor())
    registry.register(AudioExtractor())
    return registry
