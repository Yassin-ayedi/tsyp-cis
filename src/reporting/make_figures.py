"""Figures for the documentation and the report, rebuilt from the run outputs.

    python -m src.reporting.make_figures            # writes docs/figures/*.png

Reads outputs/*.json (training, evasion, benchmark), the tampered dataset
(data/processed/eurosat_tampered.npz) and the deployed model
(outputs/forensic_unet_robust_far5.pt). Nothing is recomputed except the
example masks, which come from the deployed model on test tiles.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

OUT = Path("docs/figures")
O = Path("outputs")
NPZ = Path("data/processed/eurosat_tampered.npz")
MODEL = O / "forensic_unet_robust_far5.pt"

# Palette de reference (slots categoriels 1-3, encre et surface claires)
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
NORMAL, ROBUST, THIRD = "#2a78d6", "#eb6834", "#1baf7a"
ATTACKS = ("splice", "copy_move", "color_shift", "blur")
LABEL = {"splice": "Splice", "copy_move": "Copy-move", "color_shift": "Colour shift", "blur": "Blur (held out)"}

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True,
    "font.size": 10, "axes.titlesize": 11, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "legend.frameon": False,
})


def load(name: str) -> dict:
    return json.loads((O / name).read_text(encoding="utf-8"))


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    p = k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, c - h), min(1.0, c + h)


def save(fig, name: str) -> None:
    fig.savefig(OUT / name, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print("wrote", OUT / name)


def training_curves(norm: dict, rob: dict) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.4))
    for ax, key, title in ((axes[0], "val_auc", "Validation AUC"), (axes[1], "val_iou", "Validation IoU (mask)")):
        for run, colour, name in ((norm, NORMAL, "Normal"), (rob, ROBUST, "Robust")):
            ep = [h["epoch"] for h in run["history"]]
            ax.plot(ep, [h[key] for h in run["history"]], color=colour, lw=2, label=name)
            best = run["history"][run["best_epoch"] - 1]
            ax.plot(best["epoch"], best[key], "o", ms=8, color=colour, mec=SURFACE, mew=2)
        ax.set_title(title)
        ax.set_xlabel("epoch")
        ax.set_xlim(1, 30)
    axes[0].legend(loc="lower right")
    fig.text(0.01, -0.04, "Dots: epoch kept (best validation AUC + IoU). 5,000 source tiles, CPU, seed 0.",
             color=INK2, fontsize=9)
    save(fig, "training_curves.png")


def per_attack(norm: dict, rob: dict) -> None:
    fig, ax = plt.subplots(figsize=(8, 3.6))
    y = np.arange(len(ATTACKS))[::-1]
    h = 0.36
    for off, run, colour, name in ((h / 2 + 0.02, norm, NORMAL, "Normal"), (-h / 2 - 0.02, rob, ROBUST, "Robust")):
        for yi, a in zip(y, ATTACKS):
            m = run["per_attack"][a]
            k, n = round(m["recall"] * m["n"]), m["n"]
            lo, hi = wilson(k, n)
            ax.barh(yi + off, m["recall"] * 100, height=h, color=colour, label=name if a == "splice" else None)
            ax.errorbar(m["recall"] * 100, yi + off,
                        xerr=[[max(0.0, 100 * (m["recall"] - lo))], [max(0.0, 100 * (hi - m["recall"]))]],
                        color=INK2, lw=1, capsize=2)
            ax.text(hi * 100 + 1.5, yi + off, f"{m['recall'] * 100:.0f}%", va="center", fontsize=9, color=INK)
    ax.set_yticks(y, [LABEL[a] for a in ATTACKS])
    ax.set_xlim(0, 112)
    ax.set_xlabel("edited test images detected (%), 95% Wilson interval")
    ax.set_title("Detection rate by edit type (clean test set)")
    ax.grid(axis="y", visible=False)
    ax.legend(loc="lower right", bbox_to_anchor=(1, 0.02))
    save(fig, "per_attack_recall.png")


NAMES = {"none": "none (clean)", "jpeg_q90": "JPEG q90", "jpeg_q75": "JPEG q75", "jpeg_q60": "JPEG q60",
         "resample_0.75": "resample x0.75", "resample_0.5": "resample x0.5", "noise_s2": "noise s=2",
         "noise_s5": "noise s=5", "blur_r0.6": "blur r=0.6", "blur_r1.0": "blur r=1.0",
         "chain_resample+jpeg75": "resample + JPEG q75"}


def evasion(ev_n: dict, ev_r: dict) -> None:
    ops = list(NAMES)
    y = np.arange(len(ops))[::-1]
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.6), sharey=True)
    for ax, key, title in ((axes[0], "recall", "Edited images detected (%)"),
                           (axes[1], "false_alarm_rate", "Authentic images flagged (%)")):
        for run, colour, name, dy in ((ev_n, NORMAL, f"Normal (threshold {ev_n['threshold']:.2f})", 0.12),
                                      (ev_r, ROBUST, f"Robust, far5 (threshold {ev_r['threshold']:.2f})", -0.12)):
            v = [run["results"][o][key] * 100 for o in ops]
            ax.plot(v, y + dy, "o", ms=8, color=colour, mec=SURFACE, mew=1.5, label=name)
        for yi, o in zip(y, ops):
            a, b = ev_n["results"][o][key] * 100, ev_r["results"][o][key] * 100
            ax.plot([a, b], [yi + 0.12, yi - 0.12], color=GRID, lw=1.5, zorder=0)
        ax.set_title(title)
        ax.grid(axis="y", visible=False)
    axes[1].axvline(5, color=INK2, lw=1, ls="--")
    axes[1].text(5.5, y[0] + 0.45, "5% target", color=INK2, fontsize=9)
    axes[0].set_xlim(-2, 80)
    axes[1].set_xlim(-1, 22)
    axes[0].set_yticks(y, [NAMES[o] for o in ops])
    axes[0].legend(loc="lower center", bbox_to_anchor=(1.05, -0.32), ncol=2)
    fig.suptitle("Evasion scenario: laundering applied to all 3,000 test images", x=0.01, ha="left",
                 fontweight="bold", fontsize=11)
    save(fig, "evasion.png")


def latency(bench: dict) -> None:
    rows = (("cold_first_open", "First open\n(disk I/O included)"), ("warm", "Cached files"))
    parts = (("security_ms", "Layer 1: security checks", NORMAL), ("signals_ms", "Signals: SRM + ELA", ROBUST),
             ("model_ms", "Layer 2: ForensicUNet", THIRD))
    fig, ax = plt.subplots(figsize=(8.5, 2.6))
    for yi, (key, lab) in enumerate(rows):
        left = 0.0
        for k, name, colour in parts:
            v = bench[key][k]["mean"]
            ax.barh(yi, v, left=left, height=0.5, color=colour, edgecolor=SURFACE, linewidth=2,
                    label=name if yi == 0 else None)
            left += v
        ax.text(left + 1.5, yi, f"{bench[key]['total_ms']['mean']:.0f} ms  ({bench[key]['throughput_images_per_s']:.0f} img/s)",
                va="center", fontsize=9)
    ax.set_yticks(range(len(rows)), [r[1] for r in rows])
    ax.set_xlim(0, 112)
    ax.set_xlabel("mean time per 64x64 image (ms), laptop CPU, 200 signed test images")
    ax.set_title("Where the time goes")
    ax.grid(axis="y", visible=False)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.42), ncol=3)
    save(fig, "latency.png")


def _show(ax, img, title, cmap=None, vmin=None, vmax=None):
    ax.imshow(img, cmap=cmap, vmin=vmin, vmax=vmax, interpolation="nearest")
    ax.set_title(title, fontsize=9, fontweight="normal", loc="center")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)


def examples_and_signals() -> None:
    from src.forensics.signals import ela_map, srm_residuals
    from src.pipeline.analyze import detect, load_model
    d = np.load(NPZ)
    imgs, masks, src, att, split = d["images"], d["masks"], d["source"], d["attack"], d["split"]
    test = np.where(split == "test")[0]
    model, thr = load_model(MODEL)

    fig, axes = plt.subplots(len(ATTACKS), 4, figsize=(7.2, 7.6))
    for r, a in enumerate(ATTACKS):
        i = next(j for j in test if att[j] == a)
        auth = next(j for j in test if src[j] == src[i] and att[j] == "none")
        score, prob, _ = detect(model, imgs[i])
        _show(axes[r, 0], imgs[auth], "authentic tile" if r == 0 else "")
        _show(axes[r, 1], imgs[i], "edited tile" if r == 0 else "")
        _show(axes[r, 2], masks[i], "true edit mask" if r == 0 else "", cmap="gray", vmin=0, vmax=1)
        _show(axes[r, 3], prob, "model mask" if r == 0 else "", cmap="magma", vmin=0, vmax=1)
        axes[r, 0].set_ylabel(LABEL[a], fontsize=10, color=INK)
        verdict = "detected" if score >= thr else "missed"
        axes[r, 3].text(32, 70, f"score {score:.2f}: {verdict}", ha="center", va="top", fontsize=8.5, color=INK)
    fig.suptitle(f"Synthetic edits on EuroSAT test tiles and the deployed model's output (threshold {thr:.2f})",
                 x=0.01, ha="left", fontsize=10, fontweight="bold")
    fig.tight_layout()
    save(fig, "tamper_examples.png")

    i = next(j for j in test if att[j] == "splice")
    srm = srm_residuals(imgs[i]).numpy()[0]
    ela = ela_map(imgs[i]).numpy()[0, 0]
    fig, axes = plt.subplots(1, 6, figsize=(11, 2.4))
    _show(axes[0], imgs[i], "RGB (spliced)")
    for k in range(3):
        _show(axes[1 + k], srm[k], f"SRM residual {k + 1}", cmap="gray", vmin=-1, vmax=1)
    _show(axes[4], ela, "ELA (JPEG q90)", cmap="magma", vmin=0, vmax=max(float(ela.max()), 1e-6))
    _show(axes[5], masks[i], "true edit mask", cmap="gray", vmin=0, vmax=1)
    fig.suptitle("The 7 input channels of ForensicUNet for one spliced tile (64x64)", x=0.01, ha="left",
                 fontsize=10, fontweight="bold")
    save(fig, "forensic_signals.png")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    norm, rob = load("forensic_unet_run.json"), load("forensic_unet_robust_run.json")
    training_curves(norm, rob)
    per_attack(norm, rob)
    evasion(load("evasion_results.json"), load("evasion_results_robust.json"))
    latency(load("benchmark.json"))
    examples_and_signals()


if __name__ == "__main__":
    main()
