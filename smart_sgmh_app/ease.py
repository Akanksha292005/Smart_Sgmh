"""Ease-of-use layer for a FREE GOVERNMENT hospital whose patients are mostly poor and middle-class families:
 - everything visible after login: one 'What do you need today?' grid with big tiles (Hindi/English) on /home, and public tiles on the login page;
 - a clear 'all services are free, do not pay anyone' notice (set FREE_SERVICES=0 to switch it off if some service is charged);
 - Hindi first on the login page for a new visitor; bigger-text switch (A+); speak-instead-of-type (mic) on the symptom and assistant boxes; 'no phone? come to the counter' note.
SAMPLE / to confirm: the 'free' claim comes from the hospital; change FREE_NOTE if your rules differ."""
import os
from flask import session, request

FREE = os.environ.get("FREE_SERVICES", "1") == "1"
FREE_NOTE = "All services at this government hospital are free. Do not pay anyone for an appointment, slip, bed or report. If anyone asks for money, tell the help desk: 07662-241655."

def register(ns):
    app = ns["app"]
    from i18n import HI
    from i18n_ease import EASE_HI
    for k, v in EASE_HI.items(): HI.setdefault(k, v)
    import registration
    if FREE: registration.FEE_NOTE = FREE_NOTE   # the booking page shows this instead of 'fee, if any, is paid at the counter'
    app.context_processor(lambda: dict(free_services=FREE, free_note=FREE_NOTE))

    @app.before_request
    def hindi_first():   # a first-time visitor to the login page sees Hindi; the language switch stays on the page
        if request.method == "GET" and request.path == "/start" and "lang" not in session: session["lang"] = "hi"
