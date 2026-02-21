# regions.py

REGIONS = {
    "UK": {
        "label": "United Kingdom",
        "playwright_locale": "en-GB",
        "analysis_language": "English (UK)",
        "focus": [
            "UK localization (spelling, tone, terminology, sizing conventions, units)",
            "UK compliance signals (VAT/taxes clarity, delivery charges clarity, fibre/material composition disclosure)",
        ],
    },
    "CA_EN": {
        "label": "Canada (English)",
        "playwright_locale": "en-CA",
        "analysis_language": "English (Canada)",
        "focus": [
            "Canada localization (spelling, terminology, sizing conventions, units)",
            "Canada compliance signals (taxes/duties clarity like GST/HST/PST, delivery/returns clarity, fibre/material composition disclosure)",
        ],
    },
    "CA_FR": {
        "label": "Canada (Français)",
        "playwright_locale": "fr-CA",
        "analysis_language": "Français (Canada)",
        "focus": [
            "French-Canada localization (complete French experience, natural phrasing, correct units and sizing conventions)",
            "Canada compliance signals (taxes/duties clarity like GST/HST/PST, delivery/returns clarity, bilingual presentation where applicable)",
        ],
    },
    "DE": {
        "label": "Germany",
        "playwright_locale": "de-DE",
        "analysis_language": "Deutsch",
        "focus": [
            "DE localization (German copy quality, metric units, EU sizing conventions)",
            "EU/DE compliance signals (VAT-included clarity, delivery/returns clarity, fibre/material composition disclosure)",
        ],
    },
    "FR": {
        "label": "France",
        "playwright_locale": "fr-FR",
        "analysis_language": "Français",
        "focus": [
            "FR localization (French copy quality, metric units, EU sizing conventions)",
            "EU/FR compliance signals (VAT-included clarity, delivery/returns clarity, fibre/material composition disclosure)",
        ],
    },
}