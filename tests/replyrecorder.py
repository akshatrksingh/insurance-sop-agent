"""Records every reply produced by handle_turn anywhere in the suite, with the context needed to scan it."""
import re

import insurance_claims.orchestrator as orchestrator

# Test side copy of the emotion floor phrases (CP6). A message holding one counts as intensity 2 for the scans.
FLOOR_PHRASES = ['ridiculous', 'useless', 'unacceptable', 'i already told you', 'this is a joke', 'fed up', 'sick of this',
                 'waste of time', 'outrageous', 'unbelievable']
FLOOR_RE = re.compile(r'(?<!\w)(' + '|'.join(re.escape(p) for p in FLOOR_PHRASES) + r')(?!\w)', re.I)
NEGATIVE = ('frustration', 'anger', 'anxiety')

RECORDS = []
_original = orchestrator.handle_turn


def _emotion(extraction):
    """(label, intensity) from an Extraction object or dict, ('neutral', 0) if unreadable."""
    try:
        emotion = extraction['emotion'] if isinstance(extraction, dict) else extraction.emotion
        get = (lambda k: emotion[k]) if isinstance(emotion, dict) else (lambda k: getattr(emotion, k))
        return str(get('label')), int(get('intensity'))
    except Exception:
        return 'neutral', 0


def _intensity(extraction):
    """Emotion intensity from an Extraction object or dict, 0 if unreadable."""
    return _emotion(extraction)[1]


def recording_handle_turn(session, text, llm):
    """Call the real handle_turn and record the reply with its context."""
    box = {'intensity': 0, 'label': 'neutral'}
    original_extract = getattr(llm, 'extract', None)

    def extract(*a, **k):
        """Call the real extract and note the emotion intensity."""
        out = original_extract(*a, **k)
        box['label'], box['intensity'] = _emotion(out)
        return out

    try:
        prior = sum(1 for role, _ in session.view().turns if role == 'Agent')
        turns_before, was_verified = sum(1 for r, _ in session.view().turns if r == 'Caller'), session.view().phase != 'VERIFY_ID'
        llm.extract = extract
    except Exception:
        prior, turns_before, was_verified = 0, 0, False
    try:
        result = _original(session, text, llm)
    finally:
        try:
            del llm.extract
        except Exception:
            pass
    if FLOOR_RE.search(text or ''):
        box['intensity'] = max(box['intensity'], 2)
        box['label'] = box['label'] if box['label'] in NEGATIVE else 'frustration'
    rows = session.view().model_dump()['memory_rows']
    strikes = next((int(r['value']) for r in rows if r['label'] == 'Off-topic strikes'), 0)
    RECORDS.append({'reply': result.reply, 'prior_agent': prior, 'intensity': box['intensity'],
                    'confirmed': sum(1 for r in rows if r['value'] == 'matched'),
                    'matched_labels': [r['label'] for r in rows if r['value'] == 'matched'],
                    'verified': session.view().phase != 'VERIFY_ID', 'was_verified': was_verified,
                    'label': box['label'], 'strikes': strikes, 'rejected': sum(1 for r, _ in session.view().turns if r == 'Caller') == turns_before})
    return result


def install():
    """Replace orchestrator.handle_turn with the recording wrapper (idempotent)."""
    orchestrator.handle_turn = recording_handle_turn
