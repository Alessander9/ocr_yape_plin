"""
Detector de duplicados y utilidades de hash.
=============================================
Usa hash perceptual (imagehash) para comparar imágenes similares.
"""

import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from loguru import logger

try:
    from PIL import Image
    import imagehash
    _IMAGEHASH_OK = True
except ImportError:
    _IMAGEHASH_OK = False
    logger.warning("imagehash no disponible. Detección de duplicados basada solo en MD5.")


def hash_md5_archivo(ruta: Path) -> str:
    """Calcula MD5 del archivo binario."""
    h = hashlib.md5()
    with open(ruta, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def hash_perceptual(ruta: Path) -> Optional[str]:
    """
    Calcula hash perceptual de la imagen (phash).
    Dos imágenes visualmente similares tendrán hashes similares.
    """
    if not _IMAGEHASH_OK:
        return None
    try:
        img = Image.open(ruta).convert("RGB")
        return str(imagehash.phash(img))
    except Exception as e:
        logger.debug(f"No se pudo calcular hash perceptual de {ruta.name}: {e}")
        return None


def son_similares(hash1: str, hash2: str, umbral: int = 10) -> bool:
    """
    Compara dos hashes perceptuales.
    umbral: diferencia máxima de bits para considerar similar (0 = idéntico).
    """
    if not _IMAGEHASH_OK:
        return hash1 == hash2
    try:
        h1 = imagehash.hex_to_hash(hash1)
        h2 = imagehash.hex_to_hash(hash2)
        return (h1 - h2) <= umbral
    except Exception:
        return hash1 == hash2


class RegistroHashes:
    """Mantiene un registro de hashes para detectar duplicados en un lote."""

    def __init__(self):
        self._hashes_md5: Dict[str, str] = {}        # md5 -> archivo
        self._hashes_percept: Dict[str, str] = {}    # phash -> archivo

    def verificar_y_registrar(self, ruta: Path) -> Tuple[str, bool]:
        """
        Calcula el hash de la imagen y verifica si ya existe.
        Retorna: (hash_md5, es_duplicado)
        """
        md5 = hash_md5_archivo(ruta)
        phash = hash_perceptual(ruta)

        es_duplicado = False

        # Verificar por MD5 exacto
        if md5 in self._hashes_md5:
            logger.info(f"Duplicado exacto detectado: {ruta.name} == {self._hashes_md5[md5]}")
            es_duplicado = True
        else:
            self._hashes_md5[md5] = ruta.name

        # Verificar por similitud perceptual
        if phash and not es_duplicado:
            for h_existente, archivo_existente in self._hashes_percept.items():
                if son_similares(phash, h_existente, umbral=8):
                    logger.info(f"Posible duplicado visual: {ruta.name} ~ {archivo_existente}")
                    es_duplicado = True
                    break
            if phash not in self._hashes_percept:
                self._hashes_percept[phash] = ruta.name

        return md5, es_duplicado
