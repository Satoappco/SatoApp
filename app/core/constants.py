"""
Constants for SatoApp - Agent types, data sources, tools, countries and currencies
"""

from typing import Dict, List, NamedTuple, Set
from enum import Enum


# ===== COUNTRY AND CURRENCY CONSTANTS =====

class CountryInfo(NamedTuple):
    """Country information with English and Hebrew names"""
    code: str
    name_en: str
    name_he: str
    flag_emoji: str


class CurrencyInfo(NamedTuple):
    """Currency information with English and Hebrew names"""
    code: str
    name_en: str
    name_he: str
    symbol: str


# Countries with English and Hebrew names
COUNTRIES: Dict[str, CountryInfo] = {
    "IL": CountryInfo("IL", "Israel", "ישראל", "🇮🇱"),
    "US": CountryInfo("US", "United States", "ארצות הברית", "🇺🇸"),
    "GB": CountryInfo("GB", "United Kingdom", "בריטניה", "🇬🇧"),
    "DE": CountryInfo("DE", "Germany", "גרמניה", "🇩🇪"),
    "FR": CountryInfo("FR", "France", "צרפת", "🇫🇷"),
    "IT": CountryInfo("IT", "Italy", "איטליה", "🇮🇹"),
    "ES": CountryInfo("ES", "Spain", "ספרד", "🇪🇸"),
    "CA": CountryInfo("CA", "Canada", "קנדה", "🇨🇦"),
    "AU": CountryInfo("AU", "Australia", "אוסטרליה", "🇦🇺"),
    "JP": CountryInfo("JP", "Japan", "יפן", "🇯🇵"),
    "CN": CountryInfo("CN", "China", "סין", "🇨🇳"),
    "IN": CountryInfo("IN", "India", "הודו", "🇮🇳"),
    "BR": CountryInfo("BR", "Brazil", "ברזיל", "🇧🇷"),
    "RU": CountryInfo("RU", "Russia", "רוסיה", "🇷🇺"),
    "MX": CountryInfo("MX", "Mexico", "מקסיקו", "🇲🇽"),
    "AR": CountryInfo("AR", "Argentina", "ארגנטינה", "🇦🇷"),
    "ZA": CountryInfo("ZA", "South Africa", "דרום אפריקה", "🇿🇦"),
    "EG": CountryInfo("EG", "Egypt", "מצרים", "🇪🇬"),
    "TR": CountryInfo("TR", "Turkey", "טורקיה", "🇹🇷"),
    "SA": CountryInfo("SA", "Saudi Arabia", "ערב הסעודית", "🇸🇦"),
    "AE": CountryInfo("AE", "United Arab Emirates", "איחוד האמירויות הערביות", "🇦🇪"),
    "NL": CountryInfo("NL", "Netherlands", "הולנד", "🇳🇱"),
    "BE": CountryInfo("BE", "Belgium", "בלגיה", "🇧🇪"),
    "CH": CountryInfo("CH", "Switzerland", "שוויץ", "🇨🇭"),
    "AT": CountryInfo("AT", "Austria", "אוסטריה", "🇦🇹"),
    "SE": CountryInfo("SE", "Sweden", "שוודיה", "🇸🇪"),
    "NO": CountryInfo("NO", "Norway", "נורווגיה", "🇳🇴"),
    "DK": CountryInfo("DK", "Denmark", "דנמרק", "🇩🇰"),
    "FI": CountryInfo("FI", "Finland", "פינלנד", "🇫🇮"),
    "PL": CountryInfo("PL", "Poland", "פולין", "🇵🇱"),
    "CZ": CountryInfo("CZ", "Czech Republic", "צ'כיה", "🇨🇿"),
    "HU": CountryInfo("HU", "Hungary", "הונגריה", "🇭🇺"),
    "RO": CountryInfo("RO", "Romania", "רומניה", "🇷🇴"),
    "BG": CountryInfo("BG", "Bulgaria", "בולגריה", "🇧🇬"),
    "GR": CountryInfo("GR", "Greece", "יוון", "🇬🇷"),
    "PT": CountryInfo("PT", "Portugal", "פורטוגל", "🇵🇹"),
    "IE": CountryInfo("IE", "Ireland", "אירלנד", "🇮🇪"),
    "NZ": CountryInfo("NZ", "New Zealand", "ניו זילנד", "🇳🇿"),
    "SG": CountryInfo("SG", "Singapore", "סינגפור", "🇸🇬"),
    "HK": CountryInfo("HK", "Hong Kong", "הונג קונג", "🇭🇰"),
    "KR": CountryInfo("KR", "South Korea", "דרום קוריאה", "🇰🇷"),
    "TH": CountryInfo("TH", "Thailand", "תאילנד", "🇹🇭"),
    "MY": CountryInfo("MY", "Malaysia", "מלזיה", "🇲🇾"),
    "ID": CountryInfo("ID", "Indonesia", "אינדונזיה", "🇮🇩"),
    "PH": CountryInfo("PH", "Philippines", "הפיליפינים", "🇵🇭"),
    "VN": CountryInfo("VN", "Vietnam", "וייטנאם", "🇻🇳"),
    "TW": CountryInfo("TW", "Taiwan", "טייוואן", "🇹🇼"),
}


# Currencies with English and Hebrew names
CURRENCIES: Dict[str, CurrencyInfo] = {
    "ILS": CurrencyInfo("ILS", "Israeli Shekel", "שקל ישראלי", "₪"),
    "USD": CurrencyInfo("USD", "US Dollar", "דולר אמריקאי", "$"),
    "EUR": CurrencyInfo("EUR", "Euro", "אירו", "€"),
    "GBP": CurrencyInfo("GBP", "British Pound", "לירה שטרלינג", "£"),
    "JPY": CurrencyInfo("JPY", "Japanese Yen", "ין יפני", "¥"),
    "CAD": CurrencyInfo("CAD", "Canadian Dollar", "דולר קנדי", "C$"),
    "AUD": CurrencyInfo("AUD", "Australian Dollar", "דולר אוסטרלי", "A$"),
    "CHF": CurrencyInfo("CHF", "Swiss Franc", "פרנק שוויצרי", "CHF"),
    "CNY": CurrencyInfo("CNY", "Chinese Yuan", "יואן סיני", "¥"),
    "INR": CurrencyInfo("INR", "Indian Rupee", "רופי הודי", "₹"),
    "BRL": CurrencyInfo("BRL", "Brazilian Real", "ריאל ברזילאי", "R$"),
    "RUB": CurrencyInfo("RUB", "Russian Ruble", "רובל רוסי", "₽"),
    "MXN": CurrencyInfo("MXN", "Mexican Peso", "פזו מקסיקני", "$"),
    "ARS": CurrencyInfo("ARS", "Argentine Peso", "פזו ארגנטינאי", "$"),
    "ZAR": CurrencyInfo("ZAR", "South African Rand", "רנד דרום אפריקאי", "R"),
    "EGP": CurrencyInfo("EGP", "Egyptian Pound", "לירה מצרית", "E£"),
    "TRY": CurrencyInfo("TRY", "Turkish Lira", "לירה טורקית", "₺"),
    "SAR": CurrencyInfo("SAR", "Saudi Riyal", "ריאל סעודי", "﷼"),
    "AED": CurrencyInfo("AED", "UAE Dirham", "דירהם אמירויות", "د.إ"),
    "SEK": CurrencyInfo("SEK", "Swedish Krona", "כתר שוודי", "kr"),
    "NOK": CurrencyInfo("NOK", "Norwegian Krone", "כתר נורווגי", "kr"),
    "DKK": CurrencyInfo("DKK", "Danish Krone", "כתר דני", "kr"),
    "PLN": CurrencyInfo("PLN", "Polish Zloty", "זלוטי פולני", "zł"),
    "CZK": CurrencyInfo("CZK", "Czech Koruna", "כתר צ'כי", "Kč"),
    "HUF": CurrencyInfo("HUF", "Hungarian Forint", "פורינט הונגרי", "Ft"),
    "RON": CurrencyInfo("RON", "Romanian Leu", "לאו רומני", "lei"),
    "BGN": CurrencyInfo("BGN", "Bulgarian Lev", "לב בולגרי", "лв"),
    "KRW": CurrencyInfo("KRW", "South Korean Won", "וון דרום קוריאני", "₩"),
    "THB": CurrencyInfo("THB", "Thai Baht", "באט תאילנדי", "฿"),
    "MYR": CurrencyInfo("MYR", "Malaysian Ringgit", "רינגיט מלזי", "RM"),
    "IDR": CurrencyInfo("IDR", "Indonesian Rupiah", "רופיה אינדונזית", "Rp"),
    "PHP": CurrencyInfo("PHP", "Philippine Peso", "פזו פיליפיני", "₱"),
    "VND": CurrencyInfo("VND", "Vietnamese Dong", "דונג וייטנאמי", "₫"),
    "TWD": CurrencyInfo("TWD", "Taiwan Dollar", "דולר טייוואני", "NT$"),
    "SGD": CurrencyInfo("SGD", "Singapore Dollar", "דולר סינגפורי", "S$"),
    "HKD": CurrencyInfo("HKD", "Hong Kong Dollar", "דולר הונג קונג", "HK$"),
    "NZD": CurrencyInfo("NZD", "New Zealand Dollar", "דולר ניו זילנדי", "NZ$"),
}


def get_country_by_code(code: str) -> CountryInfo:
    """Get country information by country code"""
    return COUNTRIES.get(code.upper())


def get_currency_by_code(code: str) -> CurrencyInfo:
    """Get currency information by currency code"""
    return CURRENCIES.get(code.upper())


def get_all_countries() -> List[CountryInfo]:
    """Get all countries as a list"""
    return list(COUNTRIES.values())


def get_all_currencies() -> List[CurrencyInfo]:
    """Get all currencies as a list"""
    return list(CURRENCIES.values())


def get_countries_for_currency(currency_code: str) -> List[CountryInfo]:
    """Get countries that use a specific currency"""
    # This is a simplified mapping - in reality, multiple countries can use the same currency
    currency_country_mapping = {
        "ILS": ["IL"],
        "USD": ["US"],
        "EUR": ["DE", "FR", "IT", "ES", "NL", "BE", "AT", "FI", "IE", "PT", "GR"],
        "GBP": ["GB"],
        "JPY": ["JP"],
        "CAD": ["CA"],
        "AUD": ["AU"],
        "CHF": ["CH"],
        "CNY": ["CN"],
        "INR": ["IN"],
        "BRL": ["BR"],
        "RUB": ["RU"],
        "MXN": ["MX"],
        "ARS": ["AR"],
        "ZAR": ["ZA"],
        "EGP": ["EG"],
        "TRY": ["TR"],
        "SAR": ["SA"],
        "AED": ["AE"],
        "SEK": ["SE"],
        "NOK": ["NO"],
        "DKK": ["DK"],
        "PLN": ["PL"],
        "CZK": ["CZ"],
        "HUF": ["HU"],
        "RON": ["RO"],
        "BGN": ["BG"],
        "KRW": ["KR"],
        "THB": ["TH"],
        "MYR": ["MY"],
        "IDR": ["ID"],
        "PHP": ["PH"],
        "VND": ["VN"],
        "TWD": ["TW"],
        "SGD": ["SG"],
        "HKD": ["HK"],
        "NZD": ["NZ"],
    }
    
    country_codes = currency_country_mapping.get(currency_code.upper(), [])
    return [COUNTRIES[code] for code in country_codes if code in COUNTRIES]


# ===== AGENT SYSTEM CONSTANTS =====

class AgentType(str, Enum):
    """Agent types enum"""
    SEO_CAMPAIGN_MANAGER = "seo_campaign_manager"
    GA4_ANALYST = "ga4_analyst"
    GOOGLE_ADS_SPECIALIST = "google_ads_specialist"
    FACEBOOK_ADS_SPECIALIST = "facebook_ads_specialist"
    SOCIAL_MEDIA_SPECIALIST = "social_media_specialist"
    CONTENT_SPECIALIST = "content_specialist"
    EMAIL_MARKETING_SPECIALIST = "email_marketing_specialist"
    ECOMMERCE_SPECIALIST = "ecommerce_specialist"
    CRM_SPECIALIST = "crm_specialist"
    ANALYTICS_SPECIALIST = "analytics_specialist"
    REPORTING_SPECIALIST = "reporting_specialist"


class DataSource(str, Enum):
    """Data source types enum"""
    GA4 = "ga4"
    GOOGLE_ADS = "google_ads"
    FACEBOOK_ADS = "facebook_ads"
    FACEBOOK = "facebook"
    GOOGLE_SEARCH_CONSOLE = "google_search_console"
    INSTAGRAM = "instagram"
    LINKEDIN = "linkedin"
    TWITTER = "twitter"
    YOUTUBE = "youtube"
    TIKTOK = "tiktok"
    EMAIL_MARKETING = "email_marketing"
    CRM = "crm"
    ECOMMERCE = "ecommerce"
    ADVERTISING = "advertising"


class ToolName(str, Enum):
    """Tool names enum"""
    GA4_ANALYTICS_TOOL = "ga4_analytics_tool"
    GOOGLE_ADS_TOOL = "google_ads_tool"
    FACEBOOK_TOOL = "facebook_tool"
    SEARCH_CONSOLE_TOOL = "search_console_tool"
    EMAIL_MARKETING_TOOL = "email_marketing_tool"
    CRM_TOOL = "crm_tool"
    ECOMMERCE_TOOL = "ecommerce_tool"
    SOCIAL_MEDIA_TOOL = "social_media_tool"
    CONTENT_TOOL = "content_tool"
    REPORTING_TOOL = "reporting_tool"


# Valid data sources list
VALID_DATA_SOURCES = [source.value for source in DataSource]


# ===== AGENT TOOL MAPPING =====

def get_tools_for_agent(agent_type: str) -> List[str]:
    """Get tools for a specific agent type"""
    tool_mapping = {
        AgentType.SEO_CAMPAIGN_MANAGER: [
            ToolName.GA4_ANALYTICS_TOOL,
            ToolName.GOOGLE_ADS_TOOL,
            ToolName.SEARCH_CONSOLE_TOOL,
            ToolName.REPORTING_TOOL
        ],
        AgentType.GA4_ANALYST: [
            ToolName.GA4_ANALYTICS_TOOL,
            ToolName.REPORTING_TOOL
        ],
        AgentType.GOOGLE_ADS_SPECIALIST: [
            ToolName.GOOGLE_ADS_TOOL,
            ToolName.GA4_ANALYTICS_TOOL,
            ToolName.REPORTING_TOOL
        ],
        AgentType.FACEBOOK_ADS_SPECIALIST: [
            ToolName.FACEBOOK_TOOL,
            ToolName.GA4_ANALYTICS_TOOL,
            ToolName.REPORTING_TOOL
        ],
        AgentType.SOCIAL_MEDIA_SPECIALIST: [
            ToolName.SOCIAL_MEDIA_TOOL,
            ToolName.FACEBOOK_TOOL,
            ToolName.REPORTING_TOOL
        ],
        AgentType.CONTENT_SPECIALIST: [
            ToolName.CONTENT_TOOL,
            ToolName.SOCIAL_MEDIA_TOOL,
            ToolName.REPORTING_TOOL
        ],
        AgentType.EMAIL_MARKETING_SPECIALIST: [
            ToolName.EMAIL_MARKETING_TOOL,
            ToolName.GA4_ANALYTICS_TOOL,
            ToolName.REPORTING_TOOL
        ],
        AgentType.ECOMMERCE_SPECIALIST: [
            ToolName.ECOMMERCE_TOOL,
            ToolName.GA4_ANALYTICS_TOOL,
            ToolName.REPORTING_TOOL
        ],
        AgentType.CRM_SPECIALIST: [
            ToolName.CRM_TOOL,
            ToolName.GA4_ANALYTICS_TOOL,
            ToolName.REPORTING_TOOL
        ],
        AgentType.ANALYTICS_SPECIALIST: [
            ToolName.GA4_ANALYTICS_TOOL,
            ToolName.REPORTING_TOOL
        ],
        AgentType.REPORTING_SPECIALIST: [
            ToolName.REPORTING_TOOL,
            ToolName.GA4_ANALYTICS_TOOL
        ]
    }
    
    return tool_mapping.get(agent_type, [])


def get_data_sources_for_agent(agent_type: str) -> List[str]:
    """Get data sources for a specific agent type"""
    data_source_mapping = {
        AgentType.SEO_CAMPAIGN_MANAGER: [
            DataSource.GA4,
            DataSource.GOOGLE_ADS,
            DataSource.GOOGLE_SEARCH_CONSOLE
        ],
        AgentType.GA4_ANALYST: [
            DataSource.GA4
        ],
        AgentType.GOOGLE_ADS_SPECIALIST: [
            DataSource.GOOGLE_ADS,
            DataSource.GA4
        ],
        AgentType.FACEBOOK_ADS_SPECIALIST: [
            DataSource.FACEBOOK_ADS,
            DataSource.FACEBOOK,
            DataSource.GA4
        ],
        AgentType.SOCIAL_MEDIA_SPECIALIST: [
            DataSource.FACEBOOK,
            DataSource.INSTAGRAM,
            DataSource.LINKEDIN,
            DataSource.TWITTER,
            DataSource.YOUTUBE,
            DataSource.TIKTOK
        ],
        AgentType.CONTENT_SPECIALIST: [
            DataSource.FACEBOOK,
            DataSource.INSTAGRAM,
            DataSource.LINKEDIN,
            DataSource.TWITTER,
            DataSource.YOUTUBE
        ],
        AgentType.EMAIL_MARKETING_SPECIALIST: [
            DataSource.EMAIL_MARKETING,
            DataSource.GA4
        ],
        AgentType.ECOMMERCE_SPECIALIST: [
            DataSource.ECOMMERCE,
            DataSource.GA4,
            DataSource.GOOGLE_ADS
        ],
        AgentType.CRM_SPECIALIST: [
            DataSource.CRM,
            DataSource.GA4
        ],
        AgentType.ANALYTICS_SPECIALIST: [
            DataSource.GA4,
            DataSource.GOOGLE_SEARCH_CONSOLE
        ],
        AgentType.REPORTING_SPECIALIST: [
            DataSource.GA4,
            DataSource.GOOGLE_ADS,
            DataSource.FACEBOOK_ADS
        ]
    }
    
    return data_source_mapping.get(agent_type, [])


def should_include_agent(agent_type: str, data_sources: List[str], user_question: str) -> bool:
    """Determine if an agent should be included based on context"""
    # Get expected data sources for this agent
    expected_sources = get_data_sources_for_agent(agent_type)
    
    # Check if any expected data sources are present
    has_relevant_sources = any(source in data_sources for source in expected_sources)
    
    # Check if user question contains relevant keywords
    question_lower = user_question.lower()
    
    keyword_mapping = {
        AgentType.GA4_ANALYST: ["analytics", "ga4", "google analytics", "traffic", "visitors", "sessions"],
        AgentType.GOOGLE_ADS_SPECIALIST: ["google ads", "adwords", "ads", "campaign", "keywords", "bidding"],
        AgentType.FACEBOOK_ADS_SPECIALIST: ["facebook", "facebook ads", "meta", "social ads", "targeting"],
        AgentType.SOCIAL_MEDIA_SPECIALIST: ["social media", "facebook", "instagram", "linkedin", "twitter", "social"],
        AgentType.CONTENT_SPECIALIST: ["content", "blog", "article", "copy", "writing", "seo content"],
        AgentType.EMAIL_MARKETING_SPECIALIST: ["email", "newsletter", "campaign", "mailing", "subscribers"],
        AgentType.ECOMMERCE_SPECIALIST: ["ecommerce", "shop", "store", "products", "sales", "conversion"],
        AgentType.CRM_SPECIALIST: ["crm", "customers", "leads", "contacts", "database"],
        AgentType.ANALYTICS_SPECIALIST: ["analytics", "data", "metrics", "kpi", "reporting"],
        AgentType.REPORTING_SPECIALIST: ["report", "dashboard", "summary", "analysis", "insights"]
    }
    
    has_relevant_keywords = any(keyword in question_lower for keyword in keyword_mapping.get(agent_type, []))
    
    return has_relevant_sources or has_relevant_keywords


# ===== DATA SOURCE VALIDATION =====

def validate_data_sources(data_sources: List[str]) -> tuple[List[str], List[str]]:
    """Validate data sources and return valid and invalid ones"""
    valid_sources = []
    invalid_sources = []
    
    for source in data_sources:
        if source in VALID_DATA_SOURCES:
            valid_sources.append(source)
        else:
            invalid_sources.append(source)
    
    return valid_sources, invalid_sources


def get_data_source_suggestions(invalid_source: str) -> List[str]:
    """Get suggestions for invalid data source names"""
    suggestions = []
    invalid_lower = invalid_source.lower()
    
    # Common misspellings and variations
    suggestion_map = {
        "google analytics": [DataSource.GA4],
        "ga": [DataSource.GA4],
        "google adwords": [DataSource.GOOGLE_ADS],
        "adwords": [DataSource.GOOGLE_ADS],
        "fb": [DataSource.FACEBOOK, DataSource.FACEBOOK_ADS],
        "meta": [DataSource.FACEBOOK, DataSource.FACEBOOK_ADS],
        "search console": [DataSource.GOOGLE_SEARCH_CONSOLE],
        "gsc": [DataSource.GOOGLE_SEARCH_CONSOLE],
        "ig": [DataSource.INSTAGRAM],
        "yt": [DataSource.YOUTUBE],
        "email": [DataSource.EMAIL_MARKETING],
        "shopify": [DataSource.ECOMMERCE],
        "woocommerce": [DataSource.ECOMMERCE],
        "salesforce": [DataSource.CRM],
        "hubspot": [DataSource.CRM]
    }
    
    for key, suggestions_list in suggestion_map.items():
        if key in invalid_lower:
            suggestions.extend([s.value for s in suggestions_list])
    
    # If no specific suggestions, return similar valid sources
    if not suggestions:
        for valid_source in VALID_DATA_SOURCES:
            if invalid_lower in valid_source.lower() or valid_source.lower() in invalid_lower:
                suggestions.append(valid_source)
    
    return list(set(suggestions))  # Remove duplicates


# ===== COUNTRY AND CURRENCY UTILITY FUNCTIONS =====

# Enums for easy validation
class CountryCode(str, Enum):
    """Country codes enum"""
    ISRAEL = "IL"
    UNITED_STATES = "US"
    UNITED_KINGDOM = "GB"
    GERMANY = "DE"
    FRANCE = "FR"
    ITALY = "IT"
    SPAIN = "ES"
    CANADA = "CA"
    AUSTRALIA = "AU"
    JAPAN = "JP"
    CHINA = "CN"
    INDIA = "IN"
    BRAZIL = "BR"
    RUSSIA = "RU"
    MEXICO = "MX"
    ARGENTINA = "AR"
    SOUTH_AFRICA = "ZA"
    EGYPT = "EG"
    TURKEY = "TR"
    SAUDI_ARABIA = "SA"
    UAE = "AE"
    NETHERLANDS = "NL"
    BELGIUM = "BE"
    SWITZERLAND = "CH"
    AUSTRIA = "AT"
    SWEDEN = "SE"
    NORWAY = "NO"
    DENMARK = "DK"
    FINLAND = "FI"
    POLAND = "PL"
    CZECH_REPUBLIC = "CZ"
    HUNGARY = "HU"
    ROMANIA = "RO"
    BULGARIA = "BG"
    GREECE = "GR"
    PORTUGAL = "PT"
    IRELAND = "IE"
    NEW_ZEALAND = "NZ"
    SINGAPORE = "SG"
    HONG_KONG = "HK"
    SOUTH_KOREA = "KR"
    THAILAND = "TH"
    MALAYSIA = "MY"
    INDONESIA = "ID"
    PHILIPPINES = "PH"
    VIETNAM = "VN"
    TAIWAN = "TW"


class CurrencyCode(str, Enum):
    """Currency codes enum"""
    ISRAELI_SHEKEL = "ILS"
    US_DOLLAR = "USD"
    EURO = "EUR"
    BRITISH_POUND = "GBP"
    JAPANESE_YEN = "JPY"
    CANADIAN_DOLLAR = "CAD"
    AUSTRALIAN_DOLLAR = "AUD"
    SWISS_FRANC = "CHF"
    CHINESE_YUAN = "CNY"
    INDIAN_RUPEE = "INR"
    BRAZILIAN_REAL = "BRL"
    RUSSIAN_RUBLE = "RUB"
    MEXICAN_PESO = "MXN"
    ARGENTINE_PESO = "ARS"
    SOUTH_AFRICAN_RAND = "ZAR"
    EGYPTIAN_POUND = "EGP"
    TURKISH_LIRA = "TRY"
    SAUDI_RIYAL = "SAR"
    UAE_DIRHAM = "AED"
    SWEDISH_KRONA = "SEK"
    NORWEGIAN_KRONE = "NOK"
    DANISH_KRONE = "DKK"
    POLISH_ZLOTY = "PLN"
    CZECH_KORUNA = "CZK"
    HUNGARIAN_FORINT = "HUF"
    ROMANIAN_LEU = "RON"
    BULGARIAN_LEV = "BGN"
    SOUTH_KOREAN_WON = "KRW"
    THAI_BAHT = "THB"
    MALAYSIAN_RINGGIT = "MYR"
    INDONESIAN_RUPIAH = "IDR"
    PHILIPPINE_PESO = "PHP"
    VIETNAMESE_DONG = "VND"
    TAIWAN_DOLLAR = "TWD"
    SINGAPORE_DOLLAR = "SGD"
    HONG_KONG_DOLLAR = "HKD"
    NEW_ZEALAND_DOLLAR = "NZD"