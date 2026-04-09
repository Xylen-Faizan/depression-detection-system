import os
import requests
import logging
from app.config import OPENCAGE_API_KEY

logger = logging.getLogger(__name__)

HELPLINES = {
    "IN": {  # India
        "default": [
            {"name": "iCall", "number": "9152987821"},
            {"name": "Vandrevala Foundation", "number": "1860-2662-345"},
            {"name": "NIMHANS", "number": "080-46110007"},
        ],
        "Maharashtra": [
            {"name": "iCall", "number": "9152987821"},
            {"name": "AASRA", "number": "9820466726"},
            {"name": "Vandrevala Foundation", "number": "1860-2662-345"},
        ],
        "Delhi": [
            {"name": "Sanjivini", "number": "011-24311918"},
            {"name": "Vandrevala Foundation", "number": "1860-2662-345"},
            {"name": "iCall", "number": "9152987821"},
        ],
        "Karnataka": [
            {"name": "NIMHANS", "number": "080-46110007"},
            {"name": "SAHAI", "number": "080-25497777"},
            {"name": "Vandrevala Foundation", "number": "1860-2662-345"},
        ]
    },
    "US": { # USA
        "default": [
            {"name": "988 Suicide & Crisis Lifeline", "number": "988"},
            {"name": "Crisis Text Line", "number": "Text HOME to 741741"},
            {"name": "The Trevor Project", "number": "866-488-7386"},
        ]
    },
    "GB": { # UK
        "default": [
            {"name": "Samaritans", "number": "116 123"},
            {"name": "National Suicide Prevention Helpline UK", "number": "0800 689 5652"},
            {"name": "Shout Crisis Text Line", "number": "Text SHOUT to 85258"},
        ]
    }
}

class HelplineService:
    @staticmethod
    def get_nearest_helplines(latitude, longitude):
        if not latitude or not longitude:
            logger.warning("No coordinates provided for helpline. Falling back to India defaults.")
            return HELPLINES.get("IN", {}).get("default", [])

        try:
            country_code, state = HelplineService._reverse_geocode(latitude, longitude)
            logger.info(f"Reverse geocode result: Country={country_code}, State={state}")

            country_helplines = HELPLINES.get(country_code)
            if not country_helplines:
                # Fallback to IN if country not found
                return HELPLINES.get("IN", {}).get("default", [])

            # Check for state specific helplines first
            if state and state in country_helplines:
                return country_helplines[state][:3]
            
            # Fallback to country default
            return country_helplines.get("default", [])[:3]

        except Exception as e:
            logger.error(f"Error fetching nearest helplines: {e}")
            return HELPLINES.get("IN", {}).get("default", [])

    @staticmethod
    def _reverse_geocode(latitude, longitude):
        if OPENCAGE_API_KEY:
            # Use OpenCage
            try:
                url = f"https://api.opencagedata.com/geocode/v1/json?q={latitude}+{longitude}&key={OPENCAGE_API_KEY}"
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("results"):
                        components = data["results"][0].get("components", {})
                        country_code = components.get("country_code", "").upper()
                        state = components.get("state", "")
                        return country_code, state
            except Exception as e:
                logger.error(f"OpenCage geocoding failed: {e}")
        else:
            # Use ipapi.co as fallback or log that key is missing
            logger.warning("OPENCAGE_API_KEY not found. Geocoding disabled or fallback needed.")
            pass # Without IP it is tricky to use IPAPI for geolocation of Lat/Long explicitly

        # Fallback to default
        return "IN", "default"
