"""Full-market fund pool — fetches and merges akshare bulk APIs.

Uses two pre-computed data sources:
  fund_open_fund_rank_em  → 19,747 funds with 1w~3y returns
  fund_rating_all         → 17,533 funds with manager/ratings

Provides a merged DataFrame ready for bulk screening.
"""
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class PoolFund:
    """A fund from the bulk market pool — all fields from pre-computed APIs."""

    code: str
    name: str
    fund_type: str  # from 济安金信 classification
    raw_type: str   # original akshare type (e.g. "债券型-长债", "混合型-灵活")
    manager: str
    fee: Decimal
    # Pre-computed returns (percentage points, e.g. 15.5 means +15.5%)
    ret_1m: float
    ret_3m: float
    ret_6m: float
    ret_1y: float
    ret_3y: float
    # Ratings (0-5, 0 = unrated)
    rating_morningstar: float
    rating_shanghai: float
    rating_zhaoshang: float
    rating_jiAn: float


def fetch_fund_pool(
    min_ret_1y: float = -50.0,
    allowed_types: set[str] | None = None,
    skip_filters: bool = False,
) -> list[PoolFund]:
    """Fetch and merge the full Chinese mutual fund pool.

    Args:
        min_ret_1y: Minimum 1-year return (filters out extreme losers).
        allowed_types: Fund types to include. None = all.
        skip_filters: If True, skip ALL filtering (duplicate shares, equity-only
                      index, min_ret_1y, allowed_types). Returns every fund in
                      the rank endpoint. Use for "大而全" complete dataset.

    Returns:
        List of PoolFund objects sorted by 1y return descending.
    """
    import akshare as ak

    # ── Fetch fund rankings (returns + basic info) ──────────────────
    df_rank = ak.fund_open_fund_rank_em(symbol="全部")
    if df_rank is None or df_rank.empty:
        raise RuntimeError("fund_open_fund_rank_em returned empty data")

    # ── Fetch fund ratings (manager + type + agency ratings) ────────
    df_rating = ak.fund_rating_all()
    if df_rating is None or df_rating.empty:
        raise RuntimeError("fund_rating_all returned empty data")

    # ── Merge on fund code ──────────────────────────────────────────
    df = df_rank.merge(
        df_rating,
        left_on="基金代码",
        right_on="代码",
        how="left",
        suffixes=("_rank", "_rating"),
    )

    # ── Build PoolFund list ─────────────────────────────────────────
    all_names: set[str] = set(str(n) for n in df["基金简称"])
    funds: list[PoolFund] = []
    for _, row in df.iterrows():
        try:
            code = str(row["基金代码"]).zfill(6)
            name = str(row.get("基金简称", code))
            fund_type = _classify_type(str(row.get("类型", "混合型-灵活")))
            raw_type = str(row.get("类型", "混合型-灵活"))
            # Handle pandas NaN → string "nan" (6,425 funds have this)
            if raw_type in ("nan", "None", ""):
                raw_type = "混合型-灵活"
            manager = str(row.get("基金经理", "未知"))
            fee_str = str(row.get("手续费", "0.015")).replace("%", "")
            fee = Decimal(fee_str) / Decimal("100") if fee_str else Decimal("0.015")

            ret_1y = _safe_float(row.get("近1年", 0))

            if not skip_filters:
                if ret_1y < min_ret_1y:
                    continue
                if allowed_types and fund_type not in allowed_types:
                    continue
                # Skip C/E/D/B share classes only when A/base equivalent exists
                if _is_duplicate_share(name, all_names):
                    continue
                # For index funds, only keep equity indexes
                if fund_type == "index" and not _is_equity_index(name):
                    continue

            funds.append(PoolFund(
                code=code,
                name=name,
                fund_type=fund_type,
                raw_type=raw_type,
                manager=manager,
                fee=fee,
                ret_1m=_safe_float(row.get("近1月", 0)),
                ret_3m=_safe_float(row.get("近3月", 0)),
                ret_6m=_safe_float(row.get("近6月", 0)),
                ret_1y=ret_1y,
                ret_3y=_safe_float(row.get("近3年", 0)),
                rating_morningstar=_safe_float(row.get("晨星评级", 0)),
                rating_shanghai=_safe_float(row.get("上海证券", 0)),
                rating_zhaoshang=_safe_float(row.get("招商证券", 0)),
                rating_jiAn=_safe_float(row.get("济安金信", 0)),
            ))
        except (ValueError, KeyError):
            continue

    return funds


def _safe_float(val) -> float:
    """Convert value to float, defaulting to 0 on failure."""
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


def _classify_type(raw: str) -> str:
    """Map akshare fund type strings to fortress classification."""
    raw = raw.strip()
    if "货币" in raw:
        return "money"
    if "债券" in raw:
        return "bond"
    if "混合" in raw:
        return "mixed"
    if "指数型-股票" in raw or "指数型-国际" in raw:
        return "index"  # equity index
    if "指数" in raw or "ETF" in raw:
        # Bond index → classify as bond
        if "债" in raw:
            return "bond"
        return "index"
    if "股票" in raw:
        return "stock"
    return "mixed"


def _is_equity_index(name: str) -> bool:
    """Check if an index fund tracks equity (沪深300, 中证500 etc)."""
    name = name.lower()
    bond_keywords = ["债", "国债", "信用债", "利率债", "政金债", "金融债", "可转债"]
    if any(k in name for k in bond_keywords):
        return False
    equity_keywords = ["沪深300", "中证500", "中证1000", "创业板", "科创板",
                       "上证50", "深证", "恒生", "标普", "纳斯达克", "300",
                       "500", "红利", "行业", "医药", "消费", "科技", "新能源"]
    return any(k in name for k in equity_keywords)


def _is_duplicate_share(name: str, all_names: set[str] | None = None) -> bool:
    """Check if a fund is a duplicate share class (C/E/D/B vs A).

    Only returns True when an A-class or base equivalent exists in all_names.
    If all_names is None, falls back to simple suffix check (legacy behavior).
    """
    if name.endswith("类C"):
        base = name[:-2]
        a_equiv = base + "类A"
    elif name.endswith("C"):
        base = name[:-1]
        a_equiv = base + "A"
    elif name.endswith("D"):
        base = name[:-1]
        a_equiv = base + "A"
    elif name.endswith("E"):
        base = name[:-1]
        a_equiv = base + "A"
    elif name.endswith("B"):
        base = name[:-1]
        a_equiv = base + "A"
    else:
        return False

    if all_names is not None:
        # Only skip if an A-class or base equivalent exists
        return base in all_names or a_equiv in all_names

    return True  # legacy: always skip C/D/E/B


