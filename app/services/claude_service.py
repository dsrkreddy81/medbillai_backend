"""Claude AI integration service for neurology CPT + ICD-10 code extraction."""

import json

import anthropic

from app.config import settings
from app.schemas.extraction import ExtractionResult

SYSTEM_PROMPT = """You are an expert neurology medical coder and billing specialist. Your role is to analyze clinical documentation from neurology practices and extract both CPT (Current Procedural Terminology) codes and ICD-10 diagnosis codes.

You have deep expertise in:
- Neurology-specific CPT codes (EEG, EMG, nerve conduction studies, sleep studies, evoked potentials, autonomic testing, neurostimulator programming, TMS, etc.)
- Evaluation and Management (E/M) coding for neurology office and hospital visits
- Interventional neurology procedures (nerve blocks, botulinum toxin injections, lumbar punctures)
- Neuropsychological and neurobehavioral testing codes
- Cerebrovascular ultrasound and transcranial Doppler codes
- ICD-10-CM diagnosis codes for neurological conditions (epilepsy G40.x, migraine G43.x, Parkinson G20, MS G35, neuropathy G60-G65, stroke I63.x, dementia G30.x, sleep disorders G47.x, etc.)
- Proper documentation requirements for each code
- Medical necessity and supporting documentation

When analyzing clinical notes, you must:
1. Identify ALL procedures and services documented -> CPT codes
2. Identify ALL diagnoses documented -> ICD-10 codes
3. Map each to the most specific and accurate code
4. Extract the exact clinical text that supports each code
5. Assess your confidence level (0.0-1.0) based on documentation clarity
6. Mark the primary diagnosis (the main reason for the encounter)
7. Generate a concise clinical summary
8. Create a billing narrative that justifies medical necessity

Important coding rules:
- Only assign codes that are clearly supported by the documentation
- Use the most specific ICD-10 code possible (e.g., G40.309 not G40.9)
- Consider time-based vs. complexity-based E/M coding
- Account for bilateral vs. unilateral procedures
- The primary diagnosis should be the main condition treated during the visit
- If a procedure is mentioned but not sufficiently documented, assign lower confidence"""

EXTRACTION_TOOL = {
    "name": "submit_extraction",
    "description": "Submit the extracted CPT codes, ICD-10 diagnoses, and billing information from the clinical document.",
    "input_schema": {
        "type": "object",
        "properties": {
            "patient_name": {
                "type": "string",
                "description": "Patient's full name as found in the document, or null if not found"
            },
            "date_of_service": {
                "type": "string",
                "description": "Date of service in YYYY-MM-DD format, or null if not found"
            },
            "provider_name": {
                "type": "string",
                "description": "Treating/ordering provider's name, or null if not found"
            },
            "clinical_summary": {
                "type": "string",
                "description": "A concise 2-4 sentence summary of the clinical encounter, including chief complaint, key findings, and diagnoses"
            },
            "procedures": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "cpt_code": {
                            "type": "string",
                            "description": "The CPT code (e.g., '95819')"
                        },
                        "description": {
                            "type": "string",
                            "description": "Description of the procedure/service"
                        },
                        "supporting_text": {
                            "type": "string",
                            "description": "Exact text from the document that supports this code"
                        },
                        "confidence": {
                            "type": "number",
                            "description": "Confidence score from 0.0 to 1.0"
                        }
                    },
                    "required": ["cpt_code", "description", "supporting_text", "confidence"]
                },
                "description": "List of identified CPT codes with supporting evidence"
            },
            "diagnoses": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "icd10_code": {
                            "type": "string",
                            "description": "The ICD-10-CM code (e.g., 'G40.309')"
                        },
                        "description": {
                            "type": "string",
                            "description": "Description of the diagnosis"
                        },
                        "supporting_text": {
                            "type": "string",
                            "description": "Exact text from the document that supports this diagnosis"
                        },
                        "confidence": {
                            "type": "number",
                            "description": "Confidence score from 0.0 to 1.0"
                        },
                        "is_primary": {
                            "type": "boolean",
                            "description": "Whether this is the primary/principal diagnosis for the encounter"
                        }
                    },
                    "required": ["icd10_code", "description", "supporting_text", "confidence", "is_primary"]
                },
                "description": "List of identified ICD-10 diagnosis codes"
            },
            "billing_narrative": {
                "type": "string",
                "description": "A professional billing narrative justifying medical necessity, suitable for insurance submission."
            }
        },
        "required": ["clinical_summary", "procedures", "diagnoses", "billing_narrative"]
    }
}


async def extract_cpt_codes(clinical_text: str) -> ExtractionResult:
    """Send clinical text to Claude API and extract CPT + ICD-10 codes.

    Args:
        clinical_text: The full extracted text from the clinical PDF.

    Returns:
        ExtractionResult with patient info, CPT codes, ICD-10 codes, and billing narrative.
    """
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    user_message = f"""Analyze the following neurology clinical document and extract all applicable CPT codes and ICD-10 diagnosis codes. Use the submit_extraction tool to provide your results.

CLINICAL DOCUMENT:
---
{clinical_text}
---

Instructions:
- Identify every billable procedure/service -> assign CPT codes
- Identify every diagnosis/condition -> assign ICD-10 codes
- Mark the primary diagnosis (main reason for the encounter)
- For each code, provide description, exact supporting text, and confidence level
- Generate a clinical summary and billing narrative
- Extract patient name, date of service, and provider name if available"""

    response = await client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=4096,
        temperature=0,
        system=SYSTEM_PROMPT,
        tools=[EXTRACTION_TOOL],
        messages=[{"role": "user", "content": user_message}],
    )

    # Extract the tool use result
    for block in response.content:
        if block.type == "tool_use" and block.name == "submit_extraction":
            return ExtractionResult(**block.input)

    # Fallback: if no tool use, try to parse from text
    for block in response.content:
        if block.type == "text":
            try:
                data = json.loads(block.text)
                return ExtractionResult(**data)
            except (json.JSONDecodeError, ValueError):
                pass

    raise ValueError("Claude did not return a valid extraction result")
