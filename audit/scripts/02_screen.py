"""Stage 2: programmatic screening over 100% of questions.

Regex/heuristic features only. These describe answer *surface* shape and evidence
support; they do NOT establish that an item is semantically convertible. That is
the job of stage 3 (item-level review). Output: ledger/screen.parquet (local).
"""
import re, sys, json
import polars as pl
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from common import LEDGER, REPORT, questions, emails

MONTHS = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"
RE = {
    "date_textual": re.compile(rf"\b{MONTHS}\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,?\s+\d{{4}})?\b|\b\d{{1,2}}\s+{MONTHS}\s+\d{{4}}\b", re.I),
    "date_numeric": re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b|\b\d{4}-\d{2}-\d{2}\b"),
    "year_only": re.compile(r"\b(19|20)\d{2}\b"),
    "time": re.compile(r"\b\d{1,2}:\d{2}\s*(?:a\.?m\.?|p\.?m\.?)?\b|\b\d{1,2}\s*(?:am|pm|a\.m\.|p\.m\.)\b", re.I),
    "money": re.compile(r"\$\s?\d[\d,]*(?:\.\d+)?(?:\s*(?:million|billion|thousand|mm|bn|k))?|\b\d[\d,]*(?:\.\d+)?\s*(?:dollars|cents)\b", re.I),
    "percent": re.compile(r"\b\d+(?:\.\d+)?\s*(?:%|percent)"),
    "number": re.compile(r"(?<![\w/:-])\d[\d,]*(?:\.\d+)?(?![\w/:-])"),
    "email_addr": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    "url": re.compile(r"https?://\S+|www\.\S+", re.I),
    "phone": re.compile(r"\(?\b\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}\b"),
    "quote": re.compile(r"[\"“][^\"”]{3,}[\"”]"),
    "yes_no": re.compile(r"^\s*(yes|no)\b[,.]?", re.I),
    "hedge": re.compile(r"\b(not (?:specified|mentioned|provided|stated|explicitly|clear|possible to determine)|cannot be determined|can(?:no|')t (?:be )?determine|unclear|does not (?:specify|mention|state|provide)|no (?:specific )?(?:mention|information|date|time) )", re.I),
    "list_sep": re.compile(r",\s+(?:and\s+)?|;\s+|\band\b"),
    "multi_wh": re.compile(r"\b(what|who|when|where|which|how|why)\b.*\b(and|,)\s+(what|who|when|where|which|how|why|under what|at what|on what)\b", re.I),
    "q_yesno_aux": re.compile(r"^\s*(is|are|was|were|do|does|did|has|have|had|can|could|will|would|should)\b", re.I),
    "q_according": re.compile(r"\baccording to\b", re.I),
    "cap_token": re.compile(r"\b[A-Z][a-zA-Z'&.-]{1,}\b"),
    "anachronism": re.compile(r"\b(20(?:0[3-9]|[1-9]\d))\b"),  # Enron corpus ends 2002
}

def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower()).strip()

def q_type(q: str) -> str:
    ql = q.strip().lower()
    for pref in ("according to", "in ", "on ", "at ", "by ", "under ", "to ", "for ", "based on", "as per", "from "):
        if ql.startswith(pref):
            # skip the leading clause up to the first comma
            i = ql.find(",")
            if 0 < i < 200:
                ql = ql[i + 1:].strip()
            break
    m = re.match(r"(what|who|whose|whom|when|where|which|why|how many|how much|how long|how often|how)\b", ql)
    if m:
        return m.group(1)
    if RE["q_yesno_aux"].match(ql):
        return "yes_no_aux"
    return "other"

def longest_common_substring_ratio(a: str, b: str) -> float:
    """Fraction of a's characters covered by its longest substring that also occurs in b (word-boundary greedy)."""
    a_w = a.split(); best = 0
    n = len(a_w)
    for i in range(n):
        lo, hi = best + 1, n - i
        # expand greedily: longest window starting at i present in b
        while lo <= hi:
            mid = (lo + hi) // 2
            if " ".join(a_w[i:i + mid]) in b:
                best = max(best, mid); lo = mid + 1
            else:
                hi = mid - 1
    return best / n if n else 0.0

def row_features(q, gold, alt, inc, email_norm):
    g = gold or ""; gn = norm(g).rstrip(".")
    an = norm(alt or "").rstrip(".")
    nums_g = set(x.replace(",", "") for x in RE["number"].findall(g))
    nums_email = set(x.replace(",", "") for x in RE["number"].findall(email_norm))
    caps_g = [c for c in RE["cap_token"].findall(g) if c.lower() not in {"the", "a", "an", "according", "yes", "no"}]
    caps_found = sum(1 for c in caps_g if c.lower() in email_norm)
    inc = inc or []
    f = {
        "q_type": q_type(q), "q_words": len(q.split()), "q_according": bool(RE["q_according"].search(q)),
        "q_multi_wh": bool(RE["multi_wh"].search(q)),
        "gold_words": len(g.split()), "gold_chars": len(g),
        "gold_yes_no": bool(RE["yes_no"].match(g)),
        "gold_date_textual": bool(RE["date_textual"].search(g)), "gold_date_numeric": bool(RE["date_numeric"].search(g)),
        "gold_year": bool(RE["year_only"].search(g)), "gold_time": bool(RE["time"].search(g)),
        "gold_money": bool(RE["money"].search(g)), "gold_percent": bool(RE["percent"].search(g)),
        "gold_number_count": len(nums_g), "gold_email_addr": bool(RE["email_addr"].search(g)),
        "gold_url": bool(RE["url"].search(g)), "gold_phone": bool(RE["phone"].search(g)),
        "gold_quote": bool(RE["quote"].search(g)), "gold_hedge": bool(RE["hedge"].search(g)),
        "gold_list_seps": len(RE["list_sep"].findall(g)),
        "gold_verbatim_in_email": gn in email_norm,
        "gold_lcs_ratio": round(longest_common_substring_ratio(gn, email_norm), 3),
        "gold_numbers_all_in_email": bool(nums_g) and nums_g <= nums_email,
        "gold_numbers_missing_from_email": len(nums_g - nums_email),
        "gold_caps_in_email_ratio": round(caps_found / len(caps_g), 3) if caps_g else None,
        "alt_verbatim_in_email": an in email_norm,
        "alt_equals_gold": gn == an,
        "alt_shares_numbers": (set(x.replace(",", "") for x in RE["number"].findall(alt or "")) == nums_g),
        "inc_count": len(inc),
        "inc_hedge_any": any(RE["hedge"].search(x or "") for x in inc),
        "inc_anachronism_any": any(RE["anachronism"].search(x or "") for x in inc) and not RE["anachronism"].search(g),
        "inc_words_mean": round(sum(len((x or "").split()) for x in inc) / len(inc), 1) if inc else None,
        "inc_any_in_email_lcs_gt_half": any(longest_common_substring_ratio(norm(x).rstrip("."), email_norm) > 0.5 for x in inc),
        "inc_shares_gold_numbers_any": any(nums_g and nums_g <= set(y.replace(",", "") for y in RE["number"].findall(x or "")) for x in inc),
    }
    return f

def main():
    q = questions()
    em = emails().select("path", "email")
    em_map = dict(zip(em["path"].to_list(), (norm(e) for e in em["email"].to_list())))
    print("emails normalized", len(em_map), file=sys.stderr)
    out = []
    for i, r in enumerate(q.select("qid", "path", "question", "gold", "alternates", "incorrects").iter_rows()):
        qid, path, question, gold, alts, incs = r
        f = row_features(question, gold, (alts or [None])[0], incs, em_map[path])
        f["qid"] = qid
        out.append(f)
        if i % 50000 == 0:
            print(i, file=sys.stderr)
    df = pl.DataFrame(out)
    df.write_parquet(LEDGER / "screen.parquet")
    print("wrote", df.height, "rows", file=sys.stderr)

if __name__ == "__main__":
    main()
