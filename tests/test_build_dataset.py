"""Tests de la construction du jeu falsifie (images SYNTHETIQUES)."""
import numpy as np
import pytest
from PIL import Image

from src.preprocessing.build_tampered_eurosat import (
    HELD_OUT_ATTACK, SEEN_ATTACKS, build, build_from_images)


def _imgs(n=30):
    return np.random.default_rng(0).integers(0, 256, (n, 64, 64, 3), dtype=np.uint8)


def test_no_source_in_two_splits():
    d = build_from_images(_imgs(), seed=1)
    seen = {}
    for src, sp in zip(d["source"], d["split"]):
        seen.setdefault(int(src), set()).add(str(sp))
    assert all(len(v) == 1 for v in seen.values())


def test_held_out_attack_only_in_test():
    d = build_from_images(_imgs(), seed=1)
    blur = d["attack"] == HELD_OUT_ATTACK
    assert blur.any()
    assert set(d["split"][blur]) == {"test"}
    for sp in ("train", "val"):
        used = set(d["attack"][d["split"] == sp]) - {"none"}
        assert used <= set(SEEN_ATTACKS)


def test_labels_and_masks_consistent():
    d = build_from_images(_imgs(), seed=1)
    assert d["images"].dtype == np.uint8 and d["masks"].dtype == np.uint8
    assert d["images"].shape[1:] == (64, 64, 3) and d["masks"].shape[1:] == (64, 64)
    for lab, mask in zip(d["labels"], d["masks"]):
        assert (mask.sum() > 0) == bool(lab)


def test_each_source_has_authentic_and_tampered():
    d = build_from_images(_imgs(), seed=1)
    for s in np.unique(d["source"]):
        labs = d["labels"][d["source"] == s]
        assert (labs == 0).sum() == 1 and (labs == 1).sum() >= 1


def test_deterministic():
    a = build_from_images(_imgs(), seed=3)
    b = build_from_images(_imgs(), seed=3)
    assert np.array_equal(a["images"], b["images"]) and np.array_equal(a["masks"], b["masks"])


@pytest.fixture
def fake_eurosat_rgb(tmp_path):
    """Meme structure que EuroSAT_RGB.zip decompresse : un dossier par classe, des .jpg 64x64."""
    root = tmp_path / "EuroSAT_RGB"
    rng = np.random.default_rng(0)
    for cls in ("AnnualCrop", "Forest", "River"):
        (root / cls).mkdir(parents=True)
        for i in range(6):
            Image.fromarray(rng.integers(0, 256, (64, 64, 3), dtype=np.uint8)).save(root / cls / f"{cls}_{i + 1}.jpg")
    return root


def test_build_reads_eurosat_rgb_folder(fake_eurosat_rgb, tmp_path):
    out = tmp_path / "d.npz"
    d = build(n_sources=15, seed=0, eurosat_dir=str(fake_eurosat_rgb), out=str(out))
    assert out.exists()
    assert d["images"].shape[1:] == (64, 64, 3) and len(np.unique(d["source"])) == 15


def test_build_explains_missing_folder_and_too_many_sources(fake_eurosat_rgb, tmp_path):
    with pytest.raises(FileNotFoundError, match="EuroSAT RGB"):
        build(eurosat_dir=str(tmp_path / "nowhere"), out=str(tmp_path / "x.npz"))
    with pytest.raises(ValueError, match="n_sources"):
        build(n_sources=19, eurosat_dir=str(fake_eurosat_rgb), out=str(tmp_path / "x.npz"))
