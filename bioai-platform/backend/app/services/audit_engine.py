import json
import logging
import os
from app.services.supabase import get_supabase
from app.config import settings

logger = logging.getLogger(__name__)

AUDIT_MODEL = "groq/llama-3.3-70b-versatile"

ANALYSIS_PROMPT = """
You are an intelligent observability engine for BioNexus, a bioinformatics SaaS platform.
Below is the ordered sequence of events from a user session.

Your job:
1. Identify what the user is trying to accomplish
2. Find any steps that failed, produced unexpected output, or took unusually long
3. Detect patterns — e.g. user retried the same step 3 times, or a tool returned 0 results silently
4. Output a JSON object with this exact shape:

{
  "severity": "info" | "warning" | "critical",
  "insight": "Plain-language summary of what happened in this session",
  "affected_steps": ["step_name_1", "step_name_2"],
  "suggestion": "What should be fixed or what the user should try next",
  "anomalies": ["list of specific anomalies detected"]
}

Session events:
{events_json}

Return ONLY the JSON object. No markdown, no preamble.
"""


def run_audit(session_id: str, triggered_by: str | None = None) -> None:
    sb = get_supabase()
    resp = sb.table("audit_events") \
        .select("*") \
        .eq("session_id", session_id) \
        .order("timestamp") \
        .execute()

    events = resp.data
    if not events:
        return

    try:
        import litellm
        response = litellm.completion(
            model=AUDIT_MODEL,
            messages=[{
                "role": "user",
                "content": ANALYSIS_PROMPT.format(
                    events_json=json.dumps(events, indent=2, default=str)
                ),
            }],
            max_tokens=1000,
            temperature=0.1,
            api_key=settings.GROQ_API_KEY,
        )

        raw = response.choices[0].message.content.strip()
        insight_data = json.loads(raw)

        sb.table("audit_insights").insert({
            "session_id": session_id,
            "triggered_by": triggered_by,
            "severity": insight_data.get("severity", "info"),
            "insight": insight_data.get("insight", ""),
            "affected_steps": insight_data.get("affected_steps", []),
            "suggestion": insight_data.get("suggestion", ""),
            "raw_audit": {"events": events, "anomalies": insight_data.get("anomalies", [])},
        }).execute()

        logger.info(f"Audit insight stored for session {session_id[:8]}...")
    except Exception as e:
        logger.warning(f"Audit engine failed for session {session_id[:8]}...: {e}")
