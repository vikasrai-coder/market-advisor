def normalize_symbol(symbol: str) -> str:
    s = symbol.strip().upper()
    if "." in s:
        return s
    return f"{s}.NS"


def display_symbol(symbol: str) -> str:
    return symbol.replace(".NS", "").replace(".BO", "")
