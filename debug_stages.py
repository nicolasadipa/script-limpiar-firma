"""
debug_stages.py — Instrumentación del pipeline ACTUAL (processor.py).

Ejecuta cada etapa del pipeline sobre un archivo de entrada y vuelca:
  - Una imagen PNG por etapa en debug_output/<nombre_caso>/
  - Métricas por etapa (px de tinta, % de tinta, nº de componentes, etc.)

A diferencia del viejo debug_signature.py (roto, importaba _to_gray/_denoise),
este coincide con el pipeline real basado en "mapa de tinta".

Uso:
    python debug_stages.py "<ruta_entrada>" [nombre_caso]
"""

from __future__ import annotations

import os
import sys
import cv2
import numpy as np

import config
from logger import setup_logger
from processor import (
    _flatten_to_bgr,
    _normalize_resolution,
    _remove_scanner_footer,
    _correct_illumination,
    _detect_ink_color,
    _extract_ink_channel,
    _denoise_tinta_map,
    _binarize,
    _clean_morphology,
    _remove_artifacts,
    _remove_straight_lines,
    _remove_solid_blobs,
    _isolate_main_cluster,
    _find_signature_bbox,
    _add_padding,
)

logger = setup_logger()

DEBUG_ROOT = os.path.join(config.BASE_DIR, "debug_output")


def _load(input_path: str) -> np.ndarray:
    ext = os.path.splitext(input_path)[1].lower()
    if ext == ".pdf":
        from pdf_converter import pdf_to_image
        return pdf_to_image(input_path)
    if ext in {".docx", ".doc"}:
        from docx_converter import get_first_signature_from_docx
        return get_first_signature_from_docx(input_path)
    # Mismo manejo de alfa que el pipeline real (Fix A)
    raw = cv2.imread(input_path, cv2.IMREAD_UNCHANGED)
    if raw is None:
        raise RuntimeError(f"No se pudo leer: {input_path}")
    return _flatten_to_bgr(raw)


def _ink_stats(binary: np.ndarray) -> tuple[int, float, int]:
    """Devuelve (px_tinta, %_tinta, n_componentes)."""
    px = int(np.count_nonzero(binary))
    pct = 100.0 * px / binary.size
    n, _ = cv2.connectedComponents(binary, connectivity=8)
    return px, pct, n - 1  # -1 = sin contar el fondo


def _stroke_width_stats(binary: np.ndarray) -> tuple[float, float, float]:
    """
    Estima el grosor de trazo vía distance transform sobre el esqueleto medio.
    Devuelve (grosor_medio, grosor_std, cv) donde cv = std/medio (coef. variación).

    Texto impreso: cv bajo (grosor uniforme).
    Firma manuscrita: cv alto (grosor variable, presión).
    """
    if not np.any(binary):
        return 0.0, 0.0, 0.0
    dist = cv2.distanceTransform(binary, cv2.DIST_L2, 5)
    # El valor del distance transform en cada pixel de tinta ~ mitad del grosor local.
    vals = dist[binary > 0]
    # Usamos las crestas (máximos locales) como proxy del radio del trazo.
    ridge = vals[vals > 0.5]
    if ridge.size == 0:
        return 0.0, 0.0, 0.0
    mean = float(np.mean(ridge)) * 2.0
    std = float(np.std(ridge)) * 2.0
    cv = std / mean if mean > 0 else 0.0
    return mean, std, cv


def save(case_dir: str, name: str, img: np.ndarray) -> None:
    os.makedirs(case_dir, exist_ok=True)
    cv2.imwrite(os.path.join(case_dir, name), img)


def run(input_path: str, case_name: str | None = None) -> None:
    case = case_name or os.path.splitext(os.path.basename(input_path))[0]
    case_dir = os.path.join(DEBUG_ROOT, case)
    os.makedirs(case_dir, exist_ok=True)

    print(f"\n{'='*70}\nCASO: {case}\nInput: {input_path}\n{'='*70}")

    bgr = _load(input_path)
    H0, W0 = bgr.shape[:2]
    save(case_dir, "00_original.png", bgr)
    print(f"00 original          : {W0}x{H0}px")

    bgr = _normalize_resolution(bgr)
    save(case_dir, "00b_normalized.png", bgr)
    print(f"00b normalizado      : {bgr.shape[1]}x{bgr.shape[0]}px (target lado largo={config.WORK_LONG_SIDE_PX})")

    bgr = _remove_scanner_footer(bgr)
    save(case_dir, "01_no_footer.png", bgr)
    print(f"01 sin footer        : {bgr.shape[1]}x{bgr.shape[0]}px")

    bgr_corr = _correct_illumination(bgr)
    save(case_dir, "02_clahe.png", bgr_corr)

    ink = _detect_ink_color(bgr_corr)
    print(f"03 color tinta       : {ink.upper()}")

    tinta = _extract_ink_channel(bgr_corr, ink)
    save(case_dir, "04_tinta_map.png", tinta)
    print(f"04 mapa tinta        : min={tinta.min()} max={tinta.max()} mean={tinta.mean():.1f}")

    tinta_d = _denoise_tinta_map(tinta)
    save(case_dir, "05_tinta_denoised.png", tinta_d)
    # Cuánto borró el denoise respecto del mapa original (en zonas de tinta)
    diff = cv2.absdiff(tinta, tinta_d)
    print(f"05 denoise (h={config.DENOISE_H:>2}) : cambio_medio={diff.mean():.2f} cambio_max={diff.max()}")

    binary = _binarize(tinta_d, ink)
    px, pct, ncc = _ink_stats(binary)
    sw_mean, sw_std, sw_cv = _stroke_width_stats(binary)
    save(case_dir, "06_binary.png", binary)
    print(f"06 binarizado        : tinta={pct:.2f}% comps={ncc} grosor={sw_mean:.1f}px cv={sw_cv:.2f}")

    bin_m = _clean_morphology(binary)
    px2, pct2, ncc2 = _ink_stats(bin_m)
    save(case_dir, "07_morphology.png", bin_m)
    lost = 100.0 * (px - px2) / px if px else 0.0
    print(f"07 morfología (open) : tinta={pct2:.2f}% comps={ncc2} (perdió {lost:.1f}% de px vs 06)")

    bin_a = _remove_artifacts(bin_m)
    px3, pct3, ncc3 = _ink_stats(bin_a)
    save(case_dir, "08_no_artifacts.png", bin_a)
    lost3 = 100.0 * (px2 - px3) / px2 if px2 else 0.0
    print(f"08 sin artefactos    : tinta={pct3:.2f}% comps={ncc3} (perdió {lost3:.1f}% de px vs 07)")

    bin_d = _remove_straight_lines(bin_a)
    pxd, pctd, nccd = _ink_stats(bin_d)
    save(case_dir, "08b_no_lines.png", bin_d)
    print(f"08b sin líneas (D)   : tinta={pctd:.2f}% comps={nccd} (quitó {px3-pxd} px)")

    bin_b = _remove_solid_blobs(bin_d)
    pxb, pctb, nccb = _ink_stats(bin_b)
    save(case_dir, "08c_no_blobs.png", bin_b)
    print(f"08c sin manchas (C)  : tinta={pctb:.2f}% comps={nccb} (quitó {pxd-pxb} px)")

    bin_c = _isolate_main_cluster(bin_b)
    px4, pct4, ncc4 = _ink_stats(bin_c)
    save(case_dir, "09_main_cluster.png", bin_c)
    lost4 = 100.0 * (px3 - px4) / px3 if px3 else 0.0
    print(f"09 cluster principal : tinta={pct4:.2f}% comps={ncc4} (descartó {lost4:.1f}% de px vs 08)")

    bbox = _find_signature_bbox(bin_c)
    if bbox is None:
        print("10 bbox              : NO DETECTADO")
        return
    x, y, w, h = bbox
    x1, y1, x2, y2 = _add_padding(x, y, w, h, bin_c.shape)
    # Visualizar bbox sobre la binaria y sobre el original
    vis = cv2.cvtColor(bin_c, cv2.COLOR_GRAY2BGR)
    cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 0, 255), 4)
    save(case_dir, "10_bbox.png", vis)
    crop = bin_c[y1:y2, x1:x2]
    save(case_dir, "11_crop.png", crop)
    print(f"10 bbox              : x={x} y={y} w={w} h={h} -> crop {crop.shape[1]}x{crop.shape[0]}px")
    print(f"\nSalida en: {case_dir}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python debug_stages.py \"<ruta_entrada>\" [nombre_caso]")
        sys.exit(1)
    run(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
