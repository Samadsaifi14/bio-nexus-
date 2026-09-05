"""Publication figure export helpers.

BioNexus composes figures as SVG first, then derives distribution formats from
that single source so panel layout and labels do not diverge between formats.
Exports are content-addressed and return metadata suitable for figure
provenance records.
"""
from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass
from typing import Literal

FigureFormat = Literal["svg", "png", "pdf", "tiff"]


@dataclass(frozen=True)
class FigureArtifact:
    payload: bytes
    format: FigureFormat
    content_type: str
    dpi: int | None
    sha256: str
    width_px: int | None = None
    height_px: int | None = None

    def metadata(self) -> dict:
        return {
            "format": self.format,
            "content_type": self.content_type,
            "dpi": self.dpi,
            "sha256": self.sha256,
            "bytes": len(self.payload),
            "width_px": self.width_px,
            "height_px": self.height_px,
        }


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _raster_size(data: bytes) -> tuple[int | None, int | None]:
    try:
        from PIL import Image
        with Image.open(io.BytesIO(data)) as image:
            return image.size
    except Exception:
        return None, None


def export_figure(svg: str, fmt: FigureFormat = "svg", dpi: int = 300) -> FigureArtifact:
    """Convert the canonical SVG into a requested publication format.

    PNG/TIFF are rendered at 300-600 DPI. PDF remains vector. Conversion
    failures are raised to the caller; an endpoint must never return SVG bytes
    while labelling them as a raster/PDF artifact.
    """
    if fmt not in {"svg", "png", "pdf", "tiff"}:
        raise ValueError(f"unsupported figure format: {fmt}")
    if dpi < 300 or dpi > 600:
        raise ValueError("publication raster DPI must be between 300 and 600")

    svg_bytes = svg.encode("utf-8")
    if fmt == "svg":
        return FigureArtifact(svg_bytes, "svg", "image/svg+xml", None, _sha(svg_bytes))

    try:
        import cairosvg
    except ImportError as exc:
        raise RuntimeError("CairoSVG is required for PNG/PDF/TIFF figure export") from exc

    if fmt == "pdf":
        payload = cairosvg.svg2pdf(bytestring=svg_bytes)
        return FigureArtifact(payload, "pdf", "application/pdf", None, _sha(payload))

    # CairoSVG interprets output_width/height in pixels; scale from CSS 96 DPI.
    scale = dpi / 96.0
    png = cairosvg.svg2png(bytestring=svg_bytes, scale=scale)
    if fmt == "png":
        width, height = _raster_size(png)
        return FigureArtifact(png, "png", "image/png", dpi, _sha(png), width, height)

    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Pillow is required for TIFF figure export") from exc
    source = Image.open(io.BytesIO(png)).convert("RGB")
    out = io.BytesIO()
    source.save(out, format="TIFF", dpi=(dpi, dpi), compression="tiff_lzw")
    payload = out.getvalue()
    width, height = source.size
    return FigureArtifact(payload, "tiff", "image/tiff", dpi, _sha(payload), width, height)
