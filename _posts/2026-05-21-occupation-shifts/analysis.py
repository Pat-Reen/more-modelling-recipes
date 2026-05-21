"""
Occupation shifts: 1966 Australian census vs 2026 Jobs and Skills Australia.

Reads:
  - "1966 Census - Volume 1 Population - Single Characteristics - Part 10 Occupation.pdf"
    ABS, Commonwealth Bureau of Census and Statistics, December 1970.
    Source: https://www.abs.gov.au/AUSSTATS/abs@.nsf/DetailsPage/2106.01966
    Table 1, Total Australia section (pages 87-112), Persons (P) row, "Australian
    Australia" rightmost column.
  - "Occupation profiles data - February 2026.xlsx"
    Jobs and Skills Australia, Feb 2026 release.
    Source: https://www.jobsandskills.gov.au/data/occupation-and-industry-profiles/occupations
    Table_1 "Overview" sheet, "Employed" column for each ANZSCO Unit Group (4-digit).

Outputs:
  - shifts.csv: per-occupation 1966 vs 2026 counts and workforce shares
  - chart_disappeared.png: log-scale ratio plot for the "fully disappeared" group
  - chart_shrunk.png: share-of-workforce dumbbell plot for shrunk and grown roles
  - workforce_totals.txt: the denominators with their source citations
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

import fitz  # pymupdf
import openpyxl
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

HERE = Path(__file__).parent
PDF_1966 = HERE / "1966 Census - Volume 1 Population - Single Characteristics - Part 10 Occupation.pdf"
XLSX_2026 = HERE / "Occupation profiles data - February 2026.xlsx"


# --------------------------------------------------------------------------
# 1966 extraction
# --------------------------------------------------------------------------
def extract_1966_workforce_total() -> tuple[int, int]:
    """Return (page_number, total_in_work_force_persons) from Table 1."""
    doc = fitz.open(str(PDF_1966))
    try:
        # Page 112 (index 111) is the final page of Table 1 Total Australia.
        text = doc[111].get_text()
    finally:
        doc.close()
    m = re.search(
        r"Total in the work force.*?P\s+[\d,]+\s+[\d,]+\s+[\d,]+\s+[\d,]+\s+[\d,]+\s+[\d,]+\s+[\d,]+\s+([\d,]+\s*[\d,]+)",
        text,
        re.DOTALL,
    )
    if not m:
        raise RuntimeError("Could not locate 'Total in the work force' P row on page 112")
    # The final two number-like tokens are " 43,916 4,856,455" (ACT then Australia)
    last = m.group(1).strip().split()
    aus = int(last[-1].replace(",", ""))
    return 112, aus


# 1966 hand-picked occupations.
# Each entry is verified against the PDF text on the cited page.
# count_1966 = "P" (Persons) row, "Australia" column from Table 1 Total Australia.
OCCUPATIONS_1966 = [
    # (name_1966, count_1966, pdf_page, theme)
    ("Telegraphists",                                     1098,   99, "disappeared"),
    ("Teleprinter operators",                              965,   99, "disappeared"),
    ("Telephonists, phonogram operators",               23545,   99, "shrunk"),
    ("Stenographers and typists",                      162806,   92, "shrunk"),
    ("Office machine operators",                        39493,   92, "absorbed"),
    ("Receptionists",                                   14973,   92, "grown"),
    ("Tailors and dressmakers",                         10922,  100, "shrunk"),
    ("Milliners and hat makers",                         1753,  100, "disappeared"),
    ("Bookbinders",                                      7307,  106, "shrunk"),
    ("Compositors and typesetters",                      9296,  106, "disappeared"),
    ("Blacksmiths, hammersmiths and forgemen",           3361,  101, "shrunk"),
    ("Boot and shoe factory operatives",                16602,  101, "shrunk"),
    ("Tanners, fellmongers and related",                 2931,  108, "shrunk"),
    ("Whalers",                                            36,   95, "disappeared"),
    ("Pearlers, pearl divers, pearl shellers",            395,   95, "disappeared"),
    ("Shearers",                                         6806,   95, "shrunk"),
    ("Wool classers",                                    2406,   95, "shrunk"),
    ("Firemen, railway (steam)",                         5508,   98, "disappeared"),
    ("Postmen, postal assistants, telegram deliverymen",21882,   99, "shrunk"),
    ("Domestic workers, private households",            27310,  111, "shrunk"),
    ("Service station attendants",                      10265,   93, "stable"),
    ("Maids, hotel, hospital",                          31683,  111, "shrunk"),
    ("Cooks and chefs",                                 22487,  111, "grown"),
    ("Accountants, auditors",                           18362,   90, "grown"),
    ("Economists, actuaries and statisticians",          1608,   90, "grown"),
    ("Computer programmers",                             2561,   90, "grown"),
    ("Medical practitioners",                           13697,   88, "grown"),
    ("Pharmacists",                                      8374,   88, "grown"),
]


# --------------------------------------------------------------------------
# 2026 lookup (Jobs and Skills Australia, Feb 2026)
# --------------------------------------------------------------------------
def load_2026_employed() -> dict[int, tuple[str, int]]:
    """Return {anzsco_code: (occupation_name, employed_count)} for every row."""
    wb = openpyxl.load_workbook(str(XLSX_2026), read_only=True, data_only=True)
    ws = wb["Table_1"]
    out: dict[int, tuple[str, int]] = {}
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i < 7:
            continue
        code, occ, emp = row[0], row[1], row[2]
        if not isinstance(code, int) or not isinstance(emp, (int, float)):
            continue
        out[code] = (str(occ), int(emp))
    wb.close()
    return out


def workforce_total_2026(emp: dict[int, tuple[str, int]]) -> int:
    """Sum the 4-digit ANZSCO Unit Groups (ignores 6-digit subdivisions to avoid double-count)."""
    return sum(v[1] for k, v in emp.items() if len(str(k)) == 4)


# 2026 ANZSCO crosswalk.
# Each maps a 1966 occupation line to one or more 2026 ANZSCO codes (4- or 6-digit).
# "[]" means no current ANZSCO occupation captures the named role.
CROSSWALK_2026 = {
    "Telegraphists":                                    [],
    "Teleprinter operators":                            [],
    "Telephonists, phonogram operators":                [5616],            # Switchboard Operators
    "Stenographers and typists":                        [532113],          # Typists (6-digit; no Stenographer unit group)
    "Office machine operators":                         [],                # absorbed into general clerical
    "Receptionists":                                    [5421],            # Receptionists
    "Tailors and dressmakers":                          [393213],          # combined 1966 lines; 393213 covers both
    "Milliners and hat makers":                         [],
    "Bookbinders":                                      [],                # no ANZSCO unit; trade absorbed into Print Finishers
    "Compositors and typesetters":                      [],                # disappeared with hot-metal typesetting
    "Blacksmiths, hammersmiths and forgemen":           [322111],          # Blacksmiths
    "Boot and shoe factory operatives":                 [393114],          # Shoemakers
    "Tanners, fellmongers and related":                 [],
    "Whalers":                                          [],
    "Pearlers, pearl divers, pearl shellers":           [],
    "Shearers":                                         [3612],
    "Wool classers":                                    [399917],
    "Firemen, railway (steam)":                         [],
    "Postmen, postal assistants, telegram deliverymen": [561212, 561412],  # Postal Delivery + Sorting Officers
    "Domestic workers, private households":             [811412],          # Domestic Housekeepers
    "Service station attendants":                       [6216],
    "Maids, hotel, hospital":                           [811411],          # Commercial Housekeepers
    "Cooks and chefs":                                  [3513, 3514],      # Chefs + Cooks
    "Accountants, auditors":                            [2211, 2212],      # Accountants + Auditors, Company Secretaries and Corporate Treasurers
    "Economists, actuaries and statisticians":          [2241, 2243],      # Actuaries/Mathematicians/Statisticians + Economists
    "Computer programmers":                             [2613],            # Software and Applications Programmers
    "Medical practitioners":                            [2531, 2532, 2533, 2534, 2535, 2539],  # GPs, Anaesthetists, Specialist Physicians, Psychiatrists, Surgeons, Other Medical Practitioners
    "Pharmacists":                                      [2515],
}


# --------------------------------------------------------------------------
# Broader workforce composition: 1966 majors mapped to 2026 ANZSCO majors,
# made exhaustive and mutually exclusive so each side sums to 100%.
#
# Carve-out logic so neither column double-counts:
#
#   "Professionals and managers" (ANZSCO 1+2) excludes:
#     - farm managers 1211-1214 (moved to "Farmers and primary industry")
#     - Defence Force codes 1392, 111212, 139111 (moved to "Defence Force")
#
#   "Service workers" (ANZSCO 4) excludes:
#     - Defence Force Members - Other Ranks 4411 (moved to "Defence Force")
#
#   "Trades, machinery, labourers" (ANZSCO 3+7+8) excludes:
#     - farm workers 8411-8419 (moved to "Farmers and primary industry")
#
# Special rows:
#
#   "Defence Force" combines all four ANZSCO Defence Force codes (1392 +
#   4411 + 111212 + 139111) on the 2026 side, against 1966 Group 10 (Armed
#   Services) on the 1966 side.
#
#   "Other (1966 only)" holds 1966 Group 11 "Occupation inadequately
#   described or not stated". ANZSCO has no analogue because every employed
#   person is classified to an occupation, so the 2026 figure is left at 0.
#
# Result: both columns sum to 100.0%.
# --------------------------------------------------------------------------
COMPOSITION_BUCKETS = [
    # (bucket_name, 1966_count, 1966_components_with_pages, 2026_anzsco_spec, 2026_count_override)
    (
        "Professionals and managers",
        755214,
        "Group 0 (Total professional, technical and related workers, p.90, 450,575) + "
        "Group 1 (Total administrative, executive and managerial workers, p.92, 304,639)",
        "ANZSCO 1+2 (Managers + Professionals), less farm managers 1211-1214 and Defence Force codes 1392, 111212, 139111",
        None,
    ),
    (
        "Clerical and sales",
        1089015,
        "Group 2 (Total clerical workers, p.93, 713,548) + "
        "Group 3 (Total sales workers, p.93, 375,467)",
        "ANZSCO 5+6 (Clerical and Administrative + Sales)",
        None,
    ),
    (
        "Service workers",
        360978,
        "Group 9 (Total service, sport, and recreation workers, p.112)",
        "ANZSCO 4 (Community and Personal Service), less Defence Force Members 4411",
        None,
    ),
    (
        "Trades, machinery, labourers",
        2049311,
        "Group 5 (Total miners, quarrymen, p.97, 31,864) + "
        "Group 6 (Total workers in transport and communication, p.99, 294,109) + "
        "Group 7/8 (Total craftsmen, production-process workers and labourers, p.110, 1,723,338)",
        "ANZSCO 3+7+8 (Tech and Trades + Machinery Operators + Labourers), less farm workers 8411-8419",
        None,
    ),
    (
        "Farmers and primary industry",
        469051,
        "Group 4 (Total farmers, fishermen, hunters, timber getters, p.96)",
        "ANZSCO 1211-1214 (Farmers) + 8411-8419 (Farm/Forestry/Garden Workers)",
        None,
    ),
    (
        "Defence Force",
        57293,
        "Group 10 (Members of Armed Services, p.112)",
        "ANZSCO 1392 (Senior NCO Defence Officers) + 4411 (Other Ranks) + 111212 (Senior Officers) + 139111 (Commissioned Officers)",
        None,
    ),
    (
        "Other (1966 only)",
        75593,
        "Group 11 (Occupation inadequately described or not stated, p.112)",
        "No 2026 equivalent: every employed person in ANZSCO is classified",
        0,
    ),
]


# 6-digit Defence Force codes that sit inside 4-digit Unit Groups in the
# Managers major (so we need to subtract them when carving Defence Force
# out of the Professionals+Managers bucket).
_DEFENCE_6DIGIT_IN_MGR = (111212, 139111)
# 4-digit Defence Force Unit Groups (each sits entirely inside one major).
_DEFENCE_4DIGIT_IN_MGR = (1392,)
_DEFENCE_4DIGIT_IN_SERVICE = (4411,)


def _compute_2026_composition(emp: dict[int, tuple[str, int]]) -> dict[str, int]:
    """Sum 4-digit Unit Group employment into the bucket structure above."""
    farm_mgr = sum(v[1] for k, v in emp.items() if len(str(k)) == 4 and 1211 <= k <= 1214)
    farm_wkr = sum(v[1] for k, v in emp.items() if len(str(k)) == 4 and 8411 <= k <= 8419)
    def_mgr_4 = sum(emp[c][1] for c in _DEFENCE_4DIGIT_IN_MGR if c in emp)
    def_mgr_6 = sum(emp[c][1] for c in _DEFENCE_6DIGIT_IN_MGR if c in emp)
    def_svc_4 = sum(emp[c][1] for c in _DEFENCE_4DIGIT_IN_SERVICE if c in emp)

    by_major: dict[str, int] = {}
    for k, (_, e) in emp.items():
        if len(str(k)) == 4:
            d = str(k)[0]
            by_major[d] = by_major.get(d, 0) + e

    return {
        "Professionals and managers": by_major.get("1", 0) + by_major.get("2", 0) - farm_mgr - def_mgr_4 - def_mgr_6,
        "Clerical and sales":          by_major.get("5", 0) + by_major.get("6", 0),
        "Service workers":             by_major.get("4", 0) - def_svc_4,
        "Trades, machinery, labourers": by_major.get("3", 0) + by_major.get("7", 0) + by_major.get("8", 0) - farm_wkr,
        "Farmers and primary industry": farm_mgr + farm_wkr,
        "Defence Force":               def_mgr_4 + def_mgr_6 + def_svc_4,
        "Other (1966 only)":           0,
    }


def main() -> None:
    page_total, wf1966 = extract_1966_workforce_total()
    emp_2026 = load_2026_employed()
    wf2026 = workforce_total_2026(emp_2026)

    (HERE / "workforce_totals.txt").write_text(
        f"1966 Total in work force (Persons, Australia): {wf1966:,}\n"
        f"  Source: ABS Census 1966, Vol. 1 Part 10 Occupation, Table 1, p.{page_total}.\n"
        f"\n"
        f"2026 Total employed (sum of 4-digit ANZSCO Unit Groups, Feb 2026): {wf2026:,}\n"
        f"  Source: Jobs and Skills Australia, Occupation profiles data Feb 2026, Table_1.\n",
        encoding="utf-8",
    )

    rows = []
    for name, count_1966, page, theme in OCCUPATIONS_1966:
        codes = CROSSWALK_2026[name]
        count_2026 = sum(emp_2026[c][1] for c in codes if c in emp_2026)
        share_1966 = count_1966 / wf1966
        share_2026 = count_2026 / wf2026 if count_2026 else 0.0
        ratio = (share_2026 / share_1966) if share_1966 else 0.0
        rows.append({
            "occupation_1966": name,
            "count_1966": count_1966,
            "pdf_page": page,
            "share_1966_pct": round(share_1966 * 100, 4),
            "anzsco_2026": ";".join(str(c) for c in codes) or "none",
            "count_2026": count_2026,
            "share_2026_pct": round(share_2026 * 100, 4),
            "share_ratio_2026_to_1966": round(ratio, 3),
            "theme": theme,
        })

    out_csv = HERE / "shifts.csv"
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # Composition CSV (broader workforce buckets, made to total 100%)
    comp_2026 = _compute_2026_composition(emp_2026)
    comp_rows = []
    for name, c1966, src_1966, src_2026, c2026_override in COMPOSITION_BUCKETS:
        c2026 = c2026_override if c2026_override is not None else comp_2026[name]
        s1966 = c1966 / wf1966
        s2026 = c2026 / wf2026 if c2026 else 0.0
        ratio = (s2026 / s1966) if s1966 and s2026 else (0.0 if not s2026 else None)
        comp_rows.append({
            "bucket": name,
            "count_1966": c1966,
            "share_1966_pct": round(s1966 * 100, 2),
            "source_1966": src_1966,
            "count_2026": c2026,
            "share_2026_pct": round(s2026 * 100, 2),
            "source_2026": src_2026,
            "share_ratio_2026_to_1966": round(ratio, 2) if ratio is not None else "n/a",
        })

    comp_csv = HERE / "composition.csv"
    with comp_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(comp_rows[0].keys()))
        w.writeheader()
        w.writerows(comp_rows)

    _chart_dumbbell(rows)
    _chart_ratio(rows)

    print(f"Wrote {out_csv}")
    print(f"Wrote {comp_csv}")
    print()
    print(f"Composition table (totals must sum to 100%):")
    print(f"{'Bucket':<35} {'1966 %':>8} {'2026 %':>8} {'ratio':>6}")
    total_1966 = total_2026 = 0
    for r in comp_rows:
        ratio_s = f"{r['share_ratio_2026_to_1966']:.2f}x" if isinstance(r['share_ratio_2026_to_1966'], float) else str(r['share_ratio_2026_to_1966'])
        print(f"{r['bucket']:<35} {r['share_1966_pct']:>7.2f}% {r['share_2026_pct']:>7.2f}% {ratio_s:>6}")
        total_1966 += r['share_1966_pct']
        total_2026 += r['share_2026_pct']
    print(f"{'TOTAL':<35} {total_1966:>7.2f}% {total_2026:>7.2f}%")
    print(f"1966 workforce: {wf1966:,}    2026 workforce: {wf2026:,}    growth: {wf2026/wf1966:.2f}x")
    print()
    print(f"{'1966 occupation':<55} {'1966 share %':>13} {'2026 share %':>13} {'ratio':>8}")
    for r in rows:
        print(f"{r['occupation_1966']:<55} {r['share_1966_pct']:>13.4f} {r['share_2026_pct']:>13.4f} {r['share_ratio_2026_to_1966']:>8.2f}")


def _chart_dumbbell(rows: list[dict]) -> None:
    """Dumbbell: 1966 share vs 2026 share for each occupation."""
    ordered = sorted(rows, key=lambda r: r["share_1966_pct"], reverse=True)
    labels = [r["occupation_1966"] for r in ordered]
    s1966 = [r["share_1966_pct"] for r in ordered]
    s2026 = [r["share_2026_pct"] for r in ordered]

    fig, ax = plt.subplots(figsize=(9, 11))
    y = range(len(labels))
    for i, (a, b) in enumerate(zip(s1966, s2026)):
        color = "#9ca3af" if b >= a else "#b91c1c"
        ax.plot([a, b], [i, i], color=color, lw=2, zorder=1)
    ax.scatter(s1966, list(y), color="#1f2937", s=42, zorder=3, label="1966 share")
    ax.scatter(s2026, list(y), color="#d97706", s=42, zorder=3, label="2026 share")

    ax.set_yticks(list(y))
    ax.set_yticklabels(labels, fontsize=9)
    ax.invert_yaxis()
    ax.set_xscale("symlog", linthresh=0.001)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:g}%"))
    ax.set_xlabel("Share of total workforce  (log scale, % of persons)")
    ax.set_title(
        "Share of the Australian workforce, 1966 vs Feb 2026",
        loc="left", fontsize=12, fontweight="bold",
    )
    ax.grid(axis="x", color="#e5e7eb", lw=0.5)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(loc="lower right", frameon=False)

    fig.text(
        0.01, 0.005,
        "1966: ABS Census Vol.1 Pt.10 Occupation, Table 1, Total Australia.   "
        "2026: Jobs and Skills Australia, Occupation profiles (Feb 2026).",
        fontsize=7, color="#6b7280",
    )
    fig.tight_layout()
    fig.savefig(HERE / "chart_shrunk.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


def _chart_ratio(rows: list[dict]) -> None:
    """Horizontal bar of share-ratio (2026 share / 1966 share).

    Zero-ratio rows (no 2026 ANZSCO equivalent) are drawn with no bar and
    a "no 2026 equivalent" text marker at the left edge, to keep them
    visually distinct from rows that merely shrank to a small ratio.
    """
    ordered = sorted(rows, key=lambda r: r["share_ratio_2026_to_1966"])
    labels = [r["occupation_1966"] for r in ordered]
    ratios = [r["share_ratio_2026_to_1966"] for r in ordered]

    fig, ax = plt.subplots(figsize=(9, 11))

    # Only plot bars for non-zero ratios. Zero rows get a text marker only.
    bar_widths = [r if r > 0 else 0 for r in ratios]
    colors = ["#b91c1c" if 0 < r < 1 else ("#15803d" if r >= 1 else "#9ca3af") for r in ratios]
    bars = ax.barh(labels, bar_widths, color=colors, edgecolor="none")
    ax.axvline(1.0, color="#374151", lw=0.8, ls="--")
    ax.set_xscale("log")
    ax.set_xlim(left=0.005, right=60)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(
        lambda x, _: f"{x:g}x" if x >= 1 else f"{x:.2g}x"
    ))
    ax.set_xlabel("2026 workforce share / 1966 workforce share  (log scale)")
    ax.set_title(
        "Has each 1966 occupation grown or shrunk as a share of work?",
        loc="left", fontsize=12, fontweight="bold",
    )
    ax.grid(axis="x", color="#e5e7eb", lw=0.5)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    for bar, r in zip(bars, ratios):
        if r == 0:
            ax.text(
                0.006, bar.get_y() + bar.get_height() / 2,
                "no 2026 ANZSCO equivalent",
                va="center", fontsize=8, color="#6b7280", style="italic",
            )
        else:
            label = f"{r:.2f}x" if r >= 0.01 else f"{r:.3f}x"
            ax.text(
                r * 1.05, bar.get_y() + bar.get_height() / 2,
                label, va="center", fontsize=8, color="#374151",
            )

    fig.text(
        0.01, 0.005,
        "Ratio = (2026 employed / 2026 workforce) / (1966 persons in occupation / 1966 work force). "
        "Bars below the dashed 1x line shrank as a share of work; bars above grew.",
        fontsize=7, color="#6b7280",
    )
    fig.tight_layout()
    fig.savefig(HERE / "chart_ratio.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
