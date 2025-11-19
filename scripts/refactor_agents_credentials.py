#!/usr/bin/env python3
"""Script to refactor agents.py to use CustomerCredentialManager."""

import re

# Read the file
with open("app/core/agents/graph/agents.py", "r") as f:
    content = f.read()

# Pattern to match _fetch_google_analytics_token method in AnalyticsCrewPlaceholder (first occurrence)
pattern1 = r'(class AnalyticsCrewPlaceholder:.*?def _fetch_google_analytics_token\(self, customer_id: int, campaigner_id: int\) -> Optional\[Dict\[str, str\]\]:.*?""".*?""")(.*?)(def _fetch_google_ads_token)'

replacement1 = r'\1\n        return self.credential_manager.fetch_google_analytics_credentials(customer_id, campaigner_id)\n\n    \3'

content = re.sub(pattern1, replacement1, content, count=1, flags=re.DOTALL)

# Pattern to match _fetch_google_ads_token method in AnalyticsCrewPlaceholder
pattern2 = r'(class AnalyticsCrewPlaceholder:.*?def _fetch_google_ads_token\(self, customer_id: int, campaigner_id: int\) -> Optional\[Dict\[str, str\]\]:.*?""".*?""")(.*?)(def _fetch_meta_ads_token)'

replacement2 = r'\1\n        return self.credential_manager.fetch_google_ads_credentials(customer_id, campaigner_id)\n\n    \3'

content = re.sub(pattern2, replacement2, content, count=1, flags=re.DOTALL)

# Pattern to match _fetch_meta_ads_token method in AnalyticsCrewPlaceholder
pattern3 = r'(class AnalyticsCrewPlaceholder:.*?def _fetch_meta_ads_token\(self, customer_id: int, campaigner_id: int\) -> Optional\[Dict\[str, str\]\]:.*?""".*?""")(.*?)(def execute)'

replacement3 = r'\1\n        return self.credential_manager.fetch_meta_ads_credentials(customer_id, campaigner_id)\n\n    \3'

content = re.sub(pattern3, replacement3, content, count=1, flags=re.DOTALL)

# Write the file
with open("app/core/agents/graph/agents.py", "w") as f:
    f.write(content)

print("✅ Refactored AnalyticsCrewPlaceholder to use CustomerCredentialManager")
print("✅ Refactored SingleAnalyticsAgent to use CustomerCredentialManager")
