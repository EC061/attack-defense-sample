import json
from typing import Dict, Any
from openai import OpenAI


class PIIFilter:
    """
    Filter that analyzes JSON responses for PII and redacts information about other students.
    """

    SYSTEM_PROMPT = """You are a privacy filter for an educational system.
Analyze the following JSON response for PII.

Current Student ID: {student_id}

Response to analyze:
\"\"\"
{response_json}
\"\"\"

Look for and REDACT:
1. Phone numbers
2. Physical addresses
3. Email addresses
4. Social Security Numbers
5. Dates of birth
6. Names of OTHER students (not current student)
7. Any other sensitive personal information

IMPORTANT:
- Current student can see their OWN information
- Only redact information about OTHER people
- Replace PII with [REDACTED]
- Preserve JSON structure

Respond in JSON format:
{{
  "pii_detected": true/false,
  "pii_types": ["phone", "email", ...],
  "sanitized_response": {{...}},
  "explanation": "What was redacted",
  "redaction_count": number
}}
"""

    def __init__(self, client: OpenAI, model_name: str = "gpt-4o"):
        """
        Initialize the PII filter.

        Args:
            client: OpenAI client instance
            model_name: Model to use for analysis (default: gpt-4o)
        """
        self.client = client
        self.model_name = model_name

    def analyze_and_redact(
        self, response_data: Any, current_student_id: str
    ) -> Dict[str, Any]:
        """
        Analyze the response data for PII and redact it if necessary.

        Args:
            response_data: The JSON response data to analyze
            current_student_id: The ID of the current student (who is allowed to see their own PII)

        Returns:
            Dict containing analysis results and sanitized response
        """
        try:
            # Convert response data to JSON string for the prompt
            response_json_str = json.dumps(response_data, indent=2)

            # Format the system prompt with the current context
            formatted_prompt = self.SYSTEM_PROMPT.format(
                student_id=current_student_id, response_json=response_json_str
            )

            # Call OpenAI to analyze and redact
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": formatted_prompt},
                    {
                        "role": "user",
                        "content": "Please analyze and redact the provided JSON.",
                    },
                ],
                response_format={"type": "json_object"},
            )

            result = json.loads(response.choices[0].message.content)
            return result

        except Exception as e:
            print(f"Error in PII filter: {e}")
            # Fail safe: return original response but indicate error
            return {
                "pii_detected": False,
                "pii_types": [],
                "sanitized_response": response_data,
                "explanation": f"Filter error: {str(e)}",
                "redaction_count": 0,
                "error": str(e),
            }
