"""
API routes for countries and currencies constants
"""

from fastapi import APIRouter
from typing import List
from app.core.constants import (
    get_all_countries, get_all_currencies, get_country_by_code, get_currency_by_code,
    get_countries_for_currency, CountryInfo, CurrencyInfo
)

router = APIRouter()


@router.get("/countries", response_model=List[dict])
async def get_countries():
    """Get all countries with English and Hebrew names"""
    countries = get_all_countries()
    return [
        {
            "code": country.code,
            "name_en": country.name_en,
            "name_he": country.name_he,
            "flag_emoji": country.flag_emoji
        }
        for country in countries
    ]


@router.get("/currencies", response_model=List[dict])
async def get_currencies():
    """Get all currencies with English and Hebrew names"""
    currencies = get_all_currencies()
    return [
        {
            "code": currency.code,
            "name_en": currency.name_en,
            "name_he": currency.name_he,
            "symbol": currency.symbol
        }
        for currency in currencies
    ]


@router.get("/countries/{country_code}")
async def get_country(country_code: str):
    """Get specific country by code"""
    country = get_country_by_code(country_code)
    if not country:
        return {"error": "Country not found"}
    
    return {
        "code": country.code,
        "name_en": country.name_en,
        "name_he": country.name_he,
        "flag_emoji": country.flag_emoji
    }


@router.get("/currencies/{currency_code}")
async def get_currency(currency_code: str):
    """Get specific currency by code"""
    currency = get_currency_by_code(currency_code)
    if not currency:
        return {"error": "Currency not found"}
    
    return {
        "code": currency.code,
        "name_en": currency.name_en,
        "name_he": currency.name_he,
        "symbol": currency.symbol
    }


@router.get("/currencies/{currency_code}/countries")
async def get_countries_for_currency_endpoint(currency_code: str):
    """Get countries that use a specific currency"""
    countries = get_countries_for_currency(currency_code)
    return [
        {
            "code": country.code,
            "name_en": country.name_en,
            "name_he": country.name_he,
            "flag_emoji": country.flag_emoji
        }
        for country in countries
    ]
