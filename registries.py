from typing import Dict, List, Optional

COUNTRY_REGISTRY: Dict[str, str] = {
    "al": "Albania", "ad": "Andorra", "at": "Austria", "by": "Belarus", "be": "Belgium",
    "ba": "Bosnia and Herzegovina", "bg": "Bulgaria", "hr": "Croatia", "cy": "Cyprus",
    "cz": "Czech Republic", "dk": "Denmark", "ee": "Estonia", "fi": "Finland", "fr": "France",
    "de": "Germany", "gr": "Greece", "hu": "Hungary", "is": "Iceland", "ie": "Ireland",
    "it": "Italy", "xk": "Kosovo", "lv": "Latvia", "li": "Liechtenstein", "lt": "Lithuania",
    "lu": "Luxembourg", "mt": "Malta", "md": "Moldova", "mc": "Monaco", "me": "Montenegro",
    "nl": "Netherlands", "mk": "North Macedonia", "no": "Norway", "pl": "Poland", "pt": "Portugal",
    "ro": "Romania", "ru": "Russia", "sm": "San Marino", "rs": "Serbia", "sk": "Slovakia",
    "si": "Slovenia", "es": "Spain", "se": "Sweden", "ch": "Switzerland", "tr": "Turkey",
    "ua": "Ukraine", "uk": "United Kingdom", "gb": "United Kingdom"
}

SUPPORTED_LANGUAGES: List[str] = [
    "en", "pt", "es", "fr", "de", "it", "ru", "pl", "uk"
]

def normalize_country_code(code: str) -> Optional[str]:
    """
    Validates and normalizes country code.
    Accepts 'gb' but returns 'uk'.
    Returns None if invalid.
    """
    code = code.lower().strip()
    if code not in COUNTRY_REGISTRY:
        return None
    if code == "gb":
        return "uk"
    return code

def validate_language(lang: str) -> bool:
    """Checks if language is supported."""
    return lang.lower().strip() in SUPPORTED_LANGUAGES

def validate_depth(depth: str) -> bool:
    return depth in ["fast", "standard", "extended"]

def validate_time_horizon(horizon: str) -> bool:
    return horizon in ["24h", "3d", "7d"]
