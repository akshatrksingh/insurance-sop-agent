"""Follow-up guidance from required_document_guideline.json (CASE-02, CASE-03).

Matching is deterministic: the topic's intent hints, then its phrases against the caller's message.
Templates are filled from the claim record and the guideline file only. No model text is used.
"""

import json
import re
from functools import lru_cache

from insurance_claims.data import FIXTURES
from insurance_claims.fields import mentions_field
from insurance_claims.grounded import join_items

DOC_WORDS = re.compile(r'\b(?:submit|send|upload|sent|files|format|documents?|paperwork|portal|fax|mail|receipt|confirm\w*)\b', re.I)
CANNOT_OBTAIN = re.compile(
    r"\b(?:can(?:'|’)?t|cannot|can not|unable to|not able to|won(?:'|’)?t be able to|no way to)\s+"
    r"(?:get|find|obtain|locate|provide|track down|give)\b"
    r"|\b(?:don(?:'|’)?t|do not|doesn(?:'|’)?t|does not) (?:have|possess)\b|\b(?:lost|misplaced)\b",
    re.I,
)
OTHER_ITEM = re.compile(r'\b(?:reports?|notes?|documents?|paperwork|records?|estimates?|photos?|copy|copies)\b', re.I)
HUMAN_QUESTION = 'Would you like me to connect you with a human representative?'
FORMAT_TOPIC = 'file_format_requirements'


@lru_cache(maxsize=1)
def load_guideline() -> dict:
    """Load the guideline fixture once."""
    return json.loads((FIXTURES / 'required_document_guideline.json').read_text(encoding='utf-8'))


def _clean(text: str) -> str:
    """Drop the word 'please' from fixture text, which system copy never uses."""
    return re.sub(r'\bplease\s+', '', text, flags=re.I)


def _phrase_hit(message: str, phrases: list[str]) -> bool:
    """True when any phrase appears in the message as whole words."""
    low = re.sub(r'\s+', ' ', message.casefold())
    return any(re.search(rf'\b{re.escape(p)}\b', low) for p in phrases)


def _doc_texts(documents: list[str], table: dict) -> list[str]:
    """Return the guideline text for each needed document, or none when the file has no entry for it."""
    out = []
    for doc in documents:
        for key, value in table.items():
            if key != 'default' and doc.casefold() in key.casefold():
                out.append(_clean(value['en']))
                break
    return out


def _named_docs(claim: dict, message: str) -> list[str]:
    """Return the needed documents the message names, matched on whole words of the document name."""
    low = message.casefold()
    return [d for d in claim.get('documents_needed') or [] if re.search(rf'\b{re.escape(d.casefold())}s?\b', low)]


def cannot_obtain(claim: dict, message: str) -> bool:
    """True when the caller says a requested item cannot be obtained (CASE-03)."""
    return bool(claim.get('documents_needed')) and bool(CANNOT_OBTAIN.search(message)) and bool(OTHER_ITEM.search(message))


def alternatives(claim: dict, message: str) -> dict:
    """Return the guideline alternatives for the item the caller cannot get, with the human recommendation."""
    guide = load_guideline()['document_alternative_guidance']
    docs = _named_docs(claim, message)
    texts = _doc_texts(docs, guide) or [_clean(guide['default']['en'])]
    texts.append(HUMAN_QUESTION)
    return {'topic': 'document_alternatives', 'texts': texts, 'human': True}


def get_guidance(claim: dict, intent: str | None, message: str) -> dict | None:
    """Pick follow-up guidance for a resolved claim by intent and phrases.

    Args:
        claim: The resolved claim (curated, owned by the verified party).
        intent: The session intent, or None.
        message: The caller's message.

    Returns:
        A dict with `topic`, `texts` (the strings to say) and `human` (True when a human representative
        is recommended), the fallback when the message is a document follow-up that no topic matches, or
        None when the message is not a document follow-up at all.
    """
    guide = load_guideline()
    docs = claim.get('documents_needed') or []
    if cannot_obtain(claim, message):
        return alternatives(claim, message)
    intents = {intent, 'document_submission'} if DOC_WORDS.search(message) else {intent}
    values = {
        'case_id': claim['case_id'],
        'documents': join_items(docs),
        'average_processing_time_after_submission': guide['claim_followup_settings'][
            'average_processing_time_after_submission']['en'],
    }
    for topic in guide['claim_followup_guidance']:
        phrases = topic.get('match_any')
        if not phrases or (topic.get('requires_documents') and not docs):
            continue
        if intents.isdisjoint(topic['intent_hints']) or not _phrase_hit(message, phrases):
            continue
        texts = [_clean(re.sub(r'\{(\w+)\}', lambda m: values.get(m.group(1), m.group(0)), topic['en']))]
        if topic['topic'] == FORMAT_TOPIC:
            texts += _doc_texts(docs, guide['document_guidance'])
        return {'topic': topic['topic'], 'texts': texts, 'human': False}
    if DOC_WORDS.search(message) and docs and not mentions_field(message):  # field questions keep their own path
        return {'topic': 'fallback', 'texts': [_clean(guide['claim_followup_fallback']['en'])], 'human': False}
    return None
