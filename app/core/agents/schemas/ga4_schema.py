"""
Google Analytics 4 API Schema Reference
Based on: https://developers.google.com/analytics/devguides/reporting/data/v1/api-schema
Last Updated: 2025-12-11
"""

# GA4 METRICS REFERENCE
# Organized by category for easy reference

GA4_METRICS = {
    "user_metrics": {
        "activeUsers": "Number of distinct users who visited your site or app",
        "active1DayUsers": "Number of distinct active users on your site or app within a 1 day period",
        "active7DayUsers": "Number of distinct active users on your site or app within a 7 day period",
        "active28DayUsers": "Number of distinct active users on your site or app within a 28 day period",
        "newUsers": "Number of users who interacted with your site or app for the first time",
        "totalUsers": "Total number of users",
        "dauPerMau": "Daily Active Users per Monthly Active Users ratio",
        "dauPerWau": "Daily Active Users per Weekly Active Users ratio",
        "wauPerMau": "Weekly Active Users per Monthly Active Users ratio",
    },

    "session_metrics": {
        "sessions": "Number of sessions that began on your site or app",
        "engagedSessions": "Number of sessions that lasted 10 seconds or longer, or had 1+ conversion events or 2+ page/screen views",
        "sessionsPerUser": "Average number of sessions per user",
        "bounceRate": "Percentage of sessions that were not engaged sessions",
        "engagementRate": "Percentage of sessions that were engaged sessions",
        "averageSessionDuration": "Average duration (in seconds) of users' sessions",
        "sessionConversionRate": "Percentage of sessions that resulted in a conversion event",
    },

    "engagement_metrics": {
        "screenPageViews": "Total number of app screens or web pages your users viewed",
        "screenPageViewsPerSession": "Average number of pages or screens viewed per session",
        "userEngagementDuration": "Total time (in seconds) that your site or app was in the foreground",
        "averageSessionDuration": "Average duration (in seconds) of users' sessions",
        "eventCount": "Count of events",
        "eventCountPerUser": "Average number of events per user",
        "eventsPerSession": "Average number of events per session",
    },

    "conversion_metrics": {
        "conversions": "Count of conversion events",
        "userConversionRate": "Percentage of users who triggered a conversion event",
        "sessionConversionRate": "Percentage of sessions that resulted in a conversion event",
        "eventValue": "Sum of the event parameter named 'value'",
    },

    "revenue_metrics": {
        "totalRevenue": "Sum of revenue from purchases, in-app purchases, subscriptions, and advertising",
        "purchaseRevenue": "Sum of revenue from purchases made on your website or app",
        "averagePurchaseRevenue": "Average revenue from purchases",
        "totalAdRevenue": "Sum of revenue from advertising via the AdMob and Ad Manager integrations",
        "publisherAdClicks": "Number of times ads were clicked",
        "publisherAdImpressions": "Number of times ads were displayed",
    },

    "ecommerce_metrics": {
        "transactions": "Number of purchase transactions",
        "transactionsPerPurchaser": "Average number of transactions per purchaser",
        "purchaseToViewRate": "Purchase-to-view rate (number of transactions divided by number of users who viewed any product)",
        "ecommercePurchases": "Number of times users completed a purchase",
        "itemsViewed": "Number of times an item was viewed",
        "itemsPurchased": "Number of items purchased",
        "itemRevenue": "Revenue from items only",
        "itemsAddedToCart": "Number of times an item was added to cart",
        "itemsCheckedOut": "Number of times an item was checked out",
        "itemListClickThroughRate": "Percentage of users who viewed an item list and then selected an item",
        "itemPromotionClickThroughRate": "Percentage of users who viewed a promotion and then selected it",
        "cartToViewRate": "Number of users who added a product to their cart divided by number of users who viewed any product",
        "addToCarts": "Number of times users added items to their shopping carts",
        "checkouts": "Number of times users started the checkout process",
    },

    "purchaser_metrics": {
        "totalPurchasers": "Number of users who made a purchase",
        "newPurchasers": "Number of new purchasers (first-time purchasers)",
        "firstTimePurchasers": "Number of users who completed a purchase for the first time",
        "firstTimePurchaserConversionRate": "Percentage of new users who made a purchase",
        "purchaserConversionRate": "Percentage of active users who made a purchase",
    },

    "traffic_metrics": {
        "organicGoogleSearchClicks": "Number of organic clicks from Google Search",
        "organicGoogleSearchImpressions": "Number of organic impressions from Google Search",
        "organicGoogleSearchClickThroughRate": "Click-through rate for organic Google Search results",
        "organicGoogleSearchAveragePosition": "Average ranking position of your URLs in organic Google Search results",
    },

    "cohort_metrics": {
        "cohortActiveUsers": "Number of users in a cohort who are active",
        "cohortTotalUsers": "Total number of users in a cohort",
    },
}

# GA4 DIMENSIONS REFERENCE
# Organized by category for easy reference

GA4_DIMENSIONS = {
    "date_time_dimensions": {
        "date": "Date of the event (YYYYMMDD format). REQUIRED for most queries",
        "dateHour": "Combined date and hour (YYYYMMDDHH format)",
        "dateHourMinute": "Combined date, hour, and minute (YYYYMMDDHHMM format)",
        "year": "Year of the event (YYYY format)",
        "month": "Month of the event (01-12)",
        "week": "Week of the event (00-53)",
        "day": "Day of the month (01-31)",
        "hour": "Hour of the day (00-23)",
        "minute": "Minute of the hour (00-59)",
        "dayOfWeek": "Integer day of week (0-6, Sunday is 0)",
        "dayOfWeekName": "Name of the day (Monday, Tuesday, etc.)",
        "isoWeek": "ISO week number (each week starts on Monday)",
        "isoYear": "ISO year of the event",
        "isoYearIsoWeek": "Combined ISO year and ISO week",
        "yearMonth": "Combined year and month (YYYYMM format)",
        "yearWeek": "Combined year and week (YYYYWW format)",
    },

    "geography_dimensions": {
        "continent": "Continent where users are located (e.g., Americas, Asia, Europe)",
        "subContinent": "Sub-continent where users are located (e.g., Western Europe, Northern America)",
        "country": "Country where users are located",
        "region": "Geographic region (typically state or province)",
        "city": "City where users are located",
        "metro": "Designated market area (DMA) where users are located",
        "latitude": "Approximate latitude of users",
        "longitude": "Approximate longitude of users",
    },

    "traffic_source_dimensions": {
        "source": "Source of traffic (google, direct, facebook, etc.)",
        "medium": "Medium of traffic (organic, cpc, referral, email, etc.)",
        "sourceMedium": "Combined source and medium (google / organic)",
        "sourcePlatform": "Source platform of the traffic source",
        "campaign": "Marketing campaign name",
        "campaignId": "Marketing campaign ID",
        "campaignName": "Marketing campaign name (alias for campaign)",
        "adContent": "Ad content identifier",
        "googleAdsAccountName": "Google Ads account name",
        "googleAdsAdGroupId": "Google Ads ad group ID",
        "googleAdsAdGroupName": "Google Ads ad group name",
        "googleAdsAdNetworkType": "Google Ads network type (Search, Display, etc.)",
        "googleAdsCampaignId": "Google Ads campaign ID",
        "googleAdsCampaignName": "Google Ads campaign name",
        "googleAdsCustomerId": "Google Ads customer ID",
        "googleAdsKeyword": "Google Ads matched keyword",
        "googleAdsQuery": "Google Ads search query",
        "term": "Keyword term from the traffic source",
    },

    "session_dimensions": {
        "sessionSource": "Session-scoped traffic source",
        "sessionMedium": "Session-scoped traffic medium",
        "sessionSourceMedium": "Combined session source and medium",
        "sessionCampaignId": "Session-scoped campaign ID",
        "sessionCampaignName": "Session-scoped campaign name",
        "sessionDefaultChannelGroup": "Default channel group for the session based on traffic source",
        "sessionGoogleAdsAccountName": "Session-scoped Google Ads account name",
        "sessionGoogleAdsAdGroupId": "Session-scoped Google Ads ad group ID",
        "sessionGoogleAdsAdGroupName": "Session-scoped Google Ads ad group name",
        "sessionGoogleAdsAdNetworkType": "Session-scoped Google Ads network type",
        "sessionGoogleAdsCampaignId": "Session-scoped Google Ads campaign ID",
        "sessionGoogleAdsCampaignName": "Session-scoped Google Ads campaign name",
        "sessionGoogleAdsKeyword": "Session-scoped Google Ads keyword",
        "sessionGoogleAdsQuery": "Session-scoped Google Ads query",
        "sessionManualAdContent": "Session-scoped manual ad content from UTM parameters",
        "sessionManualTerm": "Session-scoped manual term from UTM parameters",
    },

    "user_dimensions": {
        "userId": "User ID set via the User-ID feature",
        "newVsReturning": "Indicates whether the user is new or returning",
        "userAgeBracket": "Age bracket of the user (18-24, 25-34, etc.)",
        "userGender": "Gender of the user",
        "language": "Language preference of the user",
        "languageCode": "ISO 639-1 language code",
        "firstSessionDate": "Date of the user's first session (YYYYMMDD format)",
        "firstUserCampaignId": "Campaign ID that first acquired the user",
        "firstUserCampaignName": "Campaign name that first acquired the user",
        "firstUserSource": "Source that first acquired the user",
        "firstUserMedium": "Medium that first acquired the user",
        "firstUserSourceMedium": "Combined first user source and medium",
        "firstUserSourcePlatform": "Source platform that first acquired the user",
        "firstUserGoogleAdsAccountName": "Google Ads account name that first acquired the user",
        "firstUserGoogleAdsAdGroupId": "Google Ads ad group ID that first acquired the user",
        "firstUserGoogleAdsAdGroupName": "Google Ads ad group name that first acquired the user",
        "firstUserGoogleAdsAdNetworkType": "Google Ads network type that first acquired the user",
        "firstUserGoogleAdsCampaignId": "Google Ads campaign ID that first acquired the user",
        "firstUserGoogleAdsCampaignName": "Google Ads campaign name that first acquired the user",
        "firstUserGoogleAdsKeyword": "Google Ads keyword that first acquired the user",
        "firstUserGoogleAdsQuery": "Google Ads query that first acquired the user",
    },

    "device_dimensions": {
        "deviceCategory": "Type of device (desktop, mobile, tablet)",
        "deviceModel": "Model name of the device",
        "mobileDeviceBranding": "Mobile device branding/manufacturer",
        "mobileDeviceMarketingName": "Marketing name of the mobile device",
        "mobileDeviceModel": "Model of the mobile device",
        "operatingSystem": "Operating system of the device",
        "operatingSystemVersion": "Version of the operating system",
        "operatingSystemWithVersion": "Operating system with version number",
        "browser": "Browser used to view your website",
        "browserVersion": "Version of the browser",
        "screenResolution": "Screen resolution of the device (e.g., 1920x1080)",
    },

    "platform_dimensions": {
        "platform": "Platform where your app or site ran (Web, iOS, Android)",
        "platformDeviceCategory": "Combined platform and device category",
        "appVersion": "Version of your app",
        "streamId": "Numeric identifier of a data stream",
        "streamName": "Name of the data stream",
    },

    "page_dimensions": {
        "pagePath": "Page path portion of URL",
        "pagePathPlusQueryString": "Page path and query string portion of URL",
        "pageTitle": "Title of the page",
        "pageLocation": "Full URL of the page",
        "pageReferrer": "Full URL of the previous page",
        "hostName": "Hostname from where data was reported",
        "landingPage": "First page in users' sessions",
        "landingPagePlusQueryString": "First page with query string in users' sessions",
        "contentGroup": "Content group that the page belongs to",
        "contentId": "Identifier for a specific content item",
        "contentType": "Type of content",
    },

    "event_dimensions": {
        "eventName": "Name of the event",
        "linkClasses": "CSS class of the link clicked",
        "linkDomain": "Domain of the link clicked",
        "linkId": "ID attribute of the link clicked",
        "linkText": "Text of the link clicked",
        "linkUrl": "Full URL of the link clicked",
        "outbound": "Whether the link leads to a destination outside your property (true/false)",
        "fileExtension": "Extension of downloaded files",
        "fileName": "Name of downloaded files",
        "videoProvider": "Provider of embedded videos (YouTube, Vimeo, etc.)",
        "videoTitle": "Title of the video",
        "videoUrl": "URL of the video",
        "searchTerm": "Term used in site search",
    },

    "ecommerce_dimensions": {
        "itemId": "ID of the item",
        "itemName": "Name of the item",
        "itemBrand": "Brand of the item",
        "itemVariant": "Variant of the item",
        "itemCategory": "Category of the item",
        "itemCategory2": "Second category level",
        "itemCategory3": "Third category level",
        "itemCategory4": "Fourth category level",
        "itemCategory5": "Fifth category level",
        "itemListId": "ID of the item list",
        "itemListName": "Name of the item list",
        "itemListPosition": "Position of the item in the list",
        "itemPromotionCreativeName": "Name of the promotional creative",
        "itemPromotionId": "ID of the promotion",
        "itemPromotionName": "Name of the promotion",
        "transactionId": "Transaction ID",
        "affiliation": "Store or affiliation from which the transaction occurred",
        "coupon": "Coupon code used in the transaction",
        "currency": "Currency of the purchase or item",
        "paymentType": "Payment method used",
        "shippingTier": "Shipping tier (e.g., Ground, Air, Next-day)",
    },

    "app_dimensions": {
        "appInstanceId": "App instance ID",
        "firebaseAppId": "Firebase app ID",
        "appId": "ID of the app",
        "appStore": "Store where the app is distributed (Google Play, App Store)",
        "appStoreId": "ID of the app in the app store",
        "brandingInterest": "Branding interest categories",
    },
}

# COMMON GA4 DIMENSION/METRIC COMBINATIONS
# These are frequently used together and are known to be compatible

COMMON_REPORT_TYPES = {
    "traffic_overview": {
        "metrics": ["sessions", "newUsers", "screenPageViews", "bounceRate", "averageSessionDuration"],
        "dimensions": ["date"],
        "description": "Basic traffic overview over time"
    },

    "traffic_sources": {
        "metrics": ["sessions", "newUsers", "engagedSessions", "bounceRate", "averageSessionDuration"],
        "dimensions": ["sessionSource", "sessionMedium", "sessionSourceMedium"],
        "description": "Traffic acquisition by source and medium"
    },

    "channel_performance": {
        "metrics": ["sessions", "engagedSessions", "conversions", "totalRevenue"],
        "dimensions": ["sessionDefaultChannelGroup"],
        "description": "Performance by default channel grouping"
    },

    "geography": {
        "metrics": ["sessions", "newUsers", "screenPageViews", "bounceRate"],
        "dimensions": ["country", "city"],
        "description": "User activity by geographic location"
    },

    "device_type": {
        "metrics": ["sessions", "screenPageViews", "bounceRate", "averageSessionDuration"],
        "dimensions": ["deviceCategory"],
        "description": "Performance by device type"
    },

    "landing_pages": {
        "metrics": ["sessions", "newUsers", "bounceRate", "conversions"],
        "dimensions": ["landingPage"],
        "description": "Performance by landing page"
    },

    "page_performance": {
        "metrics": ["screenPageViews", "averageSessionDuration", "bounceRate"],
        "dimensions": ["pagePath", "pageTitle"],
        "description": "Individual page performance"
    },

    "campaign_performance": {
        "metrics": ["sessions", "newUsers", "conversions", "totalRevenue", "engagementRate"],
        "dimensions": ["sessionCampaignName", "sessionSource", "sessionMedium"],
        "description": "Marketing campaign effectiveness"
    },

    "google_ads": {
        "metrics": ["sessions", "conversions", "totalRevenue", "sessionConversionRate"],
        "dimensions": ["sessionGoogleAdsCampaignName", "sessionGoogleAdsAdGroupName", "sessionGoogleAdsKeyword"],
        "description": "Google Ads campaign performance"
    },

    "ecommerce_overview": {
        "metrics": ["purchaseRevenue", "transactions", "itemsPurchased", "averagePurchaseRevenue"],
        "dimensions": ["date"],
        "description": "E-commerce performance over time"
    },

    "product_performance": {
        "metrics": ["itemRevenue", "itemsPurchased", "itemsViewed", "cartToViewRate"],
        "dimensions": ["itemName", "itemCategory", "itemBrand"],
        "description": "Individual product performance"
    },

    "user_engagement": {
        "metrics": ["engagedSessions", "userEngagementDuration", "eventCount", "eventsPerSession"],
        "dimensions": ["eventName"],
        "description": "User engagement by event type"
    },

    "conversions": {
        "metrics": ["conversions", "userConversionRate", "sessionConversionRate", "eventValue"],
        "dimensions": ["eventName", "sessionSource", "sessionMedium"],
        "description": "Conversion event analysis"
    },
}

# IMPORTANT NOTES FOR USING GA4 API

USAGE_NOTES = """
CRITICAL GA4 DIMENSION/METRIC NAMING CONVENTIONS:

1. SESSION-SCOPED vs USER-SCOPED DIMENSIONS:
   - For campaign analysis, use sessionCampaignName or sessionCampaignId (NOT campaign/campaignId)
   - For traffic source, use sessionSource or firstUserSource (NOT just 'source')
   - For medium, use sessionMedium or firstUserMedium (NOT just 'medium')
   - Combined: use sessionSourceMedium or firstUserSourceMedium

2. DATE FORMATTING:
   - 'date' dimension returns YYYYMMDD format (e.g., 20231215)
   - Date ranges in API requests use YYYY-MM-DD format (e.g., 2023-12-15)
   - Always include 'date' dimension for time-series analysis

3. METRIC/DIMENSION COMPATIBILITY:
   - Not all metrics work with all dimensions
   - User-scoped metrics (totalUsers, newUsers) work with most dimensions
   - Session-scoped metrics (sessions, bounceRate) work with session dimensions
   - Item-scoped metrics (itemRevenue, itemsPurchased) require item dimensions

4. COMMON FILTERS:
   - To exclude internal traffic: add dimension filter for 'country' != '(not set)'
   - To filter Google organic: sessionSource == 'google' AND sessionMedium == 'organic'
   - To filter specific campaign: sessionCampaignName == 'your_campaign_name'

5. DATA TYPE REQUIREMENTS:
   - Date ranges: string in YYYY-MM-DD format
   - Dimension filters: string comparison operators (==, !=, contains, etc.)
   - Metric filters: numeric comparison operators (==, !=, <, >, <=, >=)
   - Multiple conditions: use AND/OR logic with proper grouping

6. PROPERTY ID:
   - Always required for GA4 API requests
   - Format: numeric property ID (e.g., '123456789')
   - Can be found in GA4 Admin settings

7. LIMITS AND PAGINATION:
   - Default limit: 10,000 rows per request
   - Maximum dimensions per request: 9
   - Maximum metrics per request: 10
   - Use pagination (offset + limit) for large datasets
"""


def get_metric_info(metric_name: str) -> dict:
    """Get information about a specific GA4 metric."""
    for category, metrics in GA4_METRICS.items():
        if metric_name in metrics:
            return {
                "name": metric_name,
                "description": metrics[metric_name],
                "category": category
            }
    return {"error": f"Metric '{metric_name}' not found in GA4 schema"}


def get_dimension_info(dimension_name: str) -> dict:
    """Get information about a specific GA4 dimension."""
    for category, dimensions in GA4_DIMENSIONS.items():
        if dimension_name in dimensions:
            return {
                "name": dimension_name,
                "description": dimensions[dimension_name],
                "category": category
            }
    return {"error": f"Dimension '{dimension_name}' not found in GA4 schema"}


def get_all_metrics() -> list:
    """Get list of all available GA4 metrics."""
    all_metrics = []
    for category, metrics in GA4_METRICS.items():
        all_metrics.extend(metrics.keys())
    return sorted(all_metrics)


def get_all_dimensions() -> list:
    """Get list of all available GA4 dimensions."""
    all_dimensions = []
    for category, dimensions in GA4_DIMENSIONS.items():
        all_dimensions.extend(dimensions.keys())
    return sorted(all_dimensions)


def get_report_template(report_type: str) -> dict:
    """Get a pre-configured report template."""
    if report_type in COMMON_REPORT_TYPES:
        return COMMON_REPORT_TYPES[report_type]
    return {"error": f"Report type '{report_type}' not found"}


def search_metrics(keyword: str) -> list:
    """Search for metrics containing the keyword."""
    results = []
    keyword_lower = keyword.lower()
    for category, metrics in GA4_METRICS.items():
        for metric_name, description in metrics.items():
            if keyword_lower in metric_name.lower() or keyword_lower in description.lower():
                results.append({
                    "name": metric_name,
                    "description": description,
                    "category": category
                })
    return results


def search_dimensions(keyword: str) -> list:
    """Search for dimensions containing the keyword."""
    results = []
    keyword_lower = keyword.lower()
    for category, dimensions in GA4_DIMENSIONS.items():
        for dimension_name, description in dimensions.items():
            if keyword_lower in dimension_name.lower() or keyword_lower in description.lower():
                results.append({
                    "name": dimension_name,
                    "description": description,
                    "category": category
                })
    return results
