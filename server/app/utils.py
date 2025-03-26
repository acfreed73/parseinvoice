import json
import re

def clean_json_output(stderr_text):
    """Extracts and formats valid JSON from invoice2data stderr output."""
    match = re.search(r"(\{.*\})", stderr_text, re.DOTALL)

    if not match:
        return None  # No valid JSON found

    raw_text = match.group(0)

    # Fix datetime issues
    raw_text = re.sub(
        r"datetime\.datetime\((\d{4}),\s*(\d{1,2}),\s*(\d{1,2}),\s*0,\s*0\)",
        r'"\1-\2-\3"',
        raw_text
    )

    raw_text = raw_text.replace("'", '"')

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        return None
