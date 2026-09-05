from __future__ import annotations

import hashlib

import pytest

from app.services.figure_export import export_figure

SVG = """<svg xmlns='http://www.w3.org/2000/svg' width='120' height='80' viewBox='0 0 120 80'>
<rect x='0' y='0' width='120' height='80' fill='white'/>
<text x='10' y='30'>A</text><line x1='10' y1='50' x2='110' y2='50' stroke='black'/>
</svg>"""


def test_svg_is_canonical_and_content_addressed():
    artifact = export_figure(SVG, "svg")
    assert artifact.content_type == "image/svg+xml"
    assert artifact.payload == SVG.encode()
    assert artifact.sha256 == hashlib.sha256(artifact.payload).hexdigest()
    assert artifact.dpi is None


def test_invalid_raster_dpi_is_rejected():
    with pytest.raises(ValueError):
        export_figure(SVG, "png", 299)
    with pytest.raises(ValueError):
        export_figure(SVG, "tiff", 601)


def test_png_pdf_tiff_are_nonempty_real_exports_when_renderer_available():
    pytest.importorskip("cairosvg")
    pytest.importorskip("PIL")

    png = export_figure(SVG, "png", 300)
    assert png.content_type == "image/png"
    assert len(png.payload) > 100
    assert png.dpi == 300
    assert png.width_px and png.width_px >= 300

    pdf = export_figure(SVG, "pdf", 300)
    assert pdf.content_type == "application/pdf"
    assert len(pdf.payload) > 100
    assert pdf.dpi is None

    tiff = export_figure(SVG, "tiff", 600)
    assert tiff.content_type == "image/tiff"
    assert len(tiff.payload) > 100
    assert tiff.dpi == 600
    assert tiff.sha256 == hashlib.sha256(tiff.payload).hexdigest()
