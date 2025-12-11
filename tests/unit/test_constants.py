"""
Tests for constants and utility functions
"""

import pytest
from app.core.constants import (
    CountryInfo,
    CurrencyInfo,
    CountryCode,
    CurrencyCode,
    DataSource,
    ToolName,
    COUNTRIES,
    CURRENCIES,
    VALID_DATA_SOURCES,
    get_country_by_code,
    get_currency_by_code,
    get_all_countries,
    get_all_currencies,
    get_countries_for_currency,
    validate_data_sources,
    get_data_source_suggestions,
)


class TestCountryInfo:
    """Test CountryInfo NamedTuple"""

    def test_country_info_creation(self):
        """Test creating CountryInfo instance"""
        country = CountryInfo("US", "United States", "ארצות הברית", "🇺🇸")
        assert country.code == "US"
        assert country.name_en == "United States"
        assert country.name_he == "ארצות הברית"
        assert country.flag_emoji == "🇺🇸"

    def test_country_info_immutable(self):
        """Test that CountryInfo is immutable"""
        country = CountryInfo("US", "United States", "ארצות הברית", "🇺🇸")
        with pytest.raises(AttributeError):
            country.code = "CA"


class TestCurrencyInfo:
    """Test CurrencyInfo NamedTuple"""

    def test_currency_info_creation(self):
        """Test creating CurrencyInfo instance"""
        currency = CurrencyInfo("USD", "US Dollar", "דולר אמריקאי", "$")
        assert currency.code == "USD"
        assert currency.name_en == "US Dollar"
        assert currency.name_he == "דולר אמריקאי"
        assert currency.symbol == "$"

    def test_currency_info_immutable(self):
        """Test that CurrencyInfo is immutable"""
        currency = CurrencyInfo("USD", "US Dollar", "דולר אמריקאי", "$")
        with pytest.raises(AttributeError):
            currency.code = "EUR"


class TestCountryConstants:
    """Test country-related constants and functions"""

    def test_countries_dict_structure(self):
        """Test that COUNTRIES dict has correct structure"""
        assert isinstance(COUNTRIES, dict)
        assert len(COUNTRIES) > 0

        # Test a few known countries
        israel = COUNTRIES["IL"]
        assert israel.code == "IL"
        assert israel.name_en == "Israel"
        assert israel.name_he == "ישראל"
        assert israel.flag_emoji == "🇮🇱"

        usa = COUNTRIES["US"]
        assert usa.code == "US"
        assert usa.name_en == "United States"
        assert usa.flag_emoji == "🇺🇸"

    def test_get_country_by_code_existing(self):
        """Test getting existing country by code"""
        country = get_country_by_code("IL")
        assert country is not None
        assert country.code == "IL"
        assert country.name_en == "Israel"

    def test_get_country_by_code_case_insensitive(self):
        """Test that country lookup is case insensitive"""
        country_upper = get_country_by_code("IL")
        country_lower = get_country_by_code("il")
        assert country_upper == country_lower

    def test_get_country_by_code_nonexistent(self):
        """Test getting nonexistent country by code"""
        country = get_country_by_code("XX")
        assert country is None

    def test_get_all_countries(self):
        """Test getting all countries as list"""
        countries = get_all_countries()
        assert isinstance(countries, list)
        assert len(countries) == len(COUNTRIES)
        assert all(isinstance(country, CountryInfo) for country in countries)

    def test_get_countries_for_currency_euro(self):
        """Test getting countries for Euro currency"""
        countries = get_countries_for_currency("EUR")
        assert isinstance(countries, list)
        assert len(countries) > 0
        assert all(isinstance(country, CountryInfo) for country in countries)

        # Should include Germany, France, etc.
        country_codes = [c.code for c in countries]
        assert "DE" in country_codes
        assert "FR" in country_codes

    def test_get_countries_for_currency_usd(self):
        """Test getting countries for USD currency"""
        countries = get_countries_for_currency("USD")
        assert isinstance(countries, list)
        assert len(countries) == 1
        assert countries[0].code == "US"

    def test_get_countries_for_currency_unknown(self):
        """Test getting countries for unknown currency"""
        countries = get_countries_for_currency("XYZ")
        assert isinstance(countries, list)
        assert len(countries) == 0


class TestCurrencyConstants:
    """Test currency-related constants and functions"""

    def test_currencies_dict_structure(self):
        """Test that CURRENCIES dict has correct structure"""
        assert isinstance(CURRENCIES, dict)
        assert len(CURRENCIES) > 0

        # Test a few known currencies
        ils = CURRENCIES["ILS"]
        assert ils.code == "ILS"
        assert ils.name_en == "Israeli Shekel"
        assert ils.name_he == "שקל ישראלי"
        assert ils.symbol == "₪"

        usd = CURRENCIES["USD"]
        assert usd.code == "USD"
        assert usd.name_en == "US Dollar"
        assert usd.symbol == "$"

    def test_get_currency_by_code_existing(self):
        """Test getting existing currency by code"""
        currency = get_currency_by_code("USD")
        assert currency is not None
        assert currency.code == "USD"
        assert currency.name_en == "US Dollar"

    def test_get_currency_by_code_case_insensitive(self):
        """Test that currency lookup is case insensitive"""
        currency_upper = get_currency_by_code("USD")
        currency_lower = get_currency_by_code("usd")
        assert currency_upper == currency_lower

    def test_get_currency_by_code_nonexistent(self):
        """Test getting nonexistent currency by code"""
        currency = get_currency_by_code("XYZ")
        assert currency is None

    def test_get_all_currencies(self):
        """Test getting all currencies as list"""
        currencies = get_all_currencies()
        assert isinstance(currencies, list)
        assert len(currencies) == len(CURRENCIES)
        assert all(isinstance(currency, CurrencyInfo) for currency in currencies)


class TestDataSourceValidation:
    """Test data source validation functions"""

    def test_validate_data_sources_all_valid(self):
        """Test validating all valid data sources"""
        sources = ["ga4", "google_ads", "facebook_ads"]
        valid, invalid = validate_data_sources(sources)
        assert valid == sources
        assert invalid == []

    def test_validate_data_sources_mixed(self):
        """Test validating mixed valid and invalid sources"""
        sources = ["ga4", "invalid_source", "google_ads", "another_invalid"]
        valid, invalid = validate_data_sources(sources)
        assert valid == ["ga4", "google_ads"]
        assert invalid == ["invalid_source", "another_invalid"]

    def test_validate_data_sources_all_invalid(self):
        """Test validating all invalid sources"""
        sources = ["invalid1", "invalid2"]
        valid, invalid = validate_data_sources(sources)
        assert valid == []
        assert invalid == sources

    def test_validate_data_sources_empty(self):
        """Test validating empty list"""
        sources = []
        valid, invalid = validate_data_sources(sources)
        assert valid == []
        assert invalid == []

    def test_get_data_source_suggestions_google_analytics(self):
        """Test suggestions for 'google analytics'"""
        suggestions = get_data_source_suggestions("google analytics")
        assert "ga4" in suggestions

    def test_get_data_source_suggestions_adwords(self):
        """Test suggestions for 'adwords'"""
        suggestions = get_data_source_suggestions("adwords")
        assert "google_ads" in suggestions

    def test_get_data_source_suggestions_facebook(self):
        """Test suggestions for 'fb'"""
        suggestions = get_data_source_suggestions("fb")
        assert "facebook" in suggestions
        assert "facebook_ads" in suggestions

    def test_get_data_source_suggestions_similar(self):
        """Test suggestions for similar but invalid sources"""
        suggestions = get_data_source_suggestions("facebok")  # typo
        # The function looks for sources that contain the invalid string or vice versa
        # "facebok" doesn't match any existing sources exactly, so it should return empty
        assert isinstance(suggestions, list)

    def test_get_data_source_suggestions_no_match(self):
        """Test suggestions when no match found"""
        suggestions = get_data_source_suggestions("completely_unknown")
        assert isinstance(suggestions, list)
        # Should return empty list for completely unknown sources


class TestEnums:
    """Test enum constants"""

    def test_data_source_enum_values(self):
        """Test DataSource enum values"""
        assert DataSource.GA4 == "ga4"
        assert DataSource.GOOGLE_ADS == "google_ads"
        assert DataSource.FACEBOOK_ADS == "facebook_ads"

    def test_tool_name_enum_values(self):
        """Test ToolName enum values"""
        assert ToolName.GA4_ANALYTICS_TOOL == "ga4_analytics_tool"
        assert ToolName.GOOGLE_ADS_TOOL == "google_ads_tool"
        assert ToolName.FACEBOOK_TOOL == "facebook_tool"

    def test_country_code_enum_values(self):
        """Test CountryCode enum values"""
        assert CountryCode.ISRAEL == "IL"
        assert CountryCode.UNITED_STATES == "US"
        assert CountryCode.UNITED_KINGDOM == "GB"

    def test_currency_code_enum_values(self):
        """Test CurrencyCode enum values"""
        assert CurrencyCode.ISRAELI_SHEKEL == "ILS"
        assert CurrencyCode.US_DOLLAR == "USD"
        assert CurrencyCode.EURO == "EUR"

    def test_valid_data_sources_list(self):
        """Test VALID_DATA_SOURCES list"""
        assert isinstance(VALID_DATA_SOURCES, list)
        assert len(VALID_DATA_SOURCES) > 0
        assert "ga4" in VALID_DATA_SOURCES
        assert "google_ads" in VALID_DATA_SOURCES
        assert "facebook_ads" in VALID_DATA_SOURCES


class TestConstantsIntegration:
    """Test integration between constants and functions"""

    def test_country_enum_matches_dict(self):
        """Test that CountryCode enum values exist in COUNTRIES dict"""
        for country_code in CountryCode:
            assert country_code.value in COUNTRIES

    def test_currency_enum_matches_dict(self):
        """Test that CurrencyCode enum values exist in CURRENCIES dict"""
        for currency_code in CurrencyCode:
            assert currency_code.value in CURRENCIES

    def test_data_source_enum_matches_valid_list(self):
        """Test that DataSource enum values are in VALID_DATA_SOURCES"""
        for data_source in DataSource:
            assert data_source.value in VALID_DATA_SOURCES
