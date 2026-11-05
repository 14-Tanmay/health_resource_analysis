
import json
import os
from groq import Groq


MODEL = "openai/gpt-oss-120b"


def _get_groq_client():

    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        try:
            import streamlit as st
            api_key = st.secrets.get("GROQ_API_KEY")
        except Exception:
            api_key = None

    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not found."
        )

    return Groq(api_key=api_key)


def _build_system_prompt():

    return """
You are an expert healthcare accessibility and resource
allocation analyst.

Analyze the supplied geographic healthcare priority data
and generate concise, evidence-based findings and
planning recommendations.

STRICT DATA RULES:

1. Use only the supplied input data.
2. Never invent population, hospital, bed, distance,
   score or geographic information.
3. Never modify or recalculate priority scores.
4. Do not invent numerical resource requirements.
5. Never prescribe an exact number of additional beds,
   hospitals, PHCs, CHCs or healthcare staff unless
   that exact requirement is explicitly supported by
   the input data.
6. Never invent budgets, response times, travel-time
   targets or infrastructure capacities.
7. Zero recorded facilities means no facility is
   recorded in the supplied dataset. Do not claim
   that no real-world facility exists.
8. Distinguish hospitals from other healthcare facilities.
9. Preserve the distinction between nearest-hospital
   distance and nearest-healthcare-facility distance.
10. Interpret priority tiers only within their respective
    geographic analysis levels.
11. Equal numbers of areas in priority tiers must not
    be interpreted as evidence of equal healthcare need.

KEY FINDINGS:

1. Generate 3-5 concise findings for each analysis level.
2. Identify important high-priority areas by their actual names.
3. Explain the healthcare resource gaps indicated by the model.
4. Consider population, hospital availability, public/private
   facilities, beds, distance and availability gaps.
5. Do not describe a relatively short distance as a major
   distance barrier without supporting evidence.
6. Explain whether the dominant concern is local facility
   availability, public healthcare provision, bed capacity
   or geographical accessibility.

PLANNING RECOMMENDATIONS:

1. Generate 3-5 concise, actionable recommendations.
2. Every recommendation must follow directly from a finding.
3. Suggest appropriate resources such as:
   - New public hospitals
   - Additional hospital beds
   - PHCs and CHCs
   - Public outpatient facilities
   - Diagnostic services
   - Primary healthcare outreach
   - Emergency referral connectivity
4. Specify the actual area for each recommendation.
5. Do not recommend exact numerical capacities unless
   supported by the supplied data.
6. If an area has zero recorded population, do not recommend
   permanent infrastructure or assume that residents live there.
7. If an area has no recorded local hospital but a relatively
   nearby facility, focus on local service availability
   and public healthcare provision rather than claiming
   extreme geographical isolation.
8. Avoid generic statements such as:
   "Review the situation", "Conduct further analysis",
   "Verify the data" or "Improve healthcare facilities".
9. Do not recommend unnecessary hospital construction
   where strengthening existing healthcare capacity
   is more directly supported by the findings.

FINAL INTERPRETATION:

Write a concise paragraph of 2-3 sentences explaining
the overall healthcare resource situation in that
geographic analysis level.

WRITING STYLE:

- Formal academic language.
- Concise sentences.
- Specific geographic names.
- No unnecessary explanations.
- No introduction, methodology or limitations section.

Return valid JSON only, using this structure:

{
    "city": "City name",
    "analysis_levels": [
        {
            "level_name": "Geographic analysis level",
            "key_findings": [
                "Finding 1"
            ],
            "planning_recommendations": [
                "Recommendation 1"
            ],
            "final_interpretation": "Short interpretation."
        }
    ]
}
"""


def _build_user_prompt(city_data):

    return f"""
Generate the healthcare accessibility report analysis
for the following city.

ACTUAL MODEL OUTPUT DATA:

{json.dumps(city_data, indent=2, ensure_ascii=False)}

Analyze every geographic level separately.

For each level:

1. Identify the most important healthcare resource gaps.
2. Identify the highest-priority areas.
3. Interpret hospital and bed availability.
4. Interpret public and private healthcare gaps.
5. Interpret nearest-facility distances correctly.
6. Recommend specific healthcare resources for
   the identified areas.
7. Keep all findings and recommendations concise.

IMPORTANT:

Do not create numerical infrastructure requirements
that are absent from the data.

Do not treat zero population as evidence of a residential
healthcare demand.

Do not confuse the nearest healthcare facility with
the nearest hospital.

Return only the required JSON.
"""


def _validate_response(data, city, city_data):

    if not isinstance(data, dict):
        raise ValueError("Invalid JSON response.")

    if "analysis_levels" not in data:
        raise ValueError("Missing analysis_levels.")

    if not isinstance(data["analysis_levels"], list):
        raise ValueError("analysis_levels must be a list.")

    expected_levels = [
        level["level_name"]
        for level in city_data["analysis_levels"]
    ]

    received_levels = [
        level.get("level_name")
        for level in data["analysis_levels"]
    ]

    if received_levels != expected_levels:
        raise ValueError(
            "The LLM response does not match the "
            "city's expected geographic analysis levels."
        )

    for level in data["analysis_levels"]:

        required_fields = [
            "level_name",
            "key_findings",
            "planning_recommendations",
            "final_interpretation"
        ]

        for field in required_fields:
            if field not in level:
                raise ValueError(
                    f"Missing field: {field}"
                )

        if not isinstance(level["key_findings"], list):
            raise ValueError("key_findings must be a list.")

        if not isinstance(
            level["planning_recommendations"], list
        ):
            raise ValueError(
                "planning_recommendations must be a list."
            )

        if not level["key_findings"]:
            raise ValueError("No key findings generated.")

        if not level["planning_recommendations"]:
            raise ValueError(
                "No planning recommendations generated."
            )

        if not isinstance(
            level["final_interpretation"], str
        ):
            raise ValueError(
                "Invalid final interpretation."
            )

    data["city"] = city

    return data


def generate_city_analysis(city_data):

    if not isinstance(city_data, dict):
        raise ValueError("city_data must be a dictionary.")

    city = city_data.get("city")

    if not city:
        raise ValueError("City name is missing.")

    client = _get_groq_client()

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": _build_system_prompt()
            },
            {
                "role": "user",
                "content": _build_user_prompt(city_data)
            }
        ],
        response_format={
            "type": "json_object"
        },
        max_completion_tokens=5000
    )

    content = response.choices[0].message.content

    if not content:
        raise ValueError("Groq returned an empty response.")

    try:
        result = json.loads(content)
    except json.JSONDecodeError as error:
        raise ValueError(
            f"Invalid Groq JSON response: {error}"
        )

    return _validate_response(
        result,
        city,
        city_data
    )
