from groq import Groq
from app.config import GROQ_API_KEY, GROQ_MODEL_NAME
import logging
import ast
import json
import re
from typing import Dict, Any

logger = logging.getLogger(__name__)

class LLMProcessor:
    def __init__(self):
        self.client = Groq(api_key=GROQ_API_KEY)
        self.conversation_history = []
        self.depression_keywords = {
            'hopelessness': 0.8,
            'worthless': 0.85,
            'suicide': 0.95,
            'depressed': 0.75,
            'lonely': 0.7,
            'sad': 0.65,
            'empty': 0.7,
            'guilt': 0.75,
            'tired': 0.6,
            'sleep': 0.65,
            'appetite': 0.6,
            'concentration': 0.65
        }
        self.positive_keywords = {
            'happy': -0.7,
            'joy': -0.75,
            'excited': -0.65,
            'good': -0.5,
            'better': -0.6,
            'improve': -0.55
        }

    def _extract_json(self, text: str) -> Dict[str, Any]:
        """Extract JSON from LLM response, handling various formats."""
        try:
            # Try to find JSON within markdown code blocks
            match = re.search(r'```(?:json)?\n(.*?)\n```', text, re.DOTALL)
            if match:
                text = match.group(1)

            # Try direct JSON parsing first
            return json.loads(text)
        except json.JSONDecodeError:
            try:
                # Fallback to literal_eval for non-standard JSON
                return ast.literal_eval(text)
            except (ValueError, SyntaxError):
                logger.error("Could not extract JSON from response")
                return None

    def _calculate_lexical_confidence(self, text: str) -> float:
        """Calculate initial confidence score based on keyword analysis."""
        text_lower = text.lower()
        score = 0.0
        keyword_count = 0

        # Check for depression keywords
        for keyword, weight in self.depression_keywords.items():
            if keyword in text_lower:
                score += weight
                keyword_count += 1

        # Check for positive keywords that might mitigate depression signals
        for keyword, weight in self.positive_keywords.items():
            if keyword in text_lower:
                score += weight
                keyword_count += 1

        # Normalize score (0-1 range)
        if keyword_count > 0:
            normalized_score = min(max(score / keyword_count, 0.0), 1.0)
            return round(normalized_score, 2)
        return 0.5  # Default neutral score if no keywords found

    def analyze_depression(self, text: str) -> Dict[str, Any]:
        try:
            lexical_confidence = self._calculate_lexical_confidence(text)
            history = "\n".join([f"User: {msg['input']}\nAI: {msg['output']}"
                               for msg in self.conversation_history[-3:]])

            prompt = f"""
Perform a comprehensive depression analysis considering:
1. Semantic content and emotional tone
2. Severity indicators (mention of self-harm, extreme hopelessness)
3. Duration indicators (long-term vs recent feelings)
4. Impact on daily functioning

Message: {text}

First, analyze these aspects and determine:
- Depression likelihood (0-1 scale)
- Severity level (mild, moderate, severe)
- Whether professional help is recommended

Then generate a supportive response appropriate for the determined level.

Respond with ONLY the following JSON structure:
{{
    "analysis_type": "depression"|"conflict"|"other",
    "is_depressed": bool,
    "confidence": float (0-1),
    "severity": "mild"|"moderate"|"severe",
    "response": str,
    "reason": str,
    "needs_professional_help": bool,
    "keywords_found": list[str],
    "lexical_confidence": float
}}

For depression analysis, consider:
- Mild: Some symptoms but manageable daily life
- Moderate: Several symptoms affecting daily functioning
- Severe: Many symptoms with significant impairment or danger
"""

            logger.info(f"Sending prompt to LLM:\n{prompt}")
            response = self.client.chat.completions.create(
                model=GROQ_MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                timeout=10,
                response_format={"type": "json_object"}
            )
            raw_response = response.choices[0].message.content.strip()
            logger.info(f"Raw LLM output:\n{raw_response}")
            result = self._extract_json(raw_response)

            if not result or not isinstance(result, dict):
                logger.error("Invalid response format from LLM")
                result = {
                    "analysis_type": "unknown",
                    "is_depressed": False,
                    "confidence": lexical_confidence,
                    "severity": "mild",
                    "response": "I'm having trouble understanding right now.",
                    "reason": "LLM returned invalid format",
                    "needs_professional_help": False,
                    "keywords_found": [],
                    "lexical_confidence": lexical_confidence
                }

            # Combine lexical and semantic confidence
            if 'confidence' in result and isinstance(result['confidence'], (int, float)):
                final_confidence = (lexical_confidence + result['confidence']) / 2
                result['confidence'] = round(final_confidence, 2)
                result['lexical_confidence'] = lexical_confidence
            else:
                result['confidence'] = lexical_confidence
                result['lexical_confidence'] = lexical_confidence

            # Validate and set default values for required fields
            required_fields = {
                "analysis_type": "unknown",
                "is_depressed": False,
                "severity": "mild",
                "response": "Let's continue our conversation.",
                "reason": "Incomplete response from AI",
                "needs_professional_help": False,
                "keywords_found": [],
                "lexical_confidence": lexical_confidence
            }

            for field, default in required_fields.items():
                if field not in result:
                    result[field] = default

            self.conversation_history.append({
                "input": text,
                "output": result["response"]
            })
            return result

        except Exception as e:
            logger.exception("LLM analysis failed")
            return {
                "analysis_type": "error",
                "is_depressed": False,
                "confidence": 0.5,
                "severity": "mild",
                "response": "Let's continue our conversation.",
                "reason": "Error occurred",
                "needs_professional_help": False,
                "keywords_found": [],
                "lexical_confidence": 0.5
            }
