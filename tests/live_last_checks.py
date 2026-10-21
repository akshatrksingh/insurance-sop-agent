"""Code checks for live_last.py. Each takes per turn records (with a strikes field) and returns failure strings."""
from live_final_checks import kinds_text, reaches


def strikes(recs):
    """Strikes 1, 2, 3 on the first three turns, the human offer on the third, ESCALATED with a handoff after yes."""
    bad = ['turn ' + str(i) + ': strikes ' + str(r['strikes']) + ' expected ' + str(i) for i, r in enumerate(recs[:3], 1) if r['strikes'] != i]
    if 'human representative' not in recs[2]['reply'].lower():
        bad.append('third reply lacks the human offer')
    if recs[-1]['phase'] != 'ESCALATED' or 'handed off' not in kinds_text(recs[-1]):
        bad.append('no handoff after yes')
    return bad


def send(recs):
    """The offer opens, then a plain yes gives a preview to the email on file and an Email sent event."""
    r = recs[-1]
    bad = [] if recs[1]['offer_open'] else ['no email offer after the closing message']
    if not r['preview_present'] or not r['preview_to_on_file'] or 'email sent' not in kinds_text(r):
        bad.append('send path: no preview, wrong recipient or no Email sent event')
    return bad + reaches(recs, ('COMPLETE',), 'send path')


def skip(recs):
    """no thanks gives no preview and a Skipped event."""
    r = recs[-1]
    bad = ['preview present or no Skipped event'] if r['preview_present'] or 'skipped email summary' not in kinds_text(r) else []
    return bad + reaches(recs, ('COMPLETE',), 'skip path')
