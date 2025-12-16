import os
import json
from glob import glob
from collections import defaultdict

import matplotlib.pyplot as plt


OUT_DIR = "data/reports/phase15_greedy"
IN_GLOB = "data/raw/*.json"  # adjust if you use subfolders


# ------------------------
# helpers
# ------------------------

def ensure_outdir():
    os.makedirs(OUT_DIR, exist_ok=True)


def load_results():
    paths = sorted(glob(IN_GLOB))
    if not paths:
        raise FileNotFoundError(f"No input files found at {IN_GLOB}")

    results = []
    for p in paths:
        with open(p, "r") as f:
            obj = json.load(f)
        obj["_path"] = p
        results.append(obj)
    return results


def scenario_label(r):
    ct = r.get("contract_type")
    ts = r.get("trump_suit")
    if ct == "suit":
        return f"suit_{ts}"
    return str(ct)


def _get_dist_team0(r):
    """distribution_team0 may have str keys after JSON."""
    dist = r.get("distribution_team0", {})
    out = {k: 0 for k in range(11)}
    for k in range(11):
        if isinstance(dist, dict):
            out[k] = dist.get(str(k), dist.get(k, 0))
        else:
            out[k] = dist[k]
    return out


def _merge_dist(dists):
    merged = {k: 0 for k in range(11)}
    for d in dists:
        for k in range(11):
            merged[k] += d.get(k, 0)
    return merged


def _dist_mean(dist):
    total = sum(dist.values())
    if total <= 0:
        return 0.0
    return sum(k * v for k, v in dist.items()) / total


def _merge_score_buckets(score_buckets_list):
    """
    Merge {score -> {count,total_tricks,avg_tricks}} across scenarios
    into {score -> {count,total_tricks,avg_tricks}}.
    """
    merged = defaultdict(lambda: {"count": 0, "total_tricks": 0.0})
    for sb in score_buckets_list:
        for score_k, v in sb.items():
            score = int(score_k)
            merged[score]["count"] += int(v.get("count", 0))
            merged[score]["total_tricks"] += float(v.get("total_tricks", 0.0))
    for score, v in merged.items():
        v["avg_tricks"] = v["total_tricks"] / v["count"] if v["count"] else 0.0
    return dict(merged)


def _merge_feature_buckets(feature_buckets_list):
    """
    Merge feature buckets across scenarios:
      feature -> value -> {count,total_tricks,avg_tricks}
    """
    merged = defaultdict(lambda: defaultdict(lambda: {"count": 0, "total_tricks": 0.0}))
    for fb in feature_buckets_list:
        for fname, by_val in fb.items():
            for val_k, v in by_val.items():
                val = int(val_k)
                merged[fname][val]["count"] += int(v.get("count", 0))
                merged[fname][val]["total_tricks"] += float(v.get("total_tricks", 0.0))
    # finalize avg_tricks
    out = {}
    for fname, by_val in merged.items():
        out[fname] = {}
        for val, stats in by_val.items():
            c = stats["count"]
            out[fname][val] = {
                "count": c,
                "total_tricks": stats["total_tricks"],
                "avg_tricks": stats["total_tricks"] / c if c else 0.0,
            }
    return out


def _pick_top_features(feature_buckets, k=2):
    """
    Pick K features worth plotting, using a simple heuristic:
    - prefer features with multiple values and decent sample size
    - prefer larger swing in avg_tricks across values
    """
    scored = []
    for fname, by_val in feature_buckets.items():
        if len(by_val) < 3:
            continue
        # compute swing + total count
        vals = sorted(by_val.keys())
        avgs = [by_val[v]["avg_tricks"] for v in vals]
        counts = [by_val[v]["count"] for v in vals]
        total = sum(counts)
        swing = (max(avgs) - min(avgs)) if avgs else 0.0
        # ignore tiny totals
        if total < 200:
            continue
        scored.append((swing, total, fname))
    scored.sort(reverse=True)
    return [t[2] for t in scored[:k]]


# ------------------------
# report generation
# ------------------------

def write_summary_txt(results, suit_results, other_results, suit_dist_agg, other_dist_agg, out_path):
    lines = []
    lines.append("PHASE 1.5 — GREEDY BASELINE SUMMARY")
    lines.append("=" * 40)
    lines.append("")
    lines.append(f"Input files ({len(results)}):")
    for r in results:
        lines.append(f"  - {scenario_label(r):8s}  hands={r.get('hands')}  avg_team0={r.get('avg_team0'):.3f}  avg_team1={r.get('avg_team1'):.3f}  file={r.get('_path')}")
    lines.append("")

    # Suit symmetry check
    if suit_results:
        suits = [r.get("trump_suit") for r in suit_results]
        means = [float(r.get("avg_team0", 0.0)) for r in suit_results]
        if means:
            rng = max(means) - min(means)
            lines.append("Suit symmetry check (Team0 mean tricks):")
            for s, m in sorted(zip(suits, means)):
                lines.append(f"  trump={s}: mean_team0={m:.4f}")
            lines.append(f"  range(max-min) = {rng:.4f}")
            lines.append("  (Small range is good; large range suggests a rules/implementation asymmetry.)")
            lines.append("")

    # Aggregate distributions
    if suit_results:
        lines.append("Aggregate suit-contract trick distribution (Team0):")
        lines.append(f"  mean tricks (from distribution) = {_dist_mean(suit_dist_agg):.4f}")
        lines.append("  counts: " + " ".join([f"{k}:{suit_dist_agg[k]}" for k in range(11)]))
        lines.append("")
    if other_results:
        lines.append("Aggregate non-suit (high/low) trick distribution (Team0):")
        lines.append(f"  mean tricks (from distribution) = {_dist_mean(other_dist_agg):.4f}")
        lines.append("  counts: " + " ".join([f"{k}:{other_dist_agg[k]}" for k in range(11)]))
        lines.append("")

    # Red flags / notes
    lines.append("Notes / quick interpretation prompts:")
    lines.append("- If suit means differ materially across C/D/H/S: inspect bower color mapping + effective-suit + tie-breaking.")
    lines.append("- If distributions look wildly different by suit: inspect trick_winner logic and legality enforcement.")
    lines.append("- If score calibration is non-monotonic/noisy: your hand scoring heuristic is miscalibrated under greedy play.")
    lines.append("")

    with open(out_path, "w") as f:
        f.write("\n".join(lines))


def main():
    ensure_outdir()
    results = load_results()

    suit_results = [r for r in results if r.get("contract_type") == "suit" and r.get("trump_suit")]
    other_results = [r for r in results if r.get("contract_type") != "suit"]

    # Aggregate distributions
    suit_dist_agg = _merge_dist([_get_dist_team0(r) for r in suit_results]) if suit_results else None
    other_dist_agg = _merge_dist([_get_dist_team0(r) for r in other_results]) if other_results else None

    # Aggregate score + feature buckets for suit contracts (the main baseline)
    suit_score_buckets = _merge_score_buckets([r.get("score_buckets_player0", {}) for r in suit_results]) if suit_results else {}
    suit_feature_buckets = _merge_feature_buckets([r.get("feature_buckets_player0", {}) for r in suit_results]) if suit_results else {}

    top_features = _pick_top_features(suit_feature_buckets, k=2)

    # ------------------------
    # Single report image (multi-panel)
    # ------------------------
    fig = plt.figure(figsize=(14, 10))

    # Panel 1: Cross-suit means (symmetry check)
    ax1 = fig.add_subplot(2, 2, 1)
    if len(suit_results) >= 2:
        suits = [r["trump_suit"] for r in suit_results]
        means = [r["avg_team0"] for r in suit_results]
        ax1.bar(suits, means)
        ax1.set_title("Suit symmetry: mean Team0 tricks by trump")
        ax1.set_xlabel("Trump suit")
        ax1.set_ylabel("Mean Team0 tricks")
    else:
        ax1.text(0.5, 0.5, "No multiple suit scenarios found", ha="center", va="center")
        ax1.axis("off")

    # Panel 2: Aggregate trick distribution (suit)
    ax2 = fig.add_subplot(2, 2, 2)
    if suit_dist_agg:
        xs = list(range(11))
        ys = [suit_dist_agg[k] for k in xs]
        ax2.bar(xs, ys)
        ax2.set_title(f"Suit contracts: Team0 trick distribution (agg)\nmean={_dist_mean(suit_dist_agg):.3f}")
        ax2.set_xlabel("Team0 tricks")
        ax2.set_ylabel("Count")
    else:
        ax2.text(0.5, 0.5, "No suit-contract results found", ha="center", va="center")
        ax2.axis("off")

    # Panel 3: Score calibration (agg suit)
    ax3 = fig.add_subplot(2, 2, 3)
    if suit_score_buckets:
        items = sorted([(int(k), v["avg_tricks"], v["count"]) for k, v in suit_score_buckets.items()], key=lambda t: t[0])
        scores = [t[0] for t in items]
        avg_tricks = [t[1] for t in items]
        ax3.plot(scores, avg_tricks, marker="o")
        ax3.set_title("Suit contracts: score calibration (P0 score → avg Team0 tricks)")
        ax3.set_xlabel("Player0 scalar score")
        ax3.set_ylabel("Avg Team0 tricks")
    else:
        ax3.text(0.5, 0.5, "No score buckets available", ha="center", va="center")
        ax3.axis("off")

    # Panel 4: Feature sensitivity (top 1–2 features, plotted on same axes)
    ax4 = fig.add_subplot(2, 2, 4)
    if suit_feature_buckets and top_features:
        for fname in top_features:
            by_val = suit_feature_buckets[fname]
            vals = sorted(by_val.keys())
            avgs = [by_val[v]["avg_tricks"] for v in vals]
            ax4.plot(vals, avgs, marker="o", label=fname)
        ax4.set_title("Suit contracts: top feature sensitivities (agg)")
        ax4.set_xlabel("Feature value")
        ax4.set_ylabel("Avg Team0 tricks")
        ax4.legend()
    else:
        ax4.text(0.5, 0.5, "No feature buckets available", ha="center", va="center")
        ax4.axis("off")

    fig.suptitle("Phase 1.5 — Greedy Baseline Report (Condensed)", fontsize=14)
    fig.tight_layout(rect=[0, 0, 1, 0.95])

    report_img = os.path.join(OUT_DIR, "phase15_greedy__report.png")
    fig.savefig(report_img, dpi=200)
    plt.close(fig)

    # ------------------------
    # Summary text file
    # ------------------------
    summary_path = os.path.join(OUT_DIR, "phase15_greedy__summary.txt")
    write_summary_txt(
        results=results,
        suit_results=suit_results,
        other_results=other_results,
        suit_dist_agg=suit_dist_agg or {k: 0 for k in range(11)},
        other_dist_agg=other_dist_agg or {k: 0 for k in range(11)},
        out_path=summary_path,
    )

    print(f"Wrote: {report_img}")
    print(f"Wrote: {summary_path}")


if __name__ == "__main__":
    main()
