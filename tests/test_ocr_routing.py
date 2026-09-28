"""
Pruebas del ruteo de conversión: ¿un PDF se convierte en el VPS (pymupdf4llm) o se
manda a OCR a la Mac mini? No llaman a la Mac: `ocr_client.ocr_pdf` se sustituye.

    uv run --extra parse pytest tests/test_ocr_routing.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

LABS = Path(__file__).resolve().parents[1]
if str(LABS) not in sys.path:
    sys.path.insert(0, str(LABS))

pymupdf = pytest.importorskip("pymupdf")
pytest.importorskip("pymupdf4llm")

from ingestion import ocr_client, pdf_triage
from ingestion import pipeline as P

PARA = ("El juez de control resolverá sobre la legalidad de la detención y las medidas "
        "cautelares solicitadas por el Ministerio Público en la audiencia inicial. ")


def _digital_pdf(pages: int = 3) -> bytes:
    doc = pymupdf.open()
    for i in range(pages):
        page = doc.new_page()
        page.insert_textbox(pymupdf.Rect(72, 72, 540, 760), f"Capítulo {i + 1}\n\n" + PARA * 8, fontsize=11)
    return doc.tobytes()


def _scanned_pdf(pages: int = 3, cover: float = 1.0) -> bytes:
    """Páginas que son sólo una imagen (como un escaneo), sin capa de texto."""
    src = pymupdf.open(stream=_digital_pdf(pages), filetype="pdf")
    out = pymupdf.open()
    for page in src:
        pix = page.get_pixmap(dpi=60)
        new = out.new_page(width=page.rect.width, height=page.rect.height)
        r = new.rect
        new.insert_image(pymupdf.Rect(r.x0, r.y0, r.x1 * cover ** .5, r.y1 * cover ** .5),
                         stream=pix.tobytes("png"))
    return out.tobytes()


@pytest.fixture
def fake_mac(monkeypatch):
    calls = []

    def fake_ocr(pdf, *, filename, pages, progress=lambda _m: None):
        calls.append({"filename": filename, "pages": pages})
        return {"markdown": "## Capítulo 1\n\n" + PARA * 20, "pages": pages,
                "seconds": 4.2, "engine": "docling+vision"}

    monkeypatch.setattr(ocr_client, "ocr_pdf", fake_ocr)
    return calls


# ── triage ────────────────────────────────────────────────────────────────────
def test_bad_char_ratio_flags_foreign_glyphs_and_replacement_chars():
    assert pdf_triage.bad_char_ratio("la encuesta, el debate y Böckenförde") == 0
    assert pdf_triage.bad_char_ratio("ඔඉ ඍඖඋඝඍඛගඉ") == 1          # fuente rota de sociología
    assert pdf_triage.bad_char_ratio("C������� 1") > 0.5


def test_triage_digital_stays_on_vps():
    t = pdf_triage.triage_pdf(_digital_pdf())
    assert not t["needs_ocr"] and t["scanned_pages"] == []


def test_triage_scanned_goes_to_ocr_even_with_small_scan_on_big_page():
    # Escaneo chico sobre hoja grande (caso real: 27–48% de cobertura).
    t = pdf_triage.triage_pdf(_scanned_pdf(cover=0.3))
    assert t["needs_ocr"] and t["scanned_pages"] == [1, 2, 3]


def test_triage_few_scanned_pages_stay_on_vps_and_are_listed():
    doc = pymupdf.open(stream=_digital_pdf(9), filetype="pdf")
    doc.insert_pdf(pymupdf.open(stream=_scanned_pdf(1), filetype="pdf"))
    t = pdf_triage.triage_pdf(doc.tobytes())
    assert not t["needs_ocr"] and t["scanned_pages"] == [10]


# ── convert_pdf: dónde se procesa ─────────────────────────────────────────────
def test_convert_digital_pdf_on_vps(fake_mac):
    info = {}
    md = P.convert_pdf(_digital_pdf(), name="ley.pdf", info=info)
    assert info["where"] == P.WHERE_VPS and info["engine"] == "pymupdf4llm"
    assert "juez de control" in md and fake_mac == []


def test_convert_scanned_pdf_on_mac(fake_mac):
    info = {}
    md = P.convert_pdf(_scanned_pdf(), name="cag.pdf", info=info)
    assert info["where"] == P.WHERE_MAC and info["engine"] == "docling+vision"
    assert info["pages"] == 3 and info["seconds"] == 4.2
    assert fake_mac == [{"filename": "cag.pdf", "pages": 3}] and "Capítulo 1" in md


def test_convert_reports_skipped_pages_when_below_threshold(fake_mac):
    doc = pymupdf.open(stream=_digital_pdf(9), filetype="pdf")
    doc.insert_pdf(pymupdf.open(stream=_scanned_pdf(1), filetype="pdf"))
    info = {}
    P.convert_pdf(doc.tobytes(), name="mixto.pdf", info=info)
    assert info["where"] == P.WHERE_VPS and info["skipped_pages"] == [10] and fake_mac == []


def test_vps_output_empty_falls_back_to_mac(fake_mac, monkeypatch):
    import pymupdf4llm
    monkeypatch.setattr(pymupdf4llm, "to_markdown", lambda _doc: "")
    info = {}
    P.convert_pdf(_digital_pdf(), name="raro.pdf", info=info)
    assert info["where"] == P.WHERE_MAC and "vacía" in info["reason"] and len(fake_mac) == 1


def test_ocr_unavailable_keeps_decision_in_info(monkeypatch):
    def down(*_a, **_k):
        raise ocr_client.OCRUnavailable("El servicio OCR de la Mac mini no responde")
    monkeypatch.setattr(ocr_client, "ocr_pdf", down)
    info = {}
    with pytest.raises(ocr_client.OCRUnavailable):
        P.convert_pdf(_scanned_pdf(), name="cag.pdf", info=info)
    assert info["where"] == P.WHERE_MAC          # el reporte dice qué se intentó


def test_ingest_pdf_dry_run_carries_conversion(fake_mac, tmp_path):
    pdf = tmp_path / "escaneado.pdf"
    pdf.write_bytes(_scanned_pdf())
    r = P.ingest_pdf(pdf, table="t", tei=None, connect_fn=None, clean_dir=tmp_path,
                     save_clean=False, dry_run=True)
    assert r.error is None and r.conversion["where"] == P.WHERE_MAC and r.n_chunks > 0


# ── cliente HTTP (sin red: transporte simulado) ───────────────────────────────
def test_ocr_client_retries_on_429_then_succeeds(monkeypatch, tmp_path):
    import httpx
    token = tmp_path / "tok"
    token.write_text("x" * 64 + "\n")
    monkeypatch.setenv("OCR_TOKEN_FILE", str(token))
    monkeypatch.setattr(ocr_client.time, "sleep", lambda _s: None)
    answers = iter([httpx.Response(429, headers={"Retry-After": "1"}, json={"detail": "busy"}),
                    httpx.Response(200, json={"markdown": "ok", "pages": 1, "seconds": 1.0,
                                              "engine": "docling+vision"})])
    seen_auth = []

    def fake_post(url, *, headers, **_k):
        seen_auth.append(headers["Authorization"])
        return next(answers)

    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr(ocr_client, "health", lambda: {"ok": True})
    msgs = []
    res = ocr_client.ocr_pdf(b"%PDF", filename="a.pdf", pages=1, progress=msgs.append)
    assert res["markdown"] == "ok" and len(seen_auth) == 2
    assert seen_auth[0] == "Bearer " + "x" * 64          # token sin el salto de línea
    assert any("ocupada" in m for m in msgs)


def test_ocr_client_missing_token_is_clear(monkeypatch, tmp_path):
    monkeypatch.setenv("OCR_TOKEN_FILE", str(tmp_path / "no-existe"))
    with pytest.raises(ocr_client.OCRUnavailable, match="token"):
        ocr_client.ocr_pdf(b"%PDF", filename="a.pdf", pages=1)
