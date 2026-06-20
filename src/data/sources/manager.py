"""Fund manager data crawler.

Two-step extraction:
  1. fund page (fundf10.eastmoney.com/jjjl_CODE.html) → extract manager IDs
  2. manager page (fund.eastmoney.com/manager/ID.html) → extract details

中国公募基金经理数据, 无官方API, 需解析HTML.
"""
import re
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True)
class ManagerInfo:
    fund_code: str
    name: str
    tenure_days: int
    cumulative_return: str
    fund_count: int


def fetch_manager(code: str) -> ManagerInfo | None:
    """Extract fund manager info for a given fund code.

    Returns ManagerInfo on success, None if data unavailable.
    """
    # Step 1: Extract manager ID from fund page
    manager_id = _extract_manager_id(code)
    if not manager_id:
        return None

    # Step 2: Extract manager details from manager page
    details = _fetch_manager_details(manager_id)
    if not details:
        return None

    name, tenure_days, cum_return, fund_count = details
    return ManagerInfo(
        fund_code=code,
        name=name,
        tenure_days=tenure_days,
        cumulative_return=cum_return,
        fund_count=fund_count,
    )


def _extract_manager_id(code: str) -> str | None:
    """Extract the first manager ID from the fund's manager page."""
    url = f"https://fundf10.eastmoney.com/jjjl_{code}.html"
    req = urllib.request.Request(url)
    req.add_header("Referer", "https://fundf10.eastmoney.com/")
    req.add_header("User-Agent", "Mozilla/5.0")

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8")
    except Exception:
        return None

    # Pattern: href="http://fund.eastmoney.com/manager/30743020.html"
    match = re.search(r'fund\.eastmoney\.com/manager/(\d+)\.html', html)
    return match.group(1) if match else None


def _fetch_manager_details(manager_id: str) -> tuple | None:
    """Extract name, tenure, return, fund count from manager page."""
    url = f"http://fund.eastmoney.com/manager/{manager_id}.html"
    req = urllib.request.Request(url)
    req.add_header("Referer", "https://fund.eastmoney.com/")
    req.add_header("User-Agent", "Mozilla/5.0")

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8")
    except Exception:
        return None

    # Name: <title>梁冰哲 基金经理档案</title>
    name = "未知"
    name_match = re.search(r'<title>([^<]+?)\s*[_ ]{1,3}\s*基金经理', html)
    if name_match:
        name = name_match.group(1).strip()

    # Tenure: search for max days
    tenure_days = 0
    days_match = re.findall(r'(\d+)天', html)
    if days_match:
        tenure_days = max(int(d) for d in days_match)

    # Cumulative return: take the best one (任职回报最高)
    returns = re.findall(r'([+-]?\d+\.\d+%)', html)
    cum_return = "---"
    if returns:
        best = max(returns, key=lambda r: float(r.replace("%", "").replace("+", "")))
        cum_return = best

    # Fund count: count fund codes in the page
    fund_codes = set(re.findall(r'f10/jjjl_(\d{6})\.html', html))
    fund_count = len(fund_codes) if fund_codes else 1

    return (name, tenure_days, cum_return, fund_count)
