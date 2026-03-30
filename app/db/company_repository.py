import re
from datetime import date
from typing import Any, Dict, List, Optional

from app.db.db import get_connection, DB_NAME

_CIN_CLEAN_RE = re.compile(r"[^A-Za-z0-9]")
# _DB_NAME = re.sub(r"[^A-Za-z0-9_]", "", DB_NAME) # type: ignore
_COMPANY_TABLE_FQN = f"company_master_new"


def _clean_cin(cin: str) -> str:
    # CIN values are case-insensitive; normalize to uppercase without spaces.
    return _CIN_CLEAN_RE.sub("", cin).upper()


def _build_boolean_fulltext_query(raw: str) -> str:
    """
    MySQL FULLTEXT BOOLEAN MODE query builder.

    We append '*' to tokens to make prefix matching work better for company names.
    """
    tokens = re.split(r"[^A-Za-z0-9]+", raw or "")
    tokens = [t for t in (tok.strip() for tok in tokens) if t]
    # Avoid producing a useless query for short inputs.
    tokens = [t for t in tokens if len(t) >= 2]
    return " ".join([f"{t}*" for t in tokens]) if tokens else ""


def search_company(
    *,
    cin: Optional[str] = None,
    company_name: Optional[str] = None,
    roc_code: Optional[str] = None,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """
    Search for companies and return lightweight candidates.

    Uses:
    - exact match by CIN (fast, indexed)
    - FULLTEXT search on Company_Name (ft_company_name) when company_name is provided
    """
    top_k = max(1, min(int(top_k), 10))
    roc_code = roc_code.strip() if isinstance(roc_code, str) else None
    company_name = company_name.strip() if isinstance(company_name, str) else None

    if cin:
        cin = _clean_cin(cin)
        sql = f"""
            SELECT CIN, Company_Name, ROC_Code
            FROM {_COMPANY_TABLE_FQN}
            WHERE CIN = %s
            LIMIT 1
        """
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (cin,))
                row = cur.fetchone()
        return [dict(row)] if row else []

    if not company_name and not roc_code:
        return []

    where_sql = []
    params: Dict[str, Any] = {"top_k": top_k}

    score_select = ""
    order_by = ""
    if company_name:
        boolean_q = _build_boolean_fulltext_query(company_name)
        if not boolean_q:
            return []
        where_sql.append("MATCH(Company_Name) AGAINST (%s IN BOOLEAN MODE)")
        params["q"] = boolean_q
        score_select = (
            ", MATCH(Company_Name) AGAINST (%s IN BOOLEAN MODE) AS match_score"
        )
        order_by = "ORDER BY match_score DESC"

    if roc_code:
        where_sql.append("ROC_Code = %s")
        params["roc_code"] = roc_code

    where_clause = " AND ".join(where_sql) if where_sql else "1=1"

    sql = f"""
        SELECT CIN, Company_Name, ROC_Code{score_select}
        FROM {_COMPANY_TABLE_FQN}
        WHERE {where_clause}
        {order_by}
        LIMIT %s
    """

    # Convert named params to %s params in correct order.
    # order expected by where_clause:
    # - if company_name: :q used twice (WHERE + score)
    # - if roc_code: :roc_code used once
    # We'll build param list based on which inputs are set.
    param_list: List[Any] = []
    if company_name:
        param_list.extend([params["q"], params["q"]])
    if roc_code:
        param_list.append(params["roc_code"])
    # top_k last
    param_list.append(top_k)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, tuple(param_list))
            rows = cur.fetchall()

    # When company_name is None, match_score won't exist; normalize it away.
    normalized: List[Dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        d.pop("match_score", None)
        normalized.append(d)
    return normalized


def get_company_profile(*, cin: str) -> Optional[Dict[str, Any]]:
    """
    Fetch company profile by CIN.
    """
    cin = _clean_cin(cin)
    sql = f"""
        SELECT
          CIN,
          Company_Name,
          ROC_Code,
          Registration_Number,
          Company_Category,
          Company_SubCategory,
          Class_of_Company,
          Authorised_Capital_Rs,
          Paid_up_Capital_Rs,
          Number_of_Members,
          Date_of_Incorporation,
          Registered_Address,
          Email_Id,
          Whether_Listed_or_not,
          ACTIVE_compliance,
          Suspended_at_stock_exchange,
          Date_of_last_AGM,
          Date_of_Balance_Sheet,
          Company_Status,
          auditor,
          inc,
          dnd,
          last_updated
        FROM {_COMPANY_TABLE_FQN}
        WHERE CIN = %s
        LIMIT 1
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (cin,))
            row = cur.fetchone()
    if not row:
        return None

    d = dict(row)

    # Normalize keys to a consistent API-friendly form.
    # (If you prefer keeping DB column names, we can do that too.)
    return {
        "cin": d.get("CIN"),
        "company_name": d.get("Company_Name"),
        "roc_code": d.get("ROC_Code"),
        "registration_number": d.get("Registration_Number"),
        "company_category": d.get("Company_Category"),
        "company_subcategory": d.get("Company_SubCategory"),
        "class_of_company": d.get("Class_of_Company"),
        "authorised_capital_rs": d.get("Authorised_Capital_Rs"),
        "paid_up_capital_rs": d.get("Paid_up_Capital_Rs"),
        "number_of_members": d.get("Number_of_Members"),
        "date_of_incorporation": (
            d.get("Date_of_Incorporation").isoformat()
            if d.get("Date_of_Incorporation") is not None
            else None
        ),
        "registered_address": d.get("Registered_Address"),
        "email_id": d.get("Email_Id"),
        "whether_listed_or_not": d.get("Whether_Listed_or_not"),
        "active_compliance": d.get("ACTIVE_compliance"),
        "suspended_at_stock_exchange": d.get("Suspended_at_stock_exchange"),
        "date_of_last_agm": (
            d.get("Date_of_last_AGM").isoformat()
            if d.get("Date_of_last_AGM") is not None
            else None
        ),
        "date_of_balance_sheet": (
            d.get("Date_of_Balance_Sheet").isoformat()
            if d.get("Date_of_Balance_Sheet") is not None
            else None
        ),
        "company_status": d.get("Company_Status"),
        "auditor": d.get("auditor"),
        "inc": d.get("inc"),
        "dnd": d.get("dnd"),
        "last_updated": (
            d.get("last_updated").isoformat()
            if d.get("last_updated") is not None
            else None
        ),
    }


def _normalize_date_of_incorporation(date_of_incorporation: Optional[str]):
    if not date_of_incorporation or not isinstance(date_of_incorporation, str):
        return None, None
    s = date_of_incorporation.strip()

    # full year AI style: 2025 -> use YEAR(Date_of_Incorporation)
    if re.fullmatch(r"\d{4}", s):
        return int(s), None

    # full date year-month-day
    m = re.fullmatch(r"(\d{4})(?:-(\d{2}))(?:-(\d{2}))?", s)
    if not m:
        return None, None
    year, month, day = m.groups()

    if month in (None, "00") or day in (None, "00"):
        # fall back to year match for incomplete dates like 2025-00-00 or 2025-03-00
        return int(year), None

    # validate date and keep exact date string if valid
    try:
        date(int(year), int(month), int(day))
        return None, f"{year}-{month}-{day}"
    except ValueError:
        return int(year), None


def search_companies_by_filters(
    *,
    location: Optional[str] = None,
    domain_keywords: Optional[str] = None,
    date_of_incorporation: Optional[str] = None,
    top_k: int = 10,
) -> List[Dict[str, Any]]:
    """
    List companies matching simple natural-language filters.

    MVP approach:
    - Try fast FULLTEXT matching if indexes exist for the relevant columns.
    - If FULLTEXT indexes are missing, fall back to slower LIKE-based filters.

    Expected usage:
      - location -> match against Registered_Address
      - domain_keywords -> match against Company_Category and Company_SubCategory
    - date_of_incorporation -> match against Date_of_Incorporation (YYYY-MM-DD)
    """
    top_k = max(1, min(int(top_k), 20))
    location = (
        location.strip() if isinstance(location, str) and location.strip() else None
    )
    domain_keywords = (
        domain_keywords.strip()
        if isinstance(domain_keywords, str) and domain_keywords.strip()
        else None
    )
    date_of_incorporation = (
        date_of_incorporation.strip()
        if isinstance(date_of_incorporation, str) and date_of_incorporation.strip()
        else None
    )

    # If no filters, don't return everything.
    if not location and not domain_keywords and not date_of_incorporation:
        return []

    # Build tokenized boolean query for FULLTEXT (if indexes exist).
    domain_q = _build_boolean_fulltext_query(domain_keywords) if domain_keywords else ""
    print(f"Built domain boolean query: '{domain_q}' from raw input: '{domain_keywords}'")
    loc_q = _build_boolean_fulltext_query(location) if location else ""
    print(f"Built location boolean query: '{loc_q}' from raw input: '{location}'")

    # Support year-only filters for date_of_incorporation (e.g., 2025)
    # and normalize invalid/full-zero dates like 2025-00-00 -> year match.
    doi_year, doi_exact = _normalize_date_of_incorporation(date_of_incorporation)

    # Candidate columns we want to return.
    select_sql = """
        SELECT
          CIN,
          Company_Name,
          ROC_Code,
          Company_Category,
          Company_SubCategory,
          Company_Status,
          Date_of_Incorporation,
          Registered_Address,
          last_updated
        FROM {_table}
    """.format(_table=_COMPANY_TABLE_FQN)

    params: Dict[str, Any] = {"top_k": top_k}

    # Prefer FULLTEXT because dataset is big.
    try:
        where_parts: List[str] = []
        if domain_keywords and domain_q:
            where_parts.append(
                "(MATCH(Company_Category) AGAINST (%s IN BOOLEAN MODE)"
                " OR MATCH(Company_SubCategory) AGAINST (%s IN BOOLEAN MODE)"
                " OR MATCH(Company_Name) AGAINST (%s IN BOOLEAN MODE))"
            )
            params["domain_q"] = domain_q
        if location and loc_q:
            where_parts.append("MATCH(Registered_Address) AGAINST (%s IN BOOLEAN MODE)")
            params["loc_q"] = loc_q
        if doi_year is not None:
            where_parts.append("YEAR(Date_of_Incorporation) = %s")
            params["doi_year"] = doi_year
        elif doi_exact is not None:
            where_parts.append("Date_of_Incorporation = %s")
            params["doi_exact"] = doi_exact

        where_clause = " AND ".join(where_parts) if where_parts else "1=1"

        sql = f"""
            {select_sql}
            WHERE {where_clause}
            LIMIT %s
        """

        # Build %s params in correct order of appearance in SQL.
        # Our where_clause order depends on which filters are active:
        # - if domain_keywords present: we inserted domain_q 3 times
        # - if location present: inserted loc_q once
        # then LIMIT.
        param_list: List[Any] = []
        if domain_keywords and domain_q:
            param_list.extend(
                [params["domain_q"], params["domain_q"], params["domain_q"]]
            )
        if location and loc_q:
            param_list.append(params["loc_q"])
        if doi_year is not None:
            param_list.append(params["doi_year"])
        elif doi_exact is not None:
            param_list.append(params["doi_exact"])
        param_list.append(top_k)

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, tuple(param_list))
                rows = cur.fetchall()
    except Exception:
        # FULLTEXT fallback (slower): LIKE search.
        # This will scan the table if indexes are not present.
        domain_tokens = []
        if domain_keywords:
            domain_tokens = [
                t
                for t in re.split(r"[^A-Za-z0-9]+", domain_keywords)
                if t and len(t) >= 2
            ]
        loc_token = location.upper() if location else None

        # For each token, require it to appear in at least one of the domain-related columns.
        token_conds: List[str] = []
        param_list: List[Any] = []
        for i, tok in enumerate(domain_tokens):
            token_conds.append(
                "(Company_Category LIKE %s OR Company_SubCategory LIKE %s OR Company_Name LIKE %s)"
            )
            pattern = f"%{tok}%"
            # 3 placeholders per token (Category, SubCategory, Name)
            param_list.extend([pattern, pattern, pattern])

        where_parts = []
        if token_conds:
            where_parts.append("(" + " AND ".join(token_conds) + ")")
        if loc_token:
            where_parts.append("UPPER(Registered_Address) LIKE %s")
            param_list.append(f"%{loc_token}%")
        if doi_year is not None:
            where_parts.append("YEAR(Date_of_Incorporation) = %s")
            param_list.append(doi_year)
        elif doi_exact is not None:
            where_parts.append("Date_of_Incorporation = %s")
            param_list.append(doi_exact)

        where_clause = " AND ".join(where_parts) if where_parts else "1=1"

        sql = f"""
            {select_sql}
            WHERE {where_clause}
            LIMIT %s
        """
        param_list.append(top_k)

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, tuple(param_list))
                rows = cur.fetchall()

    out: List[Dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        # Avoid returning huge Registered_Address blobs.
        addr = d.get("Registered_Address")
        if isinstance(addr, str) and len(addr) > 300:
            d["registered_address"] = addr[:300] + "..."
        else:
            d["registered_address"] = addr
        d.pop("Registered_Address", None)

        doi = d.get("Date_of_Incorporation")
        if doi is not None and hasattr(doi, "isoformat"):
            d["date_of_incorporation"] = doi.isoformat()
        else:
            d["date_of_incorporation"] = doi
        d.pop("Date_of_Incorporation", None)

        last_updated = d.get("last_updated")
        if last_updated is not None and hasattr(last_updated, "isoformat"):
            d["last_updated"] = last_updated.isoformat()
        out.append(d)
    return out
