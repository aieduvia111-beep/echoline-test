from flask import Flask, request, Response, session, redirect, url_for, render_template_string
import requests
import os
import json
import time
from datetime import datetime

import firebase_admin
from firebase_admin import credentials, firestore as admin_firestore
import stripe

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-key-zmien-to")

ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")

bot_instructions = {"text": "Umawiaj wizyty i podawaj cennik uslug."}

# --- Firebase Admin SDK (dostep do bazy danych z poziomu serwera) ---
FIREBASE_SA_JSON = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")
db_admin = None
if FIREBASE_SA_JSON:
    try:
        cred = credentials.Certificate(json.loads(FIREBASE_SA_JSON))
        firebase_admin.initialize_app(cred)
        db_admin = admin_firestore.client()
    except Exception as e:
        print("Blad inicjalizacji Firebase Admin:", e)

# --- Stripe (weryfikacja prawdziwych platnosci przez webhook) ---
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "")
if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY

# Mapowanie Price ID (Stripe) -> nazwa planu w naszym systemie
PLAN_PRICE_MAP = {
    "price_1TqWYDD1RWr87QNI27P77SlD": "start",
    "price_1TqWZwD1RWr87QNI55CEgojL": "pro",
    "price_1TqWaWD1RWr87QNIT7rygCGy": "firma",
}

# --- Jezyki, w ktorych moze rozmawiac bot (kod Twilio dla rozpoznawania mowy + instrukcje dla AI) ---
BOT_LANGUAGES = {
    "pl": {
        "twilio": "pl-PL",
        "instruction": "Rozmawiaj WYLACZNIE po polsku.",
        "greeting_disclosure": "Rozmowa moze byc transkrybowana.",
        "no_response": "Nie uslyszalem odpowiedzi. Dziekuje za telefon, do uslyszenia.",
        "limit_before": "Dzien dobry, przepraszam, ale w tej chwili nie moge przyjac polaczenia. Prosze sprobowac zadzwonic pozniej, lub napisac wiadomosc. Dziekuje.",
        "limit_during": "Dziekuje bardzo za rozmowe. To wszystkie informacje jakie mam w tej chwili - w razie dodatkowych pytan prosze o kontakt bezposredni. Milego dnia, do uslyszenia.",
        "session_expired": "Sesja wygasla.",
        "error": "Wystapil blad.",
        "stall": "Chwileczke, sprawdzam to dla Pana/Pani.",
        "hint_fallback": "Przepraszam za oczekiwanie. Postaram sie to sprawdzic i oddzwonic w tej sprawie. Czy moge pomoc w czyms jeszcze?",
        "greeting_with_company": "Dzien dobry, tu automatyczny asystent AI dzialajacy w imieniu {company}.",
        "greeting_generic": "Dzien dobry, tu automatyczny asystent AI.",
        "greeting_suffix": "Slucham, w czym moge pomoc?",
    },
    "en": {
        "twilio": "en-US",
        "instruction": "Speak ONLY in English.",
        "greeting_disclosure": "This call may be transcribed.",
        "no_response": "I did not hear a response. Thank you for calling, goodbye.",
        "limit_before": "Hello, I am sorry but I cannot take calls right now. Please try again later, or send a message. Thank you.",
        "limit_during": "Thank you very much for the call. That is all the information I have right now - for further questions please contact us directly. Have a nice day, goodbye.",
        "session_expired": "The session has expired.",
        "error": "An error occurred.",
        "stall": "One moment, let me check that for you.",
        "hint_fallback": "Sorry for the wait. I will look into this and get back to you. Can I help with anything else?",
        "greeting_with_company": "Hello, this is an automated AI assistant on behalf of {company}.",
        "greeting_generic": "Hello, this is an automated AI assistant.",
        "greeting_suffix": "How can I help you?",
    },
    "de": {
        "twilio": "de-DE",
        "instruction": "Sprich AUSSCHLIESSLICH auf Deutsch.",
        "greeting_disclosure": "Dieses Gespraech kann aufgezeichnet werden.",
        "no_response": "Ich habe keine Antwort gehoert. Danke fuer Ihren Anruf, auf Wiederhoeren.",
        "limit_before": "Guten Tag, es tut mir leid, aber ich kann derzeit keine Anrufe entgegennehmen. Bitte versuchen Sie es spaeter erneut. Danke.",
        "limit_during": "Vielen Dank fuer das Gespraech. Das sind alle Informationen, die ich derzeit habe - bei weiteren Fragen kontaktieren Sie uns bitte direkt. Einen schoenen Tag noch, auf Wiederhoeren.",
        "session_expired": "Die Sitzung ist abgelaufen.",
        "error": "Ein Fehler ist aufgetreten.",
        "stall": "Einen Moment bitte, ich pruefe das fuer Sie.",
        "hint_fallback": "Entschuldigen Sie die Wartezeit. Ich werde das pruefen und mich zurueckmelden. Kann ich sonst noch helfen?",
        "greeting_with_company": "Guten Tag, hier ist der automatische KI-Assistent im Auftrag von {company}.",
        "greeting_generic": "Guten Tag, hier ist der automatische KI-Assistent.",
        "greeting_suffix": "Wie kann ich Ihnen helfen?",
    },
}


def get_bot_language(user_data):
    """Zwraca slownik jezyka bota (domyslnie polski) na podstawie profilu uzytkownika."""
    lang_code = (user_data or {}).get("botLanguage", "pl")
    return BOT_LANGUAGES.get(lang_code, BOT_LANGUAGES["pl"])


# --- Limity per plan (minuty rozmow miesiecznie, liczba zlecen "Zadzwon za mnie") ---
PLAN_LIMITS = {
    "free":  {"minutes": 0,    "quick_calls": 0},
    "start": {"minutes": 100,  "quick_calls": 5},
    "pro":   {"minutes": 400,  "quick_calls": 30},
    "firma": {"minutes": 1000, "quick_calls": 999},
}


def get_user_doc_by_uid(uid):
    """Pobiera dane uzytkownika z bazy po jego UID."""
    if not db_admin or not uid:
        return None
    doc = db_admin.collection("users").document(uid).get()
    return doc.to_dict() if doc.exists else None


def get_user_by_phone(phone_number):
    """Znajduje wlasciciela danego numeru telefonu w bazie. Zwraca (uid, dane) albo (None, None)."""
    if not db_admin or not phone_number:
        return None, None
    query = db_admin.collection("users").where("phoneNumber", "==", phone_number).limit(1).stream()
    for doc in query:
        return doc.id, doc.to_dict()
    return None, None


def get_user_calls(uid, limit=50):
    """Pobiera prawdziwe rozmowy danego uzytkownika z bazy, posortowane od najnowszej."""
    if not db_admin or not uid:
        return []
    try:
        query = (
            db_admin.collection("calls")
            .where("uid", "==", uid)
            .order_by("created_at", direction=admin_firestore.Query.DESCENDING)
            .limit(limit)
            .stream()
        )
        results = []
        for doc in query:
            d = doc.to_dict()
            created = d.get("created_at", "")
            try:
                dt = datetime.fromisoformat(created)
                data_str = dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                data_str = created
            other_number = d.get("from_number") if d.get("call_type") == "incoming" else d.get("to_number")
            results.append({
                "data": data_str,
                "z_kim": other_number or "Nieznany numer",
                "podsumowanie": d.get("summary", ""),
                "call_type": d.get("call_type", "incoming"),
            })
        return results
    except Exception as e:
        print("[get_user_calls] blad:", e)
        return []


def get_plan_limits(user_data):
    """
    WAZNE: limity dostepne sa tylko jesli subscriptionActive == True,
    czyli Stripe faktycznie potwierdzil oplacenie subskrypcji (przez webhook).
    Samo posiadanie pola "plan" w bazie NIE wystarczy - to zabezpiecza przed
    sytuacja, gdzie karta przestaje dzialac, a klient dalej mialby darmowy dostep.
    """
    user_data = user_data or {}
    if not user_data.get("subscriptionActive"):
        return PLAN_LIMITS["free"], "free"
    plan = user_data.get("plan", "free")
    return PLAN_LIMITS.get(plan, PLAN_LIMITS["free"]), plan


def minutes_available(user_data):
    limits, plan = get_plan_limits(user_data)
    used = (user_data or {}).get("minutesUsed", 0)
    return used < limits["minutes"], limits["minutes"], used, plan


def quick_calls_available(user_data):
    limits, plan = get_plan_limits(user_data)
    used = (user_data or {}).get("quickCallsUsed", 0)
    return used < limits["quick_calls"], limits["quick_calls"], used, plan


def send_email(to_email, subject, html_body):
    """Wysyla maila przez Resend. Zwraca True/False czy sie udalo."""
    if not RESEND_API_KEY or not to_email:
        return False
    url = "https://api.resend.com/emails"
    headers = {"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "from": "EchoLine <onboarding@resend.dev>",
        "to": [to_email],
        "subject": subject,
        "html": html_body,
    }
    r = requests.post(url, json=payload, headers=headers)
    return r.status_code == 200


def maybe_notify_low_usage(uid, user_data):
    """
    Sprawdza czy uzytkownikowi zostalo malo minut/zlecen (ponizej 20%) i jesli tak,
    wysyla JEDNORAZOWE ostrzezenie mailem (nie spamuje przy kazdej kolejnej rozmowie -
    flaga resetuje sie dopiero przy odnowieniu planu, patrz stripe_webhook).
    """
    if not db_admin or not uid or not user_data:
        return
    if not user_data.get("subscriptionActive"):
        return
    if user_data.get("lowUsageWarningSent"):
        return

    limits, plan = get_plan_limits(user_data)
    minutes_used = user_data.get("minutesUsed", 0)
    quick_calls_used = user_data.get("quickCallsUsed", 0)

    minutes_left_pct = (limits["minutes"] - minutes_used) / limits["minutes"] if limits["minutes"] > 0 else 1
    quick_calls_left_pct = (limits["quick_calls"] - quick_calls_used) / limits["quick_calls"] if limits["quick_calls"] > 0 else 1

    if minutes_left_pct <= 0.2 or quick_calls_left_pct <= 0.2:
        email = user_data.get("email")
        if email:
            minutes_left = max(round(limits["minutes"] - minutes_used), 0)
            html = f'''
            <div style="font-family:sans-serif;padding:20px;">
                <h2>Zbliżasz się do limitu na planie {plan}</h2>
                <p>Zostało Ci około <b>{minutes_left} minut</b> rozmów w tym cyklu rozliczeniowym.</p>
                <p>Aby uniknąć przerw w obsłudze klientów, rozważ zmianę planu na wyższy.</p>
                <p><a href="https://echoline-test.onrender.com/cennik">Zobacz plany</a></p>
            </div>
            '''
            sent = send_email(email, "EchoLine: zbliżasz się do limitu", html)
            if sent:
                db_admin.collection("users").document(uid).set({"lowUsageWarningSent": True}, merge=True)


def add_minutes_used(uid, minutes):
    if not db_admin or not uid or minutes <= 0:
        return
    ref = db_admin.collection("users").document(uid)
    ref.set({"minutesUsed": admin_firestore.Increment(minutes)}, merge=True)


def increment_quick_calls(uid):
    if not db_admin or not uid:
        return
    ref = db_admin.collection("users").document(uid)
    ref.set({"quickCallsUsed": admin_firestore.Increment(1)}, merge=True)

FAKE_CALLS = [
    {"data": "2026-07-05 14:20", "z_kim": "Warsztat Kowalski", "podsumowanie": "Umowiono termin naprawy na 15.07, godz. 10:00"},
    {"data": "2026-07-04 09:05", "z_kim": "Przychodnia Zdrowie", "podsumowanie": "Potwierdzono wizyte kontrolna na 20.07"},
]

FIREBASE_CONFIG = {
    "apiKey": "AIzaSyD-MwcAdAmIWfmqPvAALYs3kxfEnWk6Pmc",
    "authDomain": "echoline-d9fc8.firebaseapp.com",
    "projectId": "echoline-d9fc8",
    "storageBucket": "echoline-d9fc8.firebasestorage.app",
    "messagingSenderId": "119753376554",
    "appId": "1:119753376554:web:ff915f5d31ddabc1f29453",
}

LOGIN_PAGE = """
<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>EchoLine - logowanie</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
  *{box-sizing:border-box;margin:0;padding:0;}
  .bg-particles{position:fixed;inset:0;overflow:hidden;pointer-events:none;z-index:0;}
  .bg-particles span{position:absolute;bottom:-10px;border-radius:50%;background:#7c6aff;opacity:0;animation:floatDust linear infinite;}
  @keyframes floatDust{
    0%{transform:translateY(0) translateX(0);opacity:0;}
    10%{opacity:0.4;}
    90%{opacity:0.4;}
    100%{transform:translateY(-105vh) translateX(30px);opacity:0;}
  }
  .langbtn{border:1px solid #eee;background:#fff;color:#999;}
  .langbtn.active{background:#111;color:#fff;border-color:#111;}
  body{font-family:'Inter',sans-serif;background:#fff;color:#111;display:flex;flex-direction:column;align-items:center;padding:60px 20px;min-height:100vh;}
  .wrap{width:100%;max-width:360px;}
  .logo{text-align:center;font-size:16px;font-weight:800;margin-bottom:36px;letter-spacing:-0.01em;display:flex;align-items:center;justify-content:center;gap:8px;}
  .logo-dot{width:10px;height:10px;border-radius:50%;background:linear-gradient(135deg,#7c6aff,#22d3a0);flex-shrink:0;}
  h1{text-align:center;font-size:26px;font-weight:800;letter-spacing:-0.02em;margin-bottom:32px;}

  button.social{width:100%;padding:12px;border-radius:9px;border:1px solid #ddd;background:#fff;font-family:inherit;font-size:14px;font-weight:600;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:10px;margin-bottom:10px;}
  button.social:hover{background:#f7f7f7;}
  svg{width:17px;height:17px;flex-shrink:0;}

  .divider{display:flex;align-items:center;gap:10px;margin:20px 0;color:#bbb;font-size:12px;}
  .divider::before,.divider::after{content:"";flex:1;height:1px;background:#eee;}

  label{display:block;font-size:13.5px;font-weight:500;margin-bottom:6px;color:#333;}
  .row-label{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;}
  .row-label a{font-size:12.5px;color:#888;text-decoration:none;cursor:pointer;}
  .row-label a:hover{color:#111;text-decoration:underline;}

  .field{margin-bottom:14px;}
  .field input{width:100%;padding:11px 13px;border-radius:9px;border:1px solid #ddd;font-family:inherit;font-size:14px;outline:none;transition:border-color .15s;}
  .field input:focus{border-color:#111;}

  button.submit{width:100%;padding:12px;border-radius:9px;border:none;background:#7c6aff;color:#fff;font-family:inherit;font-size:14.5px;font-weight:600;cursor:pointer;margin:8px 0 20px;transition:background .15s;}
  button.submit:hover{background:#6a56ef;}

  .switch{text-align:center;font-size:13.5px;color:#888;}
  .switch a{color:#111;font-weight:600;text-decoration:none;cursor:pointer;}
  .switch a:hover{text-decoration:underline;}

  .msg{padding:9px 12px;border-radius:8px;font-size:12.5px;margin-bottom:14px;display:none;}
  .msg.err{background:#fdecec;color:#c0392b;}
  .msg.ok{background:#eaf7ef;color:#1e8449;}

  .name-field{display:none;}
  .name-field.show{display:block;}

  .lang-switch{display:flex;justify-content:center;gap:6px;margin-bottom:20px;}
  .lang-switch button{padding:5px 12px;border-radius:100px;border:1px solid #eee;background:#fff;font-size:11.5px;font-weight:700;color:#999;cursor:pointer;}
  .lang-switch button.active{background:#111;color:#fff;border-color:#111;}
</style>
</head>
<body>
<div class="bg-particles">
  <span style="left:6%;width:5px;height:5px;animation-duration:16s;animation-delay:0s;"></span>
  <span style="left:16%;width:3px;height:3px;animation-duration:12s;animation-delay:2s;"></span>
  <span style="left:28%;width:4px;height:4px;animation-duration:19s;animation-delay:4s;"></span>
  <span style="left:42%;width:3px;height:3px;animation-duration:14s;animation-delay:1s;"></span>
  <span style="left:58%;width:5px;height:5px;animation-duration:17s;animation-delay:6s;"></span>
  <span style="left:71%;width:3px;height:3px;animation-duration:13s;animation-delay:3s;"></span>
  <span style="left:83%;width:4px;height:4px;animation-duration:18s;animation-delay:5s;"></span>
  <span style="left:92%;width:3px;height:3px;animation-duration:15s;animation-delay:7s;"></span>
</div>
<div class="wrap">
  <div class="lang-switch">
    <button id="langPl" onclick="setLang('pl')">PL</button>
    <button id="langEn" onclick="setLang('en')">EN</button>
  </div>
  <div class="logo"><span class="logo-dot"></span>EchoLine</div>
  <h1 id="heading" data-i18n="welcome_back">Witaj ponownie</h1>

  <div class="msg err" id="err"></div>
  <div class="msg ok" id="ok"></div>

  <button class="social" onclick="doGoogle()">
    <svg viewBox="0 0 48 48"><path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.8 32.9 29.3 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.9 1.2 8 3.1l5.7-5.7C34.5 6.1 29.5 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.7-.4-3.5z"/><path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.6 16 18.9 13 24 13c3.1 0 5.9 1.2 8 3.1l5.7-5.7C34.5 6.1 29.5 4 24 4c-7.7 0-14.3 4.3-17.7 10.7z"/><path fill="#4CAF50" d="M24 44c5.3 0 10.1-1.8 13.8-4.9l-6.4-5.4C29.3 35.4 26.8 36 24 36c-5.3 0-9.7-3.4-11.3-8.1l-6.6 5.1C9.6 39.6 16.2 44 24 44z"/><path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.1-4 5.5l6.4 5.4C41.8 35.5 44 30.1 44 24c0-1.3-.1-2.7-.4-3.5z"/></svg>
    <span data-i18n="continue_google">Kontynuuj z Google</span>
  </button>

  <div class="divider" data-i18n="or_divider">lub</div>

  <div class="name-field" id="nameField">
    <label data-i18n="first_name">Imię</label>
    <div class="field"><input type="text" id="rN" data-i18n-ph="first_name_ph" placeholder="Jak masz na imię"></div>
  </div>

  <label data-i18n="email_label">Email</label>
  <div class="field"><input type="email" id="fE" data-i18n-ph="email_ph" placeholder="ty@przyklad.pl"></div>

  <div class="row-label">
    <label style="margin-bottom:0;" data-i18n="password_label">Hasło</label>
    <a onclick="doReset()" id="forgotLink" data-i18n="forgot_password">Zapomniałem hasła</a>
  </div>
  <div class="field" style="position:relative;">
    <input type="password" id="fP" placeholder="••••••••" style="padding-right:40px;">
    <button type="button" onclick="togglePw()" style="position:absolute;right:10px;top:50%;transform:translateY(-50%);background:none;border:none;cursor:pointer;padding:4px;display:flex;">
      <i data-lucide="eye" id="eyeIcon" style="width:18px;height:18px;color:#888;"></i>
    </button>
  </div>

  <button class="submit" id="submitBtn" onclick="doLogin()" data-i18n="login_btn">Zaloguj się</button>

  <div class="switch" id="switchText">
    Nie masz konta? <a onclick="toggleMode()">Zarejestruj się</a>
  </div>

  <div style="text-align:center;font-size:11.5px;color:#bbb;margin-top:18px;">
    Kontynuując akceptujesz <a href="/regulamin" style="color:#999;">Regulamin</a> i <a href="/polityka-prywatnosci" style="color:#999;">Politykę Prywatności</a>
  </div>
</div>

<script type="module">
  import { initializeApp } from "https://www.gstatic.com/firebasejs/10.13.0/firebase-app.js";
  import {
    getAuth, GoogleAuthProvider, signInWithPopup,
    signInWithEmailAndPassword, createUserWithEmailAndPassword,
    sendPasswordResetEmail, updateProfile
  } from "https://www.gstatic.com/firebasejs/10.13.0/firebase-auth.js";
  import {
    getFirestore, doc, getDoc, setDoc, serverTimestamp
  } from "https://www.gstatic.com/firebasejs/10.13.0/firebase-firestore.js";

  const firebaseConfig = {{ firebase_config | tojson }};
  const app = initializeApp(firebaseConfig);
  const auth = getAuth(app);
  const db = getFirestore(app);

  async function ensureUserDoc(user){
    const ref = doc(db, "users", user.uid);
    const snap = await getDoc(ref);
    if(!snap.exists()){
      await setDoc(ref, {
        uid: user.uid,
        email: user.email,
        name: user.displayName || "",
        country: null,
        voiceId: null,
        phoneNumber: null,
        instructions: "Umawiaj wizyty i podawaj cennik uslug.",
        onboardingDone: false,
        createdAt: serverTimestamp()
      });
    }
  }

  let mode = 'login';

  const I18N = {
    pl: {
      welcome_back: "Witaj ponownie",
      create_account_title: "Utwórz konto",
      continue_google: "Kontynuuj z Google",
      or_divider: "lub",
      first_name: "Imię",
      first_name_ph: "Jak masz na imię",
      email_label: "Email",
      email_ph: "ty@przyklad.pl",
      password_label: "Hasło",
      forgot_password: "Zapomniałem hasła",
      login_btn: "Zaloguj się",
      register_btn: "Utwórz konto",
      no_account: "Nie masz konta?",
      have_account: "Masz już konto?",
      signup_link: "Zarejestruj się",
      login_link: "Zaloguj się",
      err_invalid: "Nieprawidłowy email lub hasło.",
      err_not_found: "Nie znaleziono konta z tym emailem.",
      err_in_use: "Konto z tym emailem już istnieje.",
      err_weak: "Hasło musi mieć min. 6 znaków.",
      err_invalid_email: "Nieprawidłowy adres email.",
      err_generic: "Wystąpił błąd: ",
      err_fill_both: "Wpisz email i hasło.",
      err_fill_email_for_reset: 'Wpisz email powyzej, potem kliknij Zapomnialem hasla.',
      ok_reset_sent: "Link do resetu hasła wysłany na ",
    },
    en: {
      welcome_back: "Welcome back",
      create_account_title: "Create account",
      continue_google: "Continue with Google",
      or_divider: "or",
      first_name: "First name",
      first_name_ph: "What's your name",
      email_label: "Email",
      email_ph: "you@example.com",
      password_label: "Password",
      forgot_password: "Forgot password",
      login_btn: "Log in",
      register_btn: "Create account",
      no_account: "Don't have an account?",
      have_account: "Already have an account?",
      signup_link: "Sign up",
      login_link: "Log in",
      err_invalid: "Invalid email or password.",
      err_not_found: "No account found with this email.",
      err_in_use: "An account with this email already exists.",
      err_weak: "Password must be at least 6 characters.",
      err_invalid_email: "Invalid email address.",
      err_generic: "An error occurred: ",
      err_fill_both: "Enter your email and password.",
      err_fill_email_for_reset: 'Enter your email above, then click Forgot password.',
      ok_reset_sent: "Password reset link sent to ",
    }
  };

  let currentLang = (navigator.language || 'pl').slice(0, 2).toLowerCase() === 'pl' ? 'pl' : 'en';

  function t(key){ return I18N[currentLang][key] || key; }

  function updateSwitchText(){
    document.getElementById('switchText').innerHTML = mode === 'login'
      ? t('no_account') + ' <a onclick="toggleMode()">' + t('signup_link') + '</a>'
      : t('have_account') + ' <a onclick="toggleMode()">' + t('login_link') + '</a>';
  }

  function applyLang(){
    document.querySelectorAll('[data-i18n]').forEach(el => {
      el.textContent = t(el.getAttribute('data-i18n'));
    });
    document.querySelectorAll('[data-i18n-ph]').forEach(el => {
      el.placeholder = t(el.getAttribute('data-i18n-ph'));
    });
    document.getElementById('heading').textContent = mode === 'login' ? t('welcome_back') : t('create_account_title');
    document.getElementById('submitBtn').textContent = mode === 'login' ? t('login_btn') : t('register_btn');
    updateSwitchText();
  }

  window.setLang = function(lang){
    currentLang = lang;
    document.getElementById('langPl').classList.toggle('active', lang === 'pl');
    document.getElementById('langEn').classList.toggle('active', lang === 'en');
    applyLang();
  };

  window.togglePw = function(){
    const input = document.getElementById('fP');
    const icon = document.getElementById('eyeIcon');
    if(input.type === 'password'){
      input.type = 'text';
      icon.innerHTML = '<path d="M17.94 17.94A10.94 10.94 0 0 1 12 19c-7 0-11-7-11-7a18.5 18.5 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 7 11 7a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/>';
    } else {
      input.type = 'password';
      icon.innerHTML = '<path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7z"/><circle cx="12" cy="12" r="3"/>';
    }
  };

  window.toggleMode = function(){
    mode = (mode === 'login') ? 'register' : 'login';
    document.getElementById('nameField').classList.toggle('show', mode === 'register');
    document.getElementById('forgotLink').style.visibility = mode === 'register' ? 'hidden' : 'visible';
    document.getElementById('submitBtn').onclick = mode === 'login' ? doLogin : doReg;
    applyLang();
    hideMsgs();
  };

  function hideMsgs(){
    document.getElementById('err').style.display='none';
    document.getElementById('ok').style.display='none';
  }
  function showErr(msg){ hideMsgs(); const e=document.getElementById('err'); e.textContent=msg; e.style.display='block'; }
  function showOk(msg){ hideMsgs(); const o=document.getElementById('ok'); o.textContent=msg; o.style.display='block'; }

  function friendlyError(code){
    if(code === 'auth/invalid-credential' || code === 'auth/wrong-password') return t('err_invalid');
    if(code === 'auth/user-not-found') return t('err_not_found');
    if(code === 'auth/email-already-in-use') return t('err_in_use');
    if(code === 'auth/weak-password') return t('err_weak');
    if(code === 'auth/invalid-email') return t('err_invalid_email');
    return t('err_generic') + code;
  }

  async function finishLogin(user){
    await ensureUserDoc(user);
    const resp = await fetch("/session-login", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({email: user.email, name: user.displayName, uid: user.uid})
    });
    if (resp.ok) window.location.href = "/dashboard";
    else showErr("Nie udalo sie zalogowac po stronie serwera.");
  }

  window.doLogin = async function(){
    const email = document.getElementById('fE').value.trim();
    const pass = document.getElementById('fP').value;
    if(!email || !pass){ showErr(t('err_fill_both')); return; }
    try{
      const r = await signInWithEmailAndPassword(auth, email, pass);
      await finishLogin(r.user);
    }catch(e){ showErr(friendlyError(e.code)); }
  };

  window.doReg = async function(){
    const name = document.getElementById('rN').value.trim();
    const email = document.getElementById('fE').value.trim();
    const pass = document.getElementById('fP').value;
    if(!email || !pass){ showErr(t('err_fill_both')); return; }
    if(pass.length < 6){ showErr(t('err_weak')); return; }
    try{
      const r = await createUserWithEmailAndPassword(auth, email, pass);
      if(name) await updateProfile(r.user, {displayName: name});
      await finishLogin(r.user);
    }catch(e){ showErr(friendlyError(e.code)); }
  };

  window.doReset = async function(){
    if(mode !== 'login') return;
    const email = document.getElementById('fE').value.trim();
    if(!email){ showErr(t('err_fill_email_for_reset')); return; }
    try{
      await sendPasswordResetEmail(auth, email);
      showOk(t('ok_reset_sent') + email + '.');
    }catch(e){ showErr(friendlyError(e.code)); }
  };

  window.doGoogle = async function(){
    try{
      const provider = new GoogleAuthProvider();
      const r = await signInWithPopup(auth, provider);
      await finishLogin(r.user);
    }catch(e){
      if(e.code !== 'auth/popup-closed-by-user') showErr(friendlyError(e.code));
    }
  };

  setLang(currentLang);
</script>
<script src="https://unpkg.com/lucide@latest/dist/umd/lucide.js"></script>
<script>lucide.createIcons();</script>
</body>
</html>
"""

DASHBOARD_PAGE = """
<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>EchoLine - panel</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
  *{box-sizing:border-box;margin:0;padding:0;}
  .bg-particles{position:fixed;inset:0;overflow:hidden;pointer-events:none;z-index:0;}
  .bg-particles span{position:absolute;bottom:-10px;border-radius:50%;background:#7c6aff;opacity:0;animation:floatDust linear infinite;}
  @keyframes floatDust{
    0%{transform:translateY(0) translateX(0);opacity:0;}
    10%{opacity:0.4;}
    90%{opacity:0.4;}
    100%{transform:translateY(-105vh) translateX(30px);opacity:0;}
  }
  .langbtn{border:1px solid #eee;background:#fff;color:#999;}
  .langbtn.active{background:#111;color:#fff;border-color:#111;}
  body{font-family:'Inter',sans-serif;background:#fff;color:#111;display:flex;min-height:100vh;}
  ::-webkit-scrollbar{width:8px;height:8px;}

  @keyframes riseIn{from{opacity:0;transform:translateY(10px);}to{opacity:1;transform:none;}}
  .rise{animation:riseIn .5s cubic-bezier(.16,1,.3,1) both;}
  .rise2{animation:riseIn .5s .08s cubic-bezier(.16,1,.3,1) both;}
  .rise3{animation:riseIn .5s .16s cubic-bezier(.16,1,.3,1) both;}
  .rise4{animation:riseIn .5s .24s cubic-bezier(.16,1,.3,1) both;}

  /* SIDEBAR */
  .sidebar{width:230px;flex-shrink:0;border-right:1px solid #eee;padding:20px 12px;display:flex;flex-direction:column;}
  .logo{font-size:15px;font-weight:800;padding:8px 8px 20px;letter-spacing:-0.01em;display:flex;align-items:center;gap:9px;}
  .logo-dot{width:22px;height:22px;border-radius:50%;background:radial-gradient(circle at 30% 30%,#a9c9ff,#7c6aff 60%,#5a4bd4);flex-shrink:0;box-shadow:0 0 14px rgba(124,106,255,0.4);}
  .nav-item{display:flex;align-items:center;gap:10px;padding:9px 10px;border-radius:9px;font-size:13.5px;font-weight:500;color:#555;text-decoration:none;margin-bottom:2px;cursor:pointer;}
  .nav-item:hover{background:#f5f5f7;}
  .nav-item.active{background:linear-gradient(135deg,#7c6aff,#5dadff);color:#fff;box-shadow:0 6px 16px rgba(124,106,255,0.3);}
  .nav-icon{width:17px;height:17px;flex-shrink:0;stroke:#666;fill:none;stroke-width:1.8;}
  .nav-item.active .nav-icon{stroke:#fff;}
  .nav-section-label{font-size:10.5px;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;color:#bbb;padding:16px 10px 6px;}

  .sidebar-widget{margin-top:auto;background:linear-gradient(160deg,#f2f0ff,#eef6ff);border-radius:16px;padding:18px;text-align:left;position:relative;overflow:hidden;}
  .sidebar-widget .sw-title{font-size:12.5px;font-weight:700;color:#5a4bd4;line-height:1.4;margin-bottom:14px;}
  .sw-orbit{width:76px;height:76px;margin:6px auto 14px;position:relative;}
  .sw-sphere{width:44px;height:44px;border-radius:50%;background:radial-gradient(circle at 30% 30%,#c9d9ff,#7c6aff 55%,#4f3fcf);position:absolute;top:16px;left:16px;box-shadow:0 0 22px rgba(124,106,255,0.5);}
  .sw-ring{position:absolute;inset:0;border:1.5px solid rgba(124,106,255,0.35);border-radius:50%;transform:rotate(-20deg) scaleY(0.42);}
  .sw-link{display:flex;align-items:center;gap:6px;font-size:12px;font-weight:600;color:#5a4bd4;text-decoration:none;}

  /* TOPBAR / MAIN */
  .main{flex:1;display:flex;flex-direction:column;min-width:0;}
  .topbar{display:flex;align-items:center;justify-content:flex-end;padding:16px 32px;gap:16px;}
  .mobile-title{display:none;font-size:16px;font-weight:700;margin-right:auto;}
  .bell{width:34px;height:34px;border-radius:50%;display:flex;align-items:center;justify-content:center;position:relative;cursor:pointer;}
  .bell:hover{background:#f5f5f7;}
  .bell svg{width:18px;height:18px;stroke:#555;fill:none;stroke-width:1.8;}
  .bell-dot{position:absolute;top:8px;right:9px;width:6px;height:6px;border-radius:50%;background:#ef4444;}
  a.logout{color:#888;font-size:13px;text-decoration:none;display:flex;align-items:center;gap:6px;}
  a.logout:hover{text-decoration:underline;}
  .logout-icon{display:none;width:18px;height:18px;stroke:#888;fill:none;stroke-width:1.8;}
  .avatar{width:32px;height:32px;border-radius:50%;background:linear-gradient(135deg,#7c6aff,#4f3fcf);color:#fff;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:700;flex-shrink:0;}
  .lang-switch-top{display:flex;gap:4px;}
  .lang-switch-top button{padding:4px 10px;border-radius:100px;border:1px solid #eee;background:#fff;font-size:11px;font-weight:700;color:#999;cursor:pointer;}
  .lang-switch-top button.active{background:#111;color:#fff;border-color:#111;}

  .content{padding:0 32px 32px;max-width:1180px;}

  /* HERO */
  .hero{background:linear-gradient(120deg,#f2f0ff,#eef6ff);border-radius:20px;padding:28px 32px;display:grid;grid-template-columns:1fr 1fr;gap:20px;align-items:center;margin-bottom:22px;position:relative;overflow:hidden;}
  .eyebrow{font-size:11px;font-weight:700;letter-spacing:0.08em;color:#7c6aff;margin-bottom:8px;}
  .hero h1{font-size:32px;font-weight:800;letter-spacing:-0.02em;margin-bottom:8px;}
  .hero p{font-size:14px;color:#777;}
  .chart-box{background:rgba(255,255,255,0.6);border-radius:14px;padding:16px 18px;}
  .chart-box-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;}
  .chart-box-top span.lbl{font-size:12.5px;color:#888;font-weight:600;}
  .chart-box-top span.val{font-size:12px;background:#fff;border-radius:8px;padding:4px 10px;font-weight:700;color:#7c6aff;}

  /* TABS */
  .tabs{display:flex;gap:10px;margin-bottom:20px;}
  .tabbtn{flex:1;display:flex;align-items:center;gap:10px;padding:14px 18px;border-radius:13px;border:1px solid #eee;background:#fff;cursor:pointer;transition:all .15s;}
  .tabbtn .ic{width:34px;height:34px;border-radius:9px;display:flex;align-items:center;justify-content:center;flex-shrink:0;background:#f5f5f7;}
  .tabbtn .ic svg{width:17px;height:17px;stroke:#888;fill:none;stroke-width:1.8;}
  .tabbtn .txt{text-align:left;}
  .tabbtn .txt b{display:block;font-size:13.5px;color:#333;}
  .tabbtn .txt small{font-size:11.5px;color:#999;}
  .tabbtn.active{border-color:#d9d2ff;background:#f8f7ff;}
  .tabbtn.active .ic{background:linear-gradient(135deg,#7c6aff,#5dadff);}
  .tabbtn.active .ic svg{stroke:#fff;}
  .tabbtn.active .txt b{color:#5a4bd4;}

  /* ACTION CARDS */
  .cards{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:20px;}
  .action-card{border:1px solid #eee;border-radius:16px;padding:22px;cursor:pointer;transition:all .15s;}
  .action-card:hover{border-color:#d9d2ff;box-shadow:0 8px 20px rgba(124,106,255,0.08);transform:translateY(-1px);}
  .glow-icon{width:56px;height:56px;border-radius:50%;display:flex;align-items:center;justify-content:center;margin-bottom:16px;position:relative;}
  .glow-icon svg{width:24px;height:24px;stroke:#fff;fill:none;stroke-width:1.8;position:relative;z-index:1;}
  .glow-icon::after{content:"";position:absolute;inset:-8px;border-radius:50%;opacity:0.35;filter:blur(10px);z-index:0;}
  .glow-purple{background:radial-gradient(circle at 30% 30%,#9b8bff,#6b57e8);}
  .glow-purple::after{background:#7c6aff;}
  .glow-blue{background:radial-gradient(circle at 30% 30%,#7fd0ff,#3ba0e8);}
  .glow-blue::after{background:#5dadff;}
  .glow-pink{background:radial-gradient(circle at 30% 30%,#ffb0e6,#e85fc4);}
  .glow-pink::after{background:#e85fc4;}
  .action-card h3{font-size:14.5px;font-weight:700;margin-bottom:4px;display:flex;align-items:center;justify-content:space-between;}
  .action-card h3 svg{width:14px;height:14px;stroke:#bbb;}
  .action-card p{font-size:12.5px;color:#888;line-height:1.4;}

  /* GRID CONTENT */
  .grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:20px;}
  .card{background:#fff;border:1px solid #eee;border-radius:16px;padding:22px;}
  .card-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;flex-wrap:wrap;gap:8px;}
  .card-head h3{font-size:14px;font-weight:700;display:flex;align-items:center;gap:8px;}
  .card-head h3 svg{width:15px;height:15px;stroke:#7c6aff;fill:none;stroke-width:1.8;}
  .card-head a{font-size:12.5px;color:#7c6aff;text-decoration:none;font-weight:600;}

  .profile-field{border:1px solid #f0f0f0;border-radius:11px;padding:12px 14px;margin-bottom:10px;display:flex;justify-content:space-between;align-items:flex-start;gap:10px;}
  .profile-field:last-child{margin-bottom:0;}
  .profile-field .pf-label{font-size:11px;color:#999;font-weight:600;margin-bottom:3px;}
  .profile-field .pf-value{font-size:13px;color:#222;}
  .profile-field textarea{width:100%;font-family:inherit;font-size:13px;border:1px solid #d9d2ff;border-radius:8px;padding:8px;min-height:50px;display:none;}
  .pf-edit{background:none;border:none;cursor:pointer;padding:4px;flex-shrink:0;}
  .pf-edit svg{width:14px;height:14px;stroke:#aaa;}
  .pf-save{display:none;font-size:11.5px;font-weight:700;color:#fff;background:#7c6aff;border:none;border-radius:7px;padding:5px 10px;cursor:pointer;margin-top:6px;}
  .edit-all{font-size:12.5px;color:#7c6aff;text-decoration:none;font-weight:600;display:inline-block;margin-top:8px;}

  table{width:100%;border-collapse:collapse;}
  td,th{padding:10px 8px;border-bottom:1px solid #f5f5f5;text-align:left;font-size:12.5px;}
  th{color:#aaa;font-weight:600;text-transform:uppercase;font-size:10px;letter-spacing:0.04em;}
  tr.datarow:hover{background:#fafaff;}
  .tag{display:inline-block;padding:3px 10px;border-radius:100px;font-size:11px;font-weight:700;}
  .tag.ok{background:#e8f8f0;color:#1e9e63;}
  .tag.missed{background:#fdf3e3;color:#c9840f;}

  /* CALL MODE (Zadzwon za mnie) */
  .call-wrap{max-width:640px;}
  .call-wrap textarea{width:100%;padding:14px;border-radius:12px;border:1px solid #ddd;font-family:inherit;font-size:14px;min-height:100px;margin-bottom:12px;}
  .call-wrap input{width:100%;padding:12px 14px;border-radius:12px;border:1px solid #ddd;font-family:inherit;font-size:14px;margin-bottom:16px;}
  .call-btn{width:100%;padding:15px;border-radius:13px;border:none;background:linear-gradient(135deg,#7c6aff,#5dadff);color:#fff;font-weight:700;font-size:15px;cursor:pointer;box-shadow:0 10px 24px rgba(124,106,255,0.3);}
  .call-btn:hover{opacity:0.92;}

  .save-inline{padding:10px 20px;border-radius:10px;border:none;background:linear-gradient(135deg,#7c6aff,#5dadff);color:#fff;font-weight:700;font-size:13.5px;cursor:pointer;}

  /* RESPONSIVE */
  @media (max-width: 900px) {
    .hero{grid-template-columns:1fr;}
    .grid2{grid-template-columns:1fr;}
  }
  @media (max-width: 760px) {
    body{flex-direction:column;}
    .sidebar{width:100%;border-right:none;border-bottom:1px solid #eee;flex-direction:row;align-items:center;padding:12px 16px;overflow-x:auto;white-space:nowrap;}
    .sidebar-widget,.nav-section-label{display:none;}
    .logo{padding:0 14px 0 0;}
    .nav-item span.label{display:none;}
    .content{padding:0 16px 24px;}
    .hero{padding:20px;border-radius:16px;}
    .hero h1{font-size:24px;}
    .cards{grid-template-columns:1fr;}
    .tabs{flex-direction:column;}
    table{font-size:11.5px;}
    td,th{padding:8px 4px;}
    .topbar{padding:12px 16px;}
    .mobile-title{display:block;}
    .logout-icon{display:block;}
    .logout-text{display:none;}
  }
</style>
</head>
<body>
<div class="bg-particles">
  <span style="left:6%;width:5px;height:5px;animation-duration:16s;animation-delay:0s;"></span>
  <span style="left:16%;width:3px;height:3px;animation-duration:12s;animation-delay:2s;"></span>
  <span style="left:28%;width:4px;height:4px;animation-duration:19s;animation-delay:4s;"></span>
  <span style="left:42%;width:3px;height:3px;animation-duration:14s;animation-delay:1s;"></span>
  <span style="left:58%;width:5px;height:5px;animation-duration:17s;animation-delay:6s;"></span>
  <span style="left:71%;width:3px;height:3px;animation-duration:13s;animation-delay:3s;"></span>
  <span style="left:83%;width:4px;height:4px;animation-duration:18s;animation-delay:5s;"></span>
  <span style="left:92%;width:3px;height:3px;animation-duration:15s;animation-delay:7s;"></span>
</div>

<div class="sidebar">
  <div class="logo"><span class="logo-dot"></span>EchoLine</div>
  <a class="nav-item{{ ' active' if active_page == 'dashboard' else '' }}" href="/dashboard">
    <i data-lucide="layout-dashboard" class="nav-icon"></i>
    <span class="label" data-i18n="nav_dashboard">Dashboard</span>
  </a>
  <a class="nav-item{{ ' active' if active_page == 'number' else '' }}" href="/numer-telefonu">
    <i data-lucide="phone" class="nav-icon"></i>
    <span class="label" data-i18n="nav_number">Numer telefonu</span>
  </a>
  <a class="nav-item{{ ' active' if active_page == 'voice' else '' }}" href="/moj-glos">
    <i data-lucide="mic" class="nav-icon"></i>
    <span class="label" data-i18n="nav_voice">Mój głos</span>
  </a>
  <a class="nav-item{{ ' active' if active_page == 'calls' else '' }}" href="/rozmowy">
    <i data-lucide="message-circle" class="nav-icon"></i>
    <span class="label" data-i18n="nav_calls">Rozmowy</span>
  </a>
  <a class="nav-item{{ ' active' if active_page == 'pricing' else '' }}" href="/cennik">
    <i data-lucide="credit-card" class="nav-icon"></i>
    <span class="label" data-i18n="nav_pricing">Cennik</span>
  </a>
  <div class="nav-section-label" data-i18n="nav_account">Konto</div>
  <a class="nav-item{{ ' active' if active_page == 'settings' else '' }}" href="/ustawienia">
    <i data-lucide="settings" class="nav-icon"></i>
    <span class="label" data-i18n="nav_settings">Ustawienia</span>
  </a>

  <div class="sidebar-widget">
    <div class="sw-title" id="swTitle">Twój asystent AI<br>24/7 gotowy do rozmów</div>
    <div class="sw-orbit"><div class="sw-ring"></div><div class="sw-sphere"></div></div>
    <a class="sw-link" href="#" data-i18n="widget_link">Zobacz statystyki →</a>
  </div>
</div>

<div class="main">
  <div class="topbar">
    <h2 class="mobile-title" data-i18n="nav_dashboard">Dashboard</h2>
    <div class="lang-switch-top">
      <button id="langPl" onclick="setLang('pl')">PL</button>
      <button id="langEn" onclick="setLang('en')">EN</button>
    </div>
    <div class="bell"><i data-lucide="bell"></i><div class="bell-dot"></div></div>
    <a class="logout" href="/logout"><i data-lucide="log-out" class="logout-icon"></i><span class="logout-text" data-i18n="logout">Wyloguj</span></a>
    <div class="avatar">{{ user_email[0]|upper if user_email else "U" }}</div>
  </div>

  <div id="sufBox" style="display:none;position:fixed;bottom:24px;right:24px;left:auto;max-width:360px;background:#fff;border:1.5px solid #7c6aff;border-radius:16px;padding:18px;box-shadow:0 20px 50px -15px rgba(124,106,255,0.4);z-index:999;">
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px;">
      <div style="width:8px;height:8px;border-radius:50%;background:#e74c3c;animation:recPulse 1.2s infinite;"></div>
      <b style="font-size:13px;" data-i18n="suf_title">Bot potrzebuje podpowiedzi</b>
    </div>
    <p id="sufQuestion" style="font-size:13px;color:#555;margin-bottom:12px;"></p>
    <div style="display:flex;gap:8px;">
      <input id="sufInput" type="text" data-i18n-ph="suf_input_ph" placeholder="Wpisz co ma powiedzieć..." style="flex:1;padding:9px 12px;border-radius:9px;border:1px solid #ddd;font-size:13px;font-family:inherit;">
      <button onclick="sendHint()" style="padding:9px 14px;border-radius:9px;border:none;background:linear-gradient(135deg,#7c6aff,#5dadff);color:#fff;font-weight:700;font-size:13px;cursor:pointer;" data-i18n="suf_send">Wyślij</button>
    </div>
  </div>

  <div class="content">

    <div class="hero rise">
      <div>
        <div class="eyebrow" data-i18n="eyebrow">WITAJ PONOWNIE</div>
        <h1><span data-i18n="hi_comma">Cześć,</span> {{ user_name or "tam" }}</h1>
        <p data-i18n="hero_sub">Oto co dzieje się z Twoim asystentem</p>
      </div>
      <div class="chart-box">
        <div class="chart-box-top"><span class="lbl" data-i18n="chart_label">Rozmowy w tym tygodniu</span><span class="val">{{ calls|length }}</span></div>
        <svg viewBox="0 0 320 110" width="100%" height="90" preserveAspectRatio="none">
          <defs>
            <linearGradient id="chartFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="#7c6aff" stop-opacity="0.35"/>
              <stop offset="100%" stop-color="#7c6aff" stop-opacity="0"/>
            </linearGradient>
          </defs>
          <path d="M0,80 L45,55 L90,60 L135,40 L180,20 L225,35 L270,25 L320,15 L320,110 L0,110 Z" fill="url(#chartFill)"/>
          <path d="M0,80 L45,55 L90,60 L135,40 L180,20 L225,35 L270,25 L320,15" fill="none" stroke="#7c6aff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        <div id="chartDays" style="display:flex;justify-content:space-between;font-size:10.5px;color:#aaa;margin-top:2px;">
          <span>Pon</span><span>Wt</span><span>Śr</span><span>Czw</span><span>Pt</span><span>Sob</span><span>Ndz</span>
        </div>
      </div>
    </div>

    <div class="tabs rise2">
      <div class="tabbtn active" id="tab-assistant" onclick="showTab('assistant')">
        <div class="ic"><svg viewBox="0 0 24 24"><path d="M12 8V4H8"/><rect width="16" height="12" x="4" y="8" rx="2"/><path d="M2 14h2"/><path d="M20 14h2"/><path d="M15 13v2"/><path d="M9 13v2"/></svg></div>
        <div class="txt"><b data-i18n="tab_assistant_title">Mój asystent</b><small data-i18n="tab_assistant_desc">Bot odbiera połączenia przychodzące</small></div>
      </div>
      <div class="tabbtn" id="tab-quickcall" onclick="showTab('quickcall')">
        <div class="ic"><svg viewBox="0 0 24 24"><path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6 19.8 19.8 0 0 1-3.1-8.6A2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .3 2 .6 3a2 2 0 0 1-.5 2.1L8 10a16 16 0 0 0 6 6l1.2-1.2a2 2 0 0 1 2.1-.5c1 .3 2 .5 3 .6a2 2 0 0 1 1.7 2z"/></svg></div>
        <div class="txt"><b data-i18n="tab_quickcall_title">Zadzwoń za mnie</b><small data-i18n="tab_quickcall_desc">Jednorazowe zlecenie rozmowy</small></div>
      </div>
    </div>

    <div id="section-assistant">
      <div class="cards rise3">
        <div class="action-card" onclick="location.href='/numer-telefonu';">
          <div class="glow-icon glow-purple"><i data-lucide="phone"></i></div>
          <h3><span data-i18n="card_number_title">Skonfiguruj numer</span> <i data-lucide="chevron-right"></i></h3>
          <p data-i18n="card_number_desc">Wybierz kraj i uzyskaj swój numer telefonu</p>
        </div>
        <div class="action-card" onclick="location.href='/moj-glos';">
          <div class="glow-icon glow-blue"><i data-lucide="mic"></i></div>
          <h3><span data-i18n="card_voice_title">Sklonuj swój głos</span> <i data-lucide="chevron-right"></i></h3>
          <p data-i18n="card_voice_desc">Nagraj próbkę, aby bot mówił Twoim głosem</p>
        </div>
        <div class="action-card" onclick="location.href='/rozmowy';">
          <div class="glow-icon glow-pink"><i data-lucide="message-circle"></i></div>
          <h3><span data-i18n="card_calls_title">Zobacz rozmowy</span> <i data-lucide="chevron-right"></i></h3>
          <p data-i18n="card_calls_desc">Przeglądaj transkrypcje i historię połączeń</p>
        </div>
      </div>

      <div class="grid2 rise4">
        <div class="card" id="voice-card">
          <div class="card-head"><h3><svg viewBox="0 0 24 24"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg><span data-i18n="voice_status_title">Status głosu</span></h3></div>
          <p id="voiceStatus" style="font-size:13px;color:#888;margin-bottom:16px;">Sprawdzam status...</p>
          <button class="save-inline" onclick="location.href='/moj-glos';" data-i18n="voice_manage_btn">Zarządzaj głosem</button>
        </div>

        <div class="card">
          <div class="card-head"><h3><svg viewBox="0 0 24 24"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4Z"/></svg><span data-i18n="profile_title">Profil asystenta</span></h3></div>

          <div class="profile-field">
            <div style="flex:1;">
              <div class="pf-label" data-i18n="pf_company_label">Nazwa firmy / kim jest bot</div>
              <div class="pf-value" data-field="companyName" data-i18n-fallback="not_set">{{ profile.companyName or "Nie ustawiono" }}</div>
              <textarea data-input="companyName">{{ profile.companyName or "" }}</textarea>
              <button class="pf-save" data-savebtn="companyName" onclick="saveField('companyName')" data-i18n="save_btn">Zapisz</button>
            </div>
            <button class="pf-edit" onclick="editField('companyName')"><i data-lucide="pencil"></i></button>
          </div>

          <div class="profile-field">
            <div style="flex:1;">
              <div class="pf-label" data-i18n="pf_pricing_label">Cennik i oferta</div>
              <div class="pf-value" data-field="pricing" data-i18n-fallback="not_set">{{ profile.pricing or "Nie ustawiono" }}</div>
              <textarea data-input="pricing">{{ profile.pricing or "" }}</textarea>
              <button class="pf-save" data-savebtn="pricing" onclick="saveField('pricing')" data-i18n="save_btn">Zapisz</button>
            </div>
            <button class="pf-edit" onclick="editField('pricing')"><i data-lucide="pencil"></i></button>
          </div>

          <div class="profile-field">
            <div style="flex:1;">
              <div class="pf-label" data-i18n="pf_hours_label">Godziny pracy</div>
              <div class="pf-value" data-field="hours" data-i18n-fallback="not_set">{{ profile.hours or "Nie ustawiono" }}</div>
              <textarea data-input="hours">{{ profile.hours or "" }}</textarea>
              <button class="pf-save" data-savebtn="hours" onclick="saveField('hours')" data-i18n="save_btn">Zapisz</button>
            </div>
            <button class="pf-edit" onclick="editField('hours')"><i data-lucide="pencil"></i></button>
          </div>

          <div class="profile-field">
            <div style="flex:1;">
              <div class="pf-label" data-i18n="pf_rules_label">Zasady i ograniczenia</div>
              <div class="pf-value" data-field="rules" data-i18n-fallback="not_set">{{ profile.rules or "Nie ustawiono" }}</div>
              <textarea data-input="rules">{{ profile.rules or "" }}</textarea>
              <button class="pf-save" data-savebtn="rules" onclick="saveField('rules')" data-i18n="save_btn">Zapisz</button>
            </div>
            <button class="pf-edit" onclick="editField('rules')"><i data-lucide="pencil"></i></button>
          </div>

          <div class="profile-field">
            <div style="flex:1;">
              <div class="pf-label" data-i18n="pf_botlang_label">Język, w którym mówi bot</div>
              <select id="botLangSelect" onchange="saveBotLanguage()" style="width:100%;padding:8px 10px;border-radius:8px;border:1px solid #ddd;font-size:13px;margin-top:6px;font-family:inherit;">
                <option value="pl" data-i18n="lang_opt_pl">Polski</option>
                <option value="en" data-i18n="lang_opt_en">Angielski</option>
                <option value="de" data-i18n="lang_opt_de">Niemiecki</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      <div class="card" id="calls-card">
        <div class="card-head">
          <h3><svg viewBox="0 0 24 24"><path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z"/></svg><span data-i18n="calls_title">Ostatnie rozmowy</span></h3>
          <a href="#" data-i18n="see_all">Zobacz wszystkie →</a>
        </div>
        <div style="overflow-x:auto;">
        <table>
          <tr><th data-i18n="th_date">Data</th><th data-i18n="th_with">Z kim</th><th data-i18n="th_summary">Podsumowanie</th><th data-i18n="th_status">Status</th></tr>
          {% for call in calls %}
          <tr class="datarow"><td>{{ call.data }}</td><td>{{ call.z_kim }}</td><td>{{ call.podsumowanie }}</td><td><span class="tag ok" data-i18n="status_completed">Zakończona</span></td></tr>
          {% endfor %}
        </table>
        </div>
      </div>
    </div>

    <div id="section-quickcall" style="display:none;">
      <div class="card call-wrap rise3">
        <div class="card-head"><h3 data-i18n="quickcall_title">Co mam załatwić?</h3></div>
        <textarea id="taskInput" data-i18n-ph="task_ph" placeholder="np. Zadzwoń do dentysty i przełóż wizytę na przyszły tydzień"></textarea>
        <label style="font-size:12.5px;font-weight:600;color:#555;display:block;margin-bottom:6px;" data-i18n="phone_label">Numer telefonu docelowego</label>
        <div style="display:flex;gap:8px;margin-bottom:16px;">
          <select id="phoneCountryCode" style="padding:12px 10px;border-radius:12px;border:1px solid #ddd;font-family:inherit;font-size:14px;background:#fff;flex-shrink:0;">
            <option value="+48">🇵🇱 +48</option>
            <option value="+1">🇺🇸 +1</option>
            <option value="+49">🇩🇪 +49</option>
            <option value="+44">🇬🇧 +44</option>
            <option value="+33">🇫🇷 +33</option>
            <option value="+34">🇪🇸 +34</option>
            <option value="+39">🇮🇹 +39</option>
          </select>
          <input id="phoneInput" type="text" data-i18n-ph="phone_ph" placeholder="np. 601 234 567" style="flex:1;margin-bottom:0;">
        </div>
        <button class="call-btn" onclick="quickCall()" data-i18n="call_now_btn">Zadzwoń teraz</button>
        <p id="quickCallStatus" style="font-size:12.5px;color:#888;margin-top:12px;"></p>
      </div>
    </div>

  </div>
</div>

<style>
  @keyframes recPulse{0%,100%{opacity:1;}50%{opacity:0.25;}}
  .spinner{width:16px;height:16px;border:2px solid #eee;border-top-color:#7c6aff;border-radius:50%;animation:spin 0.7s linear infinite;}
  @keyframes spin{to{transform:rotate(360deg);}}
  .voice-ready{color:#1e8449 !important;}
  .voice-ready-dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:#22d3a0;margin-right:6px;box-shadow:0 0 0 3px rgba(34,211,160,0.15);}
</style>

<script>
  let currentTab = 'assistant';

  const DASH_I18N = {
    pl: {
      nav_dashboard: "Dashboard",
      nav_number: "Numer telefonu",
      nav_voice: "Mój głos",
      nav_calls: "Rozmowy",
      nav_pricing: "Cennik",
      nav_account: "Konto",
      nav_settings: "Ustawienia",
      widget_title_html: "Twój asystent AI<br>24/7 gotowy do rozmów",
      widget_link: "Zobacz statystyki →",
      logout: "Wyloguj",
      suf_title: "Bot potrzebuje podpowiedzi",
      suf_input_ph: "Wpisz co ma powiedzieć...",
      suf_send: "Wyślij",
      eyebrow: "WITAJ PONOWNIE",
      hi_comma: "Cześć,",
      hero_sub: "Oto co dzieje się z Twoim asystentem",
      chart_label: "Rozmowy w tym tygodniu",
      days: ["Pon","Wt","Śr","Czw","Pt","Sob","Ndz"],
      tab_assistant_title: "Mój asystent",
      tab_assistant_desc: "Bot odbiera połączenia przychodzące",
      tab_quickcall_title: "Zadzwoń za mnie",
      tab_quickcall_desc: "Jednorazowe zlecenie rozmowy",
      card_number_title: "Skonfiguruj numer",
      card_number_desc: "Wybierz kraj i uzyskaj swój numer telefonu",
      card_voice_title: "Sklonuj swój głos",
      card_voice_desc: "Nagraj próbkę, aby bot mówił Twoim głosem",
      card_calls_title: "Zobacz rozmowy",
      card_calls_desc: "Przeglądaj transkrypcje i historię połączeń",
      voice_status_title: "Status głosu",
      voice_checking: "Sprawdzam status...",
      voice_manage_btn: "Zarządzaj głosem",
      voice_ready_text: "Głos sklonowany i gotowy do użycia",
      voice_not_ready_text: "Nie masz jeszcze sklonowanego głosu.",
      profile_title: "Profil asystenta",
      pf_company_label: "Nazwa firmy / kim jest bot",
      pf_pricing_label: "Cennik i oferta",
      pf_hours_label: "Godziny pracy",
      pf_rules_label: "Zasady i ograniczenia",
      pf_botlang_label: "Język, w którym mówi bot",
      lang_opt_pl: "Polski", lang_opt_en: "Angielski", lang_opt_de: "Niemiecki",
      not_set: "Nie ustawiono",
      save_btn: "Zapisz",
      calls_title: "Ostatnie rozmowy",
      see_all: "Zobacz wszystkie →",
      th_date: "Data",
      th_with: "Z kim",
      th_summary: "Podsumowanie",
      th_status: "Status",
      status_completed: "Zakończona",
      quickcall_title: "Co mam załatwić?",
      task_ph: "np. Zadzwoń do dentysty i przełóż wizytę na przyszły tydzień",
      phone_label: "Numer telefonu docelowego",
      phone_ph: "np. 601 234 567",
      call_now_btn: "Zadzwoń teraz",
      qc_fill: "Wpisz zadanie i numer telefonu.",
      qc_calling: "Dzwonię...",
    },
    en: {
      nav_dashboard: "Dashboard",
      nav_number: "Phone number",
      nav_voice: "My voice",
      nav_calls: "Calls",
      nav_pricing: "Pricing",
      nav_account: "Account",
      nav_settings: "Settings",
      widget_title_html: "Your AI assistant<br>ready 24/7",
      widget_link: "View statistics →",
      logout: "Log out",
      suf_title: "Bot needs a hint",
      suf_input_ph: "Type what it should say...",
      suf_send: "Send",
      eyebrow: "WELCOME BACK",
      hi_comma: "Hi,",
      hero_sub: "Here's what's happening with your assistant",
      chart_label: "Calls this week",
      days: ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"],
      tab_assistant_title: "My assistant",
      tab_assistant_desc: "Bot answers incoming calls",
      tab_quickcall_title: "Call for me",
      tab_quickcall_desc: "One-time call request",
      card_number_title: "Set up number",
      card_number_desc: "Choose a country and get your phone number",
      card_voice_title: "Clone your voice",
      card_voice_desc: "Record a sample so the bot speaks in your voice",
      card_calls_title: "View calls",
      card_calls_desc: "Browse transcripts and call history",
      voice_status_title: "Voice status",
      voice_checking: "Checking status...",
      voice_manage_btn: "Manage voice",
      voice_ready_text: "Voice cloned and ready to use",
      voice_not_ready_text: "You don't have a cloned voice yet.",
      profile_title: "Assistant profile",
      pf_company_label: "Company name / who the bot is",
      pf_pricing_label: "Pricing and offer",
      pf_hours_label: "Business hours",
      pf_rules_label: "Rules and restrictions",
      pf_botlang_label: "Language the bot speaks",
      lang_opt_pl: "Polish", lang_opt_en: "English", lang_opt_de: "German",
      not_set: "Not set",
      save_btn: "Save",
      calls_title: "Recent calls",
      see_all: "View all →",
      th_date: "Date",
      th_with: "With",
      th_summary: "Summary",
      th_status: "Status",
      status_completed: "Completed",
      quickcall_title: "What should I take care of?",
      task_ph: "e.g. Call the dentist and reschedule the appointment",
      phone_label: "Target phone number",
      phone_ph: "e.g. 601 234 567",
      call_now_btn: "Call now",
      qc_fill: "Enter a task and phone number.",
      qc_calling: "Calling...",
    }
  };

  let currentLang = (navigator.language || 'pl').slice(0, 2).toLowerCase() === 'pl' ? 'pl' : 'en';

  function dt(key){ return DASH_I18N[currentLang][key] || key; }

  function applyDashLang(){
    document.querySelectorAll('[data-i18n]').forEach(el => {
      const key = el.getAttribute('data-i18n');
      el.textContent = dt(key);
    });
    document.querySelectorAll('[data-i18n-ph]').forEach(el => {
      el.placeholder = dt(el.getAttribute('data-i18n-ph'));
    });
    document.querySelectorAll('[data-i18n-fallback]').forEach(el => {
      // Pola profilu: jesli nie ma ustawionej wartosci (pokazuje sie fallback "Nie ustawiono"/"Not set"),
      // tlumaczymy sam fallback - prawdziwe dane uzytkownika (np. wpisany cennik) zostaja bez zmian.
      const original = el.textContent.trim();
      if (original === "Nie ustawiono" || original === "Not set") {
        el.textContent = dt("not_set");
      }
    });
    document.getElementById('swTitle').innerHTML = dt('widget_title_html');
    const days = dt('days');
    document.querySelectorAll('#chartDays span').forEach((el, i) => { el.textContent = days[i]; });
  }

  window.setLang = function(lang){
    currentLang = lang;
    document.getElementById('langPl').classList.toggle('active', lang === 'pl');
    document.getElementById('langEn').classList.toggle('active', lang === 'en');
    applyDashLang();
    if (typeof window.setVoiceStatus === 'function' && window.lastVoiceReady !== undefined) {
      window.setVoiceStatus(window.lastVoiceReady);
    }
  };

  window.showTab = function(tab){
    // Jesli klikasz te sama zakladke, ktora juz jest aktywna - zwin z powrotem do "Moj asystent"
    if (tab === currentTab && tab === 'quickcall') {
      tab = 'assistant';
    }
    currentTab = tab;
    document.getElementById('tab-assistant').classList.toggle('active', tab === 'assistant');
    document.getElementById('tab-quickcall').classList.toggle('active', tab === 'quickcall');
    document.getElementById('section-assistant').style.display = tab === 'assistant' ? 'block' : 'none';
    document.getElementById('section-quickcall').style.display = tab === 'quickcall' ? 'block' : 'none';
  };

  window.editField = function(name){
    document.querySelector(`[data-field="${name}"]`).style.display = 'none';
    document.querySelector(`[data-input="${name}"]`).style.display = 'block';
    document.querySelector(`[data-savebtn="${name}"]`).style.display = 'inline-block';
  };

  window.quickCall = async function(){
    const task = document.getElementById('taskInput').value.trim();
    const countryCode = document.getElementById('phoneCountryCode').value;
    const phoneRaw = document.getElementById('phoneInput').value.trim().replace(/\\s+/g, '');
    const status = document.getElementById('quickCallStatus');
    if(!task || !phoneRaw){ status.textContent = dt('qc_fill'); status.style.color = '#c0392b'; return; }

    // Jesli uzytkownik sam wpisal numer z + na poczatku, uzyj go bez zmian; inaczej dolacz wybrany kod kraju
    const phone = phoneRaw.startsWith('+') ? phoneRaw : countryCode + phoneRaw.replace(/^0+/, '');

    status.textContent = dt('qc_calling');
    status.style.color = '#888';

    try {
      const resp = await fetch('/start-outbound-call', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ phone_number: phone, task: task })
      });
      const result = await resp.json();
      if (!resp.ok || result.error) {
        status.textContent = 'Blad: ' + (result.error || 'nieznany blad');
        status.style.color = '#c0392b';
        return;
      }
      status.textContent = 'Dzwonie do ' + phone + '... (ID polaczenia: ' + result.call_sid + ')';
      status.style.color = '#1e8449';
    } catch (e) {
      status.textContent = 'Blad polaczenia: ' + e.message;
      status.style.color = '#c0392b';
    }
  };

  setLang(currentLang);
</script>

<script type="module">
  import { initializeApp } from "https://www.gstatic.com/firebasejs/10.13.0/firebase-app.js";
  import { getAuth, onAuthStateChanged } from "https://www.gstatic.com/firebasejs/10.13.0/firebase-auth.js";
  import { getFirestore, doc, getDoc, updateDoc, collection, query, where, onSnapshot } from "https://www.gstatic.com/firebasejs/10.13.0/firebase-firestore.js";

  const firebaseConfig = {{ firebase_config | tojson }};
  const app = initializeApp(firebaseConfig);
  const auth = getAuth(app);
  const db = getFirestore(app);

  let currentUid = null;

  onAuthStateChanged(auth, async (user) => {
    if (!user) return;
    currentUid = user.uid;
    const snap = await getDoc(doc(db, "users", user.uid));
    const data = snap.exists() ? snap.data() : {};
    setVoiceStatus(!!data.voiceId);
    document.getElementById('botLangSelect').value = data.botLanguage || 'pl';

    listenForHints(user.uid);

    ["companyName", "pricing", "hours", "rules"].forEach((name) => {
      const val = data[name];
      if (val) {
        const displayEl = document.querySelector(`[data-field="${name}"]`);
        const inputEl = document.querySelector(`[data-input="${name}"]`);
        if (displayEl) displayEl.textContent = val;
        if (inputEl) inputEl.value = val;
      }
    });
  });

  function listenForHints(uid){
    const hintsQuery = query(collection(db, "hints"), where("uid", "==", uid), where("answered", "==", false));
    onSnapshot(hintsQuery, (snapshot) => {
      const box = document.getElementById("sufBox");
      if (!box) return;
      if (snapshot.empty) {
        box.style.display = "none";
        return;
      }
      const hintDoc = snapshot.docs[0];
      const data = hintDoc.data();
      box.style.display = "block";
      document.getElementById("sufQuestion").textContent = data.question || "Bot potrzebuje podpowiedzi.";
      box.dataset.callSid = hintDoc.id;
    });
  }

  window.sendHint = async function(){
    const box = document.getElementById("sufBox");
    const callSid = box.dataset.callSid;
    const input = document.getElementById("sufInput");
    const value = input.value.trim();
    if (!callSid || !value) return;
    await updateDoc(doc(db, "hints", callSid), { hint: value, answered: true });
    input.value = "";
    box.style.display = "none";
  };

  window.saveField = async function(name){
    if(!currentUid) return;
    const value = document.querySelector(`[data-input="${name}"]`).value.trim();
    await updateDoc(doc(db, "users", currentUid), { [name]: value });
    const displayEl = document.querySelector(`[data-field="${name}"]`);
    displayEl.textContent = value || "Nie ustawiono";
    displayEl.style.display = 'block';
    document.querySelector(`[data-input="${name}"]`).style.display = 'none';
    document.querySelector(`[data-savebtn="${name}"]`).style.display = 'none';
  };

  window.saveBotLanguage = async function(){
    if(!currentUid) return;
    const value = document.getElementById('botLangSelect').value;
    await updateDoc(doc(db, "users", currentUid), { botLanguage: value });
  };

  window.setVoiceStatus = function(ready){
    window.lastVoiceReady = ready;
    const statusEl = document.getElementById("voiceStatus");
    if (ready) {
      statusEl.innerHTML = '<span class="voice-ready-dot"></span>' + dt('voice_ready_text');
      statusEl.className = "voice-ready";
    } else {
      statusEl.textContent = dt('voice_not_ready_text');
      statusEl.className = "";
    }
  }
  const setVoiceStatus = window.setVoiceStatus;
</script>
</script>
<script src="https://unpkg.com/lucide@latest/dist/umd/lucide.js"></script>
<script>lucide.createIcons();</script>
</body>
</html>
"""

VOICE_PAGE = """
<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>EchoLine - Mój głos</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
  *{box-sizing:border-box;margin:0;padding:0;}
  .bg-particles{position:fixed;inset:0;overflow:hidden;pointer-events:none;z-index:0;}
  .bg-particles span{position:absolute;bottom:-10px;border-radius:50%;background:#7c6aff;opacity:0;animation:floatDust linear infinite;}
  @keyframes floatDust{
    0%{transform:translateY(0) translateX(0);opacity:0;}
    10%{opacity:0.4;}
    90%{opacity:0.4;}
    100%{transform:translateY(-105vh) translateX(30px);opacity:0;}
  }
  .langbtn{border:1px solid #eee;background:#fff;color:#999;}
  .langbtn.active{background:#111;color:#fff;border-color:#111;}
  body{font-family:'Inter',sans-serif;background:#fff;color:#111;display:flex;min-height:100vh;}

  @keyframes riseIn{from{opacity:0;transform:translateY(10px);}to{opacity:1;transform:none;}}
  .rise{animation:riseIn .5s cubic-bezier(.16,1,.3,1) both;}

  /* SIDEBAR */
  .sidebar{width:230px;flex-shrink:0;border-right:1px solid #eee;padding:20px 12px;display:flex;flex-direction:column;}
  .logo{font-size:15px;font-weight:800;padding:8px 8px 20px;letter-spacing:-0.01em;display:flex;align-items:center;gap:9px;}
  .logo-dot{width:22px;height:22px;border-radius:50%;background:radial-gradient(circle at 30% 30%,#a9c9ff,#7c6aff 60%,#5a4bd4);flex-shrink:0;box-shadow:0 0 14px rgba(124,106,255,0.4);}
  .nav-item{display:flex;align-items:center;gap:10px;padding:9px 10px;border-radius:9px;font-size:13.5px;font-weight:500;color:#555;text-decoration:none;margin-bottom:2px;cursor:pointer;}
  .nav-item:hover{background:#f5f5f7;}
  .nav-item.active{background:linear-gradient(135deg,#7c6aff,#5dadff);color:#fff;box-shadow:0 6px 16px rgba(124,106,255,0.3);}
  .nav-icon{width:17px;height:17px;flex-shrink:0;stroke:#666;fill:none;stroke-width:1.8;}
  .nav-item.active .nav-icon{stroke:#fff;}
  .nav-section-label{font-size:10.5px;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;color:#bbb;padding:16px 10px 6px;}

  .sidebar-widget{margin-top:auto;background:linear-gradient(160deg,#f2f0ff,#eef6ff);border-radius:16px;padding:18px;text-align:left;}
  .sidebar-widget .sw-title{font-size:12.5px;font-weight:700;color:#5a4bd4;line-height:1.4;margin-bottom:14px;}
  .sw-orbit{width:76px;height:76px;margin:6px auto 14px;position:relative;}
  .sw-sphere{width:44px;height:44px;border-radius:50%;background:radial-gradient(circle at 30% 30%,#c9d9ff,#7c6aff 55%,#4f3fcf);position:absolute;top:16px;left:16px;box-shadow:0 0 22px rgba(124,106,255,0.5);}
  .sw-ring{position:absolute;inset:0;border:1.5px solid rgba(124,106,255,0.35);border-radius:50%;transform:rotate(-20deg) scaleY(0.42);}
  .sw-link{display:flex;align-items:center;gap:6px;font-size:12px;font-weight:600;color:#5a4bd4;text-decoration:none;}

  /* MAIN LAYOUT: srodek + panel boczny */
  .main{flex:1;display:flex;min-width:0;}
  .center{flex:1;padding:64px 36px 32px;min-width:0;}
  .center-head{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px;}
  .center-head h1{font-size:28px;font-weight:800;letter-spacing:-0.01em;margin-bottom:6px;}
  .center-head p{font-size:14px;color:#888;}
  .howto-btn{display:flex;align-items:center;gap:7px;padding:9px 16px;border-radius:100px;border:1px solid #eee;background:#fff;font-size:13px;font-weight:600;color:#555;cursor:pointer;white-space:nowrap;}
  .howto-btn svg{width:15px;height:15px;stroke:#999;fill:none;stroke-width:1.8;}

  /* STAGE - orb */
  .stage{position:relative;height:360px;display:flex;align-items:center;justify-content:center;margin:20px 0 8px;}
  .stage-glow{position:absolute;width:340px;height:340px;border-radius:50%;background:radial-gradient(circle,rgba(124,106,255,0.14),transparent 70%);}
  .wave-svg{position:absolute;width:100%;height:100%;top:0;left:0;pointer-events:none;}
  .orb-shadow{position:absolute;bottom:18px;width:180px;height:24px;background:radial-gradient(ellipse,rgba(124,106,255,0.25),transparent 75%);border-radius:50%;}

  .idle-orb{width:210px;height:210px;border-radius:50%;position:relative;z-index:2;
    background:radial-gradient(circle at 32% 28%,rgba(215,225,255,0.95),rgba(124,106,255,0.7) 55%,rgba(93,140,255,0.55) 100%);
    box-shadow:0 0 70px rgba(124,106,255,0.4), inset 0 0 40px rgba(255,255,255,0.5), inset 0 0 2px rgba(255,255,255,0.9);
    animation:breathe 3.4s ease-in-out infinite;
    display:flex;align-items:center;justify-content:center;overflow:hidden;}
  @keyframes breathe{0%,100%{transform:scale(1);}50%{transform:scale(1.045);}}
  .orb-ring{position:absolute;width:250px;height:250px;border-radius:50%;border:1px solid rgba(124,106,255,0.3);z-index:1;}

  .spark{position:absolute;border-radius:50%;background:#fff;opacity:0;animation:sparkFloat 4.5s ease-in-out infinite;box-shadow:0 0 6px 1px rgba(255,255,255,0.8);}
  @keyframes sparkFloat{0%{opacity:0;transform:translate(0,0) scale(0.4);}20%{opacity:0.95;}100%{opacity:0;transform:translate(var(--dx),var(--dy)) scale(1.3);}}

  #waveCanvas{position:relative;z-index:2;}

  .status-row{display:flex;align-items:center;justify-content:center;gap:8px;margin-top:6px;}
  .status-dot{width:8px;height:8px;border-radius:50%;background:#7c6aff;}
  .status-row b{font-size:15px;font-weight:700;}
  .status-sub{text-align:center;font-size:13px;color:#999;margin-top:4px;margin-bottom:22px;}
  .voice-ready .status-dot{background:#22d3a0;}

  .record-btn{display:flex;align-items:center;gap:10px;justify-content:center;position:relative;width:260px;margin:0 auto;padding:16px 28px;border-radius:100px;border:none;background:linear-gradient(135deg,#7c6aff,#5dadff);color:#fff;font-weight:700;font-size:15px;cursor:pointer;box-shadow:0 14px 30px rgba(124,106,255,0.35);}
  .record-btn svg{width:18px;height:18px;stroke:#fff;fill:none;stroke-width:2;}
  .record-btn::before{content:"";position:absolute;inset:-7px;border-radius:100px;border:1.5px solid rgba(124,106,255,0.3);animation:ringPulse 2.4s ease-out infinite;}
  @keyframes ringPulse{0%{transform:scale(1);opacity:0.8;}100%{transform:scale(1.1);opacity:0;}}
  .record-hint{text-align:center;font-size:12.5px;color:#aaa;margin-top:14px;}

  .privacy-bar{display:flex;align-items:center;gap:10px;justify-content:center;margin-top:22px;padding:13px;background:#fafafa;border-radius:12px;font-size:12.5px;color:#888;}
  .privacy-bar svg{width:15px;height:15px;stroke:#aaa;fill:none;stroke-width:1.8;flex-shrink:0;}

  /* RIGHT PANEL */
  .rightcol{width:290px;flex-shrink:0;padding:64px 24px 32px 0;display:flex;flex-direction:column;gap:16px;}
  .panel-card{background:#fff;border:1px solid #eee;border-radius:16px;padding:20px;}
  .panel-card h4{font-size:13.5px;font-weight:700;display:flex;align-items:center;gap:8px;margin-bottom:14px;}
  .panel-card h4 svg{width:16px;height:16px;stroke:#7c6aff;fill:none;stroke-width:1.8;}

  .tip{display:flex;align-items:center;gap:9px;font-size:12.5px;color:#555;padding:6px 0;}
  .tip svg{width:15px;height:15px;flex-shrink:0;}
  .tip.done svg{stroke:#7c6aff;fill:#7c6aff;}
  .tip.pending svg{stroke:#ddd;fill:none;}

  .step-row{display:flex;gap:12px;position:relative;padding-bottom:18px;}
  .step-row:last-child{padding-bottom:0;}
  .step-row::before{content:"";position:absolute;left:11px;top:24px;bottom:0;width:1px;background:#eee;}
  .step-row:last-child::before{display:none;}
  .step-num{width:23px;height:23px;border-radius:50%;background:#f0f0f0;color:#999;font-size:11.5px;font-weight:700;display:flex;align-items:center;justify-content:center;flex-shrink:0;z-index:1;}
  .step-row.active .step-num{background:linear-gradient(135deg,#7c6aff,#5dadff);color:#fff;}
  .step-row.done .step-num{background:#22d3a0;color:#fff;}
  .step-title{font-size:13px;font-weight:700;}
  .step-sub{font-size:11.5px;color:#999;}

  .voice-item{display:flex;align-items:center;gap:10px;padding:10px 0;border-bottom:1px solid #f5f5f5;}
  .voice-item:last-of-type{border-bottom:none;}
  .play-btn{width:30px;height:30px;border-radius:50%;background:#f5f3ff;display:flex;align-items:center;justify-content:center;flex-shrink:0;cursor:pointer;}
  .play-btn svg{width:13px;height:13px;stroke:#7c6aff;fill:#7c6aff;}
  .voice-item-name{font-size:12.5px;font-weight:700;display:flex;align-items:center;gap:6px;}
  .voice-tag{font-size:10px;font-weight:700;background:#e8f8f0;color:#1e9e63;padding:2px 8px;border-radius:100px;}
  .voice-item-date{font-size:11px;color:#999;}
  .add-voice-btn{width:100%;margin-top:10px;padding:11px;border-radius:10px;border:1.5px dashed #d9d2ff;background:#fbfaff;color:#7c6aff;font-weight:700;font-size:12.5px;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:6px;}
  .add-voice-btn svg{width:14px;height:14px;stroke:#7c6aff;fill:none;stroke-width:2;}
  .empty-voices{font-size:12.5px;color:#aaa;text-align:center;padding:10px 0;}

  @media (max-width: 1100px) {
    .main{flex-direction:column;}
    .rightcol{width:100%;padding:0 36px 32px;flex-direction:row;flex-wrap:wrap;}
    .panel-card{flex:1;min-width:220px;}
  }
  @media (max-width: 760px) {
    body{flex-direction:column;}
    .sidebar{width:100%;border-right:none;border-bottom:1px solid #eee;flex-direction:row;align-items:center;padding:12px 16px;overflow-x:auto;white-space:nowrap;}
    .sidebar-widget,.nav-section-label{display:none;}
    .logo{padding:0 14px 0 0;}
    .nav-item span.label{display:none;}
    .center{padding:20px 16px;}
    .center-head{flex-direction:column;gap:12px;}
    .center-head h1{font-size:22px;}
    .stage{height:260px;}
    .idle-orb{width:150px;height:150px;}
    .orb-ring{width:180px;height:180px;}
    #waveCanvas{width:150px !important;height:150px !important;}
    .record-btn{width:100%;}
    .rightcol{padding:0 16px 24px;flex-direction:column;}
    .panel-card{min-width:0;}
    .lang-switch-top{position:absolute !important;top:64px !important;right:12px !important;}
  }
</style>
</head>
<body>
<div class="bg-particles">
  <span style="left:6%;width:5px;height:5px;animation-duration:16s;animation-delay:0s;"></span>
  <span style="left:16%;width:3px;height:3px;animation-duration:12s;animation-delay:2s;"></span>
  <span style="left:28%;width:4px;height:4px;animation-duration:19s;animation-delay:4s;"></span>
  <span style="left:42%;width:3px;height:3px;animation-duration:14s;animation-delay:1s;"></span>
  <span style="left:58%;width:5px;height:5px;animation-duration:17s;animation-delay:6s;"></span>
  <span style="left:71%;width:3px;height:3px;animation-duration:13s;animation-delay:3s;"></span>
  <span style="left:83%;width:4px;height:4px;animation-duration:18s;animation-delay:5s;"></span>
  <span style="left:92%;width:3px;height:3px;animation-duration:15s;animation-delay:7s;"></span>
</div>

<div class="sidebar">
  <div class="logo"><span class="logo-dot"></span>EchoLine</div>
  <a class="nav-item{{ ' active' if active_page == 'dashboard' else '' }}" href="/dashboard">
    <i data-lucide="layout-dashboard" class="nav-icon"></i>
    <span class="label" data-i18n="nav_dashboard">Dashboard</span>
  </a>
  <a class="nav-item{{ ' active' if active_page == 'number' else '' }}" href="/numer-telefonu">
    <i data-lucide="phone" class="nav-icon"></i>
    <span class="label" data-i18n="nav_number">Numer telefonu</span>
  </a>
  <a class="nav-item{{ ' active' if active_page == 'voice' else '' }}" href="/moj-glos">
    <i data-lucide="mic" class="nav-icon"></i>
    <span class="label" data-i18n="nav_voice">Mój głos</span>
  </a>
  <a class="nav-item{{ ' active' if active_page == 'calls' else '' }}" href="/rozmowy">
    <i data-lucide="message-circle" class="nav-icon"></i>
    <span class="label" data-i18n="nav_calls">Rozmowy</span>
  </a>
  <a class="nav-item{{ ' active' if active_page == 'pricing' else '' }}" href="/cennik">
    <i data-lucide="credit-card" class="nav-icon"></i>
    <span class="label" data-i18n="nav_pricing">Cennik</span>
  </a>
  <div class="nav-section-label" data-i18n="nav_account">Konto</div>
  <a class="nav-item{{ ' active' if active_page == 'settings' else '' }}" href="/ustawienia">
    <i data-lucide="settings" class="nav-icon"></i>
    <span class="label" data-i18n="nav_settings">Ustawienia</span>
  </a>

  <div class="sidebar-widget">
    <div class="sw-title" id="swTitle">Twój asystent AI<br>24/7 gotowy do rozmów</div>
    <div class="sw-orbit"><div class="sw-ring"></div><div class="sw-sphere"></div></div>
    <a class="sw-link" href="/dashboard" data-i18n="widget_link">Zobacz statystyki →</a>
  </div>
</div>

<div class="main">
  <div class="lang-switch-top" style="display:flex;gap:4px;position:fixed;top:16px;right:24px;z-index:999;background:#fff;padding:5px;border-radius:100px;box-shadow:0 4px 16px -4px rgba(0,0,0,0.15);border:1px solid #f0f0f0;">
    <button id="langPl" onclick="setLang('pl')" class="langbtn" style="padding:4px 10px;border-radius:100px;font-size:11px;font-weight:700;cursor:pointer;">PL</button>
    <button id="langEn" onclick="setLang('en')" class="langbtn" style="padding:4px 10px;border-radius:100px;font-size:11px;font-weight:700;cursor:pointer;">EN</button>
  </div>
  <div class="center rise">
    <div class="center-head">
      <div>
        <h1 data-i18n="page_title">Sklonuj swój głos</h1>
        <p data-i18n="page_sub">Nagraj próbkę swojego głosu, a AI stworzy jego cyfrową kopię.</p>
      </div>
      <button class="howto-btn"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><path d="M9.1 9a3 3 0 0 1 5.8 1c0 2-3 2-3 4"/><line x1="12" y1="17" x2="12" y2="17"/></svg><span data-i18n="howto_btn">Jak to działa?</span></button>
    </div>

    <div class="stage">
      <div class="stage-glow"></div>
      <div class="orb-shadow"></div>

      <svg class="wave-svg" viewBox="0 0 600 360" preserveAspectRatio="xMidYMid meet">
        <path d="M0,180 C100,140 150,220 220,180 S320,140 380,180 S480,220 600,170" stroke="rgba(124,106,255,0.18)" stroke-width="2" fill="none"/>
        <path d="M0,200 C120,230 180,150 260,190 S360,230 420,190 S520,150 600,200" stroke="rgba(93,173,255,0.16)" stroke-width="2" fill="none"/>
      </svg>

      <div id="idleStage" style="position:relative;display:flex;align-items:center;justify-content:center;">
        <div class="orb-ring"></div>
        <div class="idle-orb" id="idleOrb"></div>
        <div class="spark" style="width:4px;height:4px;top:15%;left:20%;--dx:-25px;--dy:-20px;animation-delay:0s;"></div>
        <div class="spark" style="width:3px;height:3px;top:70%;left:78%;--dx:20px;--dy:25px;animation-delay:1.2s;"></div>
        <div class="spark" style="width:5px;height:5px;top:20%;left:75%;--dx:20px;--dy:-15px;animation-delay:2.1s;"></div>
        <div class="spark" style="width:3px;height:3px;top:78%;left:22%;--dx:-20px;--dy:20px;animation-delay:3s;"></div>
        <canvas id="waveCanvas" width="210" height="210" style="position:absolute;"></canvas>
      </div>

      <div id="processingWrap" style="display:none;flex-direction:column;align-items:center;">
        <div class="spinner-orb"></div>
      </div>
    </div>

    <div class="status-row" id="statusRow">
      <div class="status-dot"></div>
      <b id="statusTitle">Gotowy do nagrywania</b>
    </div>
    <p class="status-sub" id="statusSub">Wypowiedz tekst wyraźnie i naturalnie.</p>

    <button class="record-btn" id="recordBtn" onclick="toggleRecording()">
      <svg viewBox="0 0 24 24"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" x2="12" y1="19" y2="22"/></svg>
      <span id="recordBtnText">Nagraj</span>
    </button>
    <p class="record-hint" data-i18n="record_hint">Zalecamy nagrać 1-2 minuty czystego mówionego tekstu.</p>

    <div class="privacy-bar">
      <svg viewBox="0 0 24 24"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
      <span data-i18n="privacy_text">Twoje nagrania są prywatne i szyfrowane end-to-end.</span>
    </div>
  </div>

  <div class="rightcol rise">
    <div class="panel-card">
      <h4><i data-lucide="lightbulb"></i><span data-i18n="tips_title">Wskazówki</span></h4>
      <div class="tip done"><svg viewBox="0 0 24 24" fill="none" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M9 12l2 2 4-4"/></svg><span data-i18n="tip_1">Mów w cichym otoczeniu</span></div>
      <div class="tip done"><svg viewBox="0 0 24 24" fill="none" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M9 12l2 2 4-4"/></svg><span data-i18n="tip_2">Używaj naturalnego tempa</span></div>
      <div class="tip done"><svg viewBox="0 0 24 24" fill="none" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M9 12l2 2 4-4"/></svg><span data-i18n="tip_3">Rób krótkie przerwy</span></div>
      <div class="tip pending"><svg viewBox="0 0 24 24" fill="none" stroke-width="1.8"><circle cx="12" cy="12" r="9"/></svg><span data-i18n="tip_4">Unikaj szumów i echa</span></div>
    </div>

    <div class="panel-card">
      <h4><i data-lucide="list-checks"></i><span data-i18n="progress_title">Postęp klonowania</span></h4>
      <div class="step-row active" id="step1">
        <div class="step-num">1</div>
        <div><div class="step-title" data-i18n="step1_title">Nagrywanie próbki</div><div class="step-sub" data-i18n="step1_sub">Zarejestruj swój głos</div></div>
      </div>
      <div class="step-row" id="step2">
        <div class="step-num">2</div>
        <div><div class="step-title" data-i18n="step2_title">Przetwarzanie przez AI</div><div class="step-sub" data-i18n="step2_sub">Analiza cech głosu</div></div>
      </div>
      <div class="step-row" id="step3">
        <div class="step-num">3</div>
        <div><div class="step-title" data-i18n="step3_title">Głos gotowy</div><div class="step-sub" data-i18n="step3_sub">Gotowy do użycia</div></div>
      </div>
    </div>

    <div class="panel-card">
      <h4><i data-lucide="audio-lines"></i><span data-i18n="your_voices_title">Twoje głosy</span></h4>
      <div id="voicesList">
        <div class="empty-voices" data-i18n="no_voice_yet">Nie masz jeszcze żadnego głosu.</div>
      </div>
      <button class="add-voice-btn" onclick="document.getElementById('recordBtn').scrollIntoView({behavior:'smooth',block:'center'});"><svg viewBox="0 0 24 24"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg><span data-i18n="clone_new_voice">Sklonuj nowy głos</span></button>
    </div>

    <div class="panel-card">
      <h4><i data-lucide="library"></i><span data-i18n="library_title">Biblioteka głosów</span></h4>
      <p style="font-size:11.5px;color:#999;margin-bottom:10px;" data-i18n="library_desc">Nie chcesz nagrywać własnego głosu? Wybierz gotowy.</p>
      <select id="libLangSelect" onchange="loadVoiceLibrary()" style="width:100%;padding:8px 10px;border-radius:8px;border:1px solid #ddd;font-size:12.5px;margin-bottom:10px;font-family:inherit;">
        <option value="pl" data-i18n="lang_pl">Polski</option>
        <option value="en" data-i18n="lang_en">Angielski</option>
        <option value="de" data-i18n="lang_de">Niemiecki</option>
        <option value="es" data-i18n="lang_es">Hiszpański</option>
        <option value="fr" data-i18n="lang_fr">Francuski</option>
        <option value="it" data-i18n="lang_it">Włoski</option>
      </select>
      <div id="libraryList">
        <div class="empty-voices" data-i18n="loading_voices">Ładowanie głosów...</div>
      </div>
    </div>
  </div>
</div>

<style>
  .lib-voice{display:flex;align-items:center;gap:10px;padding:9px 0;border-bottom:1px solid #f5f5f5;}
  .lib-voice:last-child{border-bottom:none;}
  .lib-play{width:28px;height:28px;border-radius:50%;background:#f5f3ff;display:flex;align-items:center;justify-content:center;flex-shrink:0;cursor:pointer;border:none;}
  .lib-play svg{width:12px;height:12px;stroke:#7c6aff;fill:#7c6aff;}
  .lib-name{font-size:12.5px;font-weight:700;flex:1;}
  .lib-meta{font-size:10.5px;color:#999;}
  .lib-select{font-size:11px;font-weight:700;color:#7c6aff;background:#f5f3ff;border:none;padding:5px 10px;border-radius:8px;cursor:pointer;flex-shrink:0;}
  .lib-select:hover{background:#ece8ff;}
</style>

<style>
  .spinner-orb{width:120px;height:120px;border-radius:50%;
    background:conic-gradient(from 0deg,#7c6aff,#5dadff,#a9c9ff,#7c6aff);
    animation:morph 1.6s linear infinite;filter:blur(2px);}
  @keyframes morph{
    0%{transform:rotate(0deg) scale(1);border-radius:50%;}
    50%{transform:rotate(180deg) scale(0.94);border-radius:46% 54% 60% 40%;}
    100%{transform:rotate(360deg) scale(1);border-radius:50%;}
  }
</style>

<script>
  const VOICE_I18N = {
    pl: {
      nav_dashboard: 'Dashboard', nav_number: 'Numer telefonu', nav_voice: 'Mój głos',
      nav_calls: 'Rozmowy', nav_pricing: 'Cennik', nav_account: 'Konto', nav_settings: 'Ustawienia',
      widget_title_html: 'Twój asystent AI<br>24/7 gotowy do rozmów',
      widget_link: 'Zobacz statystyki →',
      page_title: 'Sklonuj swój głos',
      page_sub: 'Nagraj próbkę swojego głosu, a AI stworzy jego cyfrową kopię.',
      howto_btn: 'Jak to działa?',
      record_hint: 'Zalecamy nagrać 1-2 minuty czystego mówionego tekstu.',
      privacy_text: 'Twoje nagrania są prywatne i szyfrowane end-to-end.',
      tips_title: 'Wskazówki',
      tip_1: 'Mów w cichym otoczeniu',
      tip_2: 'Używaj naturalnego tempa',
      tip_3: 'Rób krótkie przerwy',
      tip_4: 'Unikaj szumów i echa',
      progress_title: 'Postęp klonowania',
      step1_title: 'Nagrywanie próbki', step1_sub: 'Zarejestruj swój głos',
      step2_title: 'Przetwarzanie przez AI', step2_sub: 'Analiza cech głosu',
      step3_title: 'Głos gotowy', step3_sub: 'Gotowy do użycia',
      your_voices_title: 'Twoje głosy',
      no_voice_yet: 'Nie masz jeszcze żadnego głosu.',
      clone_new_voice: 'Sklonuj nowy głos',
      library_title: 'Biblioteka głosów',
      library_desc: 'Nie chcesz nagrywać własnego głosu? Wybierz gotowy.',
      lang_pl: 'Polski', lang_en: 'Angielski', lang_de: 'Niemiecki',
      lang_es: 'Hiszpański', lang_fr: 'Francuski', lang_it: 'Włoski',
      loading_voices: 'Ładowanie głosów...',
      status_ready: 'Gotowy do nagrywania',
      status_ready_sub: 'Wypowiedz tekst wyraźnie i naturalnie.',
      status_done: 'Głos gotowy',
      status_done_sub: 'Twój cyfrowy głos jest aktywny i gotowy do użycia.',
      status_recording: 'Nagrywanie...',
      status_recording_sub: 'Mów teraz, kliknij ponownie aby zakończyć.',
      status_processing: 'Przetwarzanie',
      status_processing_sub: 'Analizujemy Twój głos...',
      status_error: 'Błąd klonowania',
      btn_record: 'Nagraj',
      btn_record_again: 'Nagraj ponownie',
      btn_stop: 'Zatrzymaj nagrywanie',
      your_voice_label: 'Twój głos',
      active_tag: 'Aktywny',
      click_to_listen: 'Kliknij, aby odsłuchać próbkę',
    },
    en: {
      nav_dashboard: 'Dashboard', nav_number: 'Phone number', nav_voice: 'My voice',
      nav_calls: 'Calls', nav_pricing: 'Pricing', nav_account: 'Account', nav_settings: 'Settings',
      widget_title_html: 'Your AI assistant<br>ready 24/7',
      widget_link: 'View statistics →',
      page_title: 'Clone your voice',
      page_sub: 'Record a sample of your voice, and AI will create its digital copy.',
      howto_btn: 'How does it work?',
      record_hint: 'We recommend recording 1-2 minutes of clear spoken text.',
      privacy_text: 'Your recordings are private and encrypted end-to-end.',
      tips_title: 'Tips',
      tip_1: 'Speak in a quiet environment',
      tip_2: 'Use a natural pace',
      tip_3: 'Take short pauses',
      tip_4: 'Avoid noise and echo',
      progress_title: 'Cloning progress',
      step1_title: 'Recording sample', step1_sub: 'Record your voice',
      step2_title: 'Processing by AI', step2_sub: 'Analyzing voice traits',
      step3_title: 'Voice ready', step3_sub: 'Ready to use',
      your_voices_title: 'Your voices',
      no_voice_yet: 'You do not have a voice yet.',
      clone_new_voice: 'Clone a new voice',
      library_title: 'Voice library',
      library_desc: 'Do not want to record your own voice? Choose a ready one.',
      lang_pl: 'Polish', lang_en: 'English', lang_de: 'German',
      lang_es: 'Spanish', lang_fr: 'French', lang_it: 'Italian',
      loading_voices: 'Loading voices...',
      status_ready: 'Ready to record',
      status_ready_sub: 'Speak clearly and naturally.',
      status_done: 'Voice ready',
      status_done_sub: 'Your digital voice is active and ready to use.',
      status_recording: 'Recording...',
      status_recording_sub: 'Speak now, click again to finish.',
      status_processing: 'Processing',
      status_processing_sub: 'Analyzing your voice...',
      status_error: 'Cloning error',
      btn_record: 'Record',
      btn_record_again: 'Record again',
      btn_stop: 'Stop recording',
      your_voice_label: 'Your voice',
      active_tag: 'Active',
      click_to_listen: 'Click to listen to the sample',
    }
  };

  let currentLang = (navigator.language || 'pl').slice(0, 2).toLowerCase() === 'pl' ? 'pl' : 'en';

  function vt(key){ return VOICE_I18N[currentLang][key] || key; }

  function applyVoiceLang(){
    document.querySelectorAll('[data-i18n]').forEach(function(el){
      el.textContent = vt(el.getAttribute('data-i18n'));
    });
    document.getElementById('swTitle').innerHTML = vt('widget_title_html');
    if (typeof window.refreshVoiceStatusText === 'function') window.refreshVoiceStatusText();
  }

  window.setLang = function(lang){
    currentLang = lang;
    document.getElementById('langPl').classList.toggle('active', lang === 'pl');
    document.getElementById('langEn').classList.toggle('active', lang === 'en');
    applyVoiceLang();
    if (typeof window.loadVoiceLibrary === 'function') window.loadVoiceLibrary();
  };

  setLang(currentLang);
</script>

<script type="module">
  import { initializeApp } from "https://www.gstatic.com/firebasejs/10.13.0/firebase-app.js";
  import { getAuth, onAuthStateChanged } from "https://www.gstatic.com/firebasejs/10.13.0/firebase-auth.js";
  import { getFirestore, doc, getDoc, updateDoc } from "https://www.gstatic.com/firebasejs/10.13.0/firebase-firestore.js";

  const firebaseConfig = {{ firebase_config | tojson }};
  const app = initializeApp(firebaseConfig);
  const auth = getAuth(app);
  const db = getFirestore(app);

  let currentUid = null;
  let existingVoiceId = null;

  onAuthStateChanged(auth, async (user) => {
    if (!user) return;
    currentUid = user.uid;
    const snap = await getDoc(doc(db, "users", user.uid));
    const data = snap.exists() ? snap.data() : {};
    existingVoiceId = data.voiceId || null;
    setVoiceStatus(!!data.voiceId);
  });

  // Wykryj jezyk przegladarki uzytkownika jako domyslny w selektorze
  (function detectLang(){
    const browserLang = (navigator.language || "pl").slice(0, 2).toLowerCase();
    const select = document.getElementById("libLangSelect");
    if (select && [...select.options].some(o => o.value === browserLang)) {
      select.value = browserLang;
    }
  })();

  window.loadVoiceLibrary = async function(){
    const list = document.getElementById("libraryList");
    const lang = document.getElementById("libLangSelect").value;
    list.innerHTML = `<div class="empty-voices">Ładowanie głosów...</div>`;
    try {
      const resp = await fetch("/voice-library?lang=" + lang);
      const result = await resp.json();
      if (!resp.ok || result.error || !result.voices || result.voices.length === 0) {
        list.innerHTML = `<div class="empty-voices">Brak dostepnych glosow dla tego jezyka.</div>`;
        return;
      }
      list.innerHTML = result.voices.map(v => `
        <div class="lib-voice">
          <button class="lib-play" onclick="playPreview('${v.preview_url}', this)"><svg viewBox="0 0 24 24"><polygon points="6 3 20 12 6 21 6 3"/></svg></button>
          <div style="flex:1;">
            <div class="lib-name">${v.name}</div>
            <div class="lib-meta">${v.gender || ""} ${v.accent ? "· " + v.accent : ""}</div>
          </div>
          <button class="lib-select" onclick="selectLibraryVoice('${v.voice_id}')">Wybierz</button>
        </div>
      `).join("");
    } catch (e) {
      list.innerHTML = `<div class="empty-voices">Blad ladowania: ${e.message}</div>`;
    }
  }

  loadVoiceLibrary();

  let currentPreviewAudio = null;

  window.playPreview = function(url, btn){
    if (!url) return;
    if (currentPreviewAudio) {
      currentPreviewAudio.pause();
      currentPreviewAudio.currentTime = 0;
    }
    currentPreviewAudio = new Audio(url);
    currentPreviewAudio.play();
  };

  window.selectLibraryVoice = async function(voiceId){
    if (!currentUid) return;
    existingVoiceId = voiceId;
    await updateDoc(doc(db, "users", currentUid), { voiceId: voiceId });
    setVoiceStatus(true);
  };

  window.testVoice = async function(){
    const hint = document.getElementById("playHint");
    if (!existingVoiceId) return;
    if (hint) { hint.textContent = "Generuję próbkę..."; }
    try {
      const resp = await fetch("/test-voice", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ voice_id: existingVoiceId })
      });
      if (!resp.ok) {
        const errText = await resp.text();
        if (hint) hint.textContent = "Blad: " + errText.slice(0, 100);
        return;
      }
      const blob = await resp.blob();
      const audioUrl = URL.createObjectURL(blob);
      if (currentPreviewAudio) { currentPreviewAudio.pause(); currentPreviewAudio.currentTime = 0; }
      currentPreviewAudio = new Audio(audioUrl);
      if (hint) hint.textContent = "Odtwarzanie...";
      currentPreviewAudio.play();
      currentPreviewAudio.onended = () => { if (hint) hint.textContent = "Kliknij, aby odsluchac probke"; };
    } catch (e) {
      if (hint) hint.textContent = "Blad polaczenia: " + e.message;
    }
  };

  function setSteps(stage){
    // stage: 1 = nagrywanie, 2 = przetwarzanie, 3 = gotowe
    for (let i = 1; i <= 3; i++) {
      const el = document.getElementById("step" + i);
      el.classList.remove("active", "done");
      if (i < stage) el.classList.add("done");
      if (i === stage) el.classList.add("active");
    }
  }

  let lastVoiceReady = false;

  window.refreshVoiceStatusText = function(){
    setVoiceStatus(lastVoiceReady);
  };

  function setVoiceStatus(ready){
    lastVoiceReady = ready;
    const statusRow = document.getElementById("statusRow");
    const title = document.getElementById("statusTitle");
    const sub = document.getElementById("statusSub");
    const btnText = document.getElementById("recordBtnText");
    const voicesList = document.getElementById("voicesList");

    if (ready) {
      statusRow.classList.add("voice-ready");
      title.textContent = vt("status_done");
      sub.textContent = vt("status_done_sub");
      btnText.textContent = vt("btn_record_again");
      setSteps(3);
      voicesList.innerHTML = `
        <div class="voice-item">
          <div class="play-btn" id="playBtn" onclick="testVoice()"><svg viewBox="0 0 24 24"><polygon points="6 3 20 12 6 21 6 3"/></svg></div>
          <div style="flex:1;">
            <div class="voice-item-name">${vt("your_voice_label")} <span class="voice-tag">${vt("active_tag")}</span></div>
            <div class="voice-item-date" id="playHint">${vt("click_to_listen")}</div>
          </div>
        </div>`;
    } else {
      statusRow.classList.remove("voice-ready");
      title.textContent = vt("status_ready");
      sub.textContent = vt("status_ready_sub");
      btnText.textContent = vt("btn_record");
      setSteps(1);
      voicesList.innerHTML = `<div class="empty-voices">${vt("no_voice_yet")}</div>`;
    }
  }

  let mediaRecorder, chunks = [], recording = false;
  let audioCtx, analyser, timeData, animId, startTime;
  let level = 0, rippleT = 0;
  let waveW = 210, waveH = 210;

  function drawOrb(){
    const canvas = document.getElementById("waveCanvas");
    const ctx = canvas.getContext("2d");
    analyser.getByteTimeDomainData(timeData);

    let sum = 0;
    for (let i = 0; i < timeData.length; i++) {
      const v = (timeData[i] - 128) / 128;
      sum += v * v;
    }
    const rms = Math.sqrt(sum / timeData.length);
    level = level * 0.8 + Math.min(rms * 3.2, 1) * 0.2;

    ctx.clearRect(0, 0, waveW, waveH);
    const cx = waveW / 2, cy = waveH / 2;

    rippleT += 0.015 + level * 0.05;
    for (let i = 0; i < 3; i++) {
      const phase = (rippleT + i / 3) % 1;
      const ringR = 60 + phase * 45;
      const alpha = (1 - phase) * 0.3;
      ctx.beginPath();
      ctx.strokeStyle = `rgba(255,255,255,${alpha})`;
      ctx.lineWidth = 2;
      ctx.arc(cx, cy, ringR, 0, Math.PI * 2);
      ctx.stroke();
    }

    const scale = 1 + level * 0.08;
    document.getElementById("idleOrb").style.transform = `scale(${scale})`;

    animId = requestAnimationFrame(drawOrb);
  }

  function sizeCanvas(){
    const canvas = document.getElementById("waveCanvas");
    canvas.width = waveW;
    canvas.height = waveH;
  }

  window.toggleRecording = async function(){
    const btn = document.getElementById("recordBtn");
    const btnText = document.getElementById("recordBtnText");
    const processingWrap = document.getElementById("processingWrap");
    const idleStage = document.getElementById("idleStage");
    const title = document.getElementById("statusTitle");
    const sub = document.getElementById("statusSub");
    const cancelBtn = document.getElementById("cancelBtn");

    if (!recording) {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        const source = audioCtx.createMediaStreamSource(stream);
        analyser = audioCtx.createAnalyser();
        analyser.fftSize = 512;
        timeData = new Uint8Array(analyser.fftSize);
        source.connect(analyser);
        sizeCanvas();
        drawOrb();

        recordingCancelled = false;
        mediaRecorder = new MediaRecorder(stream);
        chunks = [];
        mediaRecorder.ondataavailable = (e) => chunks.push(e.data);
        mediaRecorder.onstop = () => {
          if (recordingCancelled) {
            resetToIdle();
          } else {
            uploadRecording();
          }
        };
        mediaRecorder.start();
        recording = true;

        btnText.textContent = vt("btn_stop");
        title.textContent = vt("status_recording");
        sub.textContent = vt("status_recording_sub");
        if (cancelBtn) cancelBtn.style.display = "block";
        setSteps(1);
      } catch (e) {
        alert("Nie udalo sie uzyskac dostepu do mikrofonu: " + e.message);
      }
    } else {
      mediaRecorder.stop();
      recording = false;
      cancelAnimationFrame(animId);
      idleStage.style.display = "none";
      processingWrap.style.display = "flex";
      btn.style.display = "none";
      if (cancelBtn) cancelBtn.style.display = "none";
      title.textContent = vt("status_processing");
      sub.textContent = vt("status_processing_sub");
      setSteps(2);
    }
  };

  async function uploadRecording(){
    const btn = document.getElementById("recordBtn");
    const processingWrap = document.getElementById("processingWrap");
    const idleStage = document.getElementById("idleStage");

    function resetUI(){
      processingWrap.style.display = "none";
      idleStage.style.display = "flex";
      btn.style.display = "flex";
    }

    function showError(msg){
      resetUI();
      document.getElementById("statusTitle").textContent = vt("status_error");
      document.getElementById("statusSub").textContent = msg;
      document.getElementById("statusSub").style.color = "#c0392b";
      setSteps(1);
    }

    try {
      const blob = new Blob(chunks, { type: "audio/webm" });
      if (blob.size === 0) {
        showError("Nagranie jest puste - sprawdz mikrofon i sprobuj ponownie.");
        return;
      }

      const formData = new FormData();
      formData.append("audio", blob, "sample.webm");
      if (existingVoiceId) formData.append("old_voice_id", existingVoiceId);

      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 30000);

      const resp = await fetch("/clone-voice", { method: "POST", body: formData, signal: controller.signal });
      clearTimeout(timeoutId);

      if (!resp.ok) {
        const text = await resp.text();
        showError("Serwer zwrocil blad (" + resp.status + "): " + text.slice(0, 200));
        return;
      }

      const result = await resp.json();

      if (result.voice_id && currentUid) {
        await updateDoc(doc(db, "users", currentUid), { voiceId: result.voice_id });
        resetUI();
        setVoiceStatus(true);
      } else {
        showError(result.error || "Nieznany blad - brak voice_id w odpowiedzi.");
      }
    } catch (e) {
      if (e.name === "AbortError") {
        showError("Przekroczono czas oczekiwania (30s) - sprobuj ponownie z krotszym nagraniem.");
      } else {
        showError("Blad polaczenia: " + e.message);
      }
    }
  }
</script>
<script src="https://unpkg.com/lucide@latest/dist/umd/lucide.js"></script>
<script>lucide.createIcons();</script>
</body>
</html>
"""

NUMBER_PAGE = """
<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>EchoLine - Numer telefonu</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
  *{box-sizing:border-box;margin:0;padding:0;}
  .bg-particles{position:fixed;inset:0;overflow:hidden;pointer-events:none;z-index:0;}
  .bg-particles span{position:absolute;bottom:-10px;border-radius:50%;background:#7c6aff;opacity:0;animation:floatDust linear infinite;}
  @keyframes floatDust{
    0%{transform:translateY(0) translateX(0);opacity:0;}
    10%{opacity:0.4;}
    90%{opacity:0.4;}
    100%{transform:translateY(-105vh) translateX(30px);opacity:0;}
  }
  .langbtn{border:1px solid #eee;background:#fff;color:#999;}
  .langbtn.active{background:#111;color:#fff;border-color:#111;}
  body{font-family:'Inter',sans-serif;background:#fff;color:#111;display:flex;min-height:100vh;}

  @keyframes riseIn{from{opacity:0;transform:translateY(10px);}to{opacity:1;transform:none;}}
  .rise{animation:riseIn .5s cubic-bezier(.16,1,.3,1) both;}

  /* SIDEBAR - identyczne jak reszta aplikacji */
  .sidebar{width:230px;flex-shrink:0;border-right:1px solid #eee;padding:20px 12px;display:flex;flex-direction:column;}
  .logo{font-size:15px;font-weight:800;padding:8px 8px 20px;letter-spacing:-0.01em;display:flex;align-items:center;gap:9px;}
  .logo-dot{width:22px;height:22px;border-radius:50%;background:radial-gradient(circle at 30% 30%,#a9c9ff,#7c6aff 60%,#5a4bd4);flex-shrink:0;box-shadow:0 0 14px rgba(124,106,255,0.4);}
  .nav-item{display:flex;align-items:center;gap:10px;padding:9px 10px;border-radius:9px;font-size:13.5px;font-weight:500;color:#555;text-decoration:none;margin-bottom:2px;cursor:pointer;}
  .nav-item:hover{background:#f5f5f7;}
  .nav-item.active{background:linear-gradient(135deg,#7c6aff,#5dadff);color:#fff;box-shadow:0 6px 16px rgba(124,106,255,0.3);}
  .nav-icon{width:17px;height:17px;flex-shrink:0;stroke:#666;fill:none;stroke-width:1.8;}
  .nav-item.active .nav-icon{stroke:#fff;}
  .nav-section-label{font-size:10.5px;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;color:#bbb;padding:16px 10px 6px;}

  .sidebar-widget{margin-top:auto;background:linear-gradient(160deg,#f2f0ff,#eef6ff);border-radius:16px;padding:18px;text-align:left;}
  .sidebar-widget .sw-title{font-size:12.5px;font-weight:700;color:#5a4bd4;line-height:1.4;margin-bottom:14px;}
  .sw-orbit{width:76px;height:76px;margin:6px auto 14px;position:relative;}
  .sw-sphere{width:44px;height:44px;border-radius:50%;background:radial-gradient(circle at 30% 30%,#c9d9ff,#7c6aff 55%,#4f3fcf);position:absolute;top:16px;left:16px;box-shadow:0 0 22px rgba(124,106,255,0.5);}
  .sw-ring{position:absolute;inset:0;border:1.5px solid rgba(124,106,255,0.35);border-radius:50%;transform:rotate(-20deg) scaleY(0.42);}
  .sw-link{display:flex;align-items:center;gap:6px;font-size:12px;font-weight:600;color:#5a4bd4;text-decoration:none;}

  /* MAIN */
  .main{flex:1;display:flex;min-width:0;}
  .center{flex:1;padding:64px 36px 32px;min-width:0;}
  .center-head h1{font-size:26px;font-weight:800;letter-spacing:-0.01em;margin-bottom:6px;position:relative;}
  .center-head p{font-size:14px;color:#888;margin-bottom:26px;}

  .hero-orb-deco{position:absolute;top:20px;right:40px;width:80px;height:80px;display:none;}

  .step-label{display:flex;align-items:center;gap:8px;font-size:14.5px;font-weight:700;margin:26px 0 12px;}
  .step-label svg{width:16px;height:16px;stroke:#7c6aff;fill:none;stroke-width:1.8;}
  .step-label:first-of-type{margin-top:0;}

  /* COUNTRY CARDS */
  .country-row{display:flex;gap:12px;overflow-x:auto;padding-bottom:4px;}
  .country-card{flex:0 0 auto;min-width:140px;border:1.5px solid #eee;border-radius:13px;padding:14px 16px;display:flex;align-items:center;gap:10px;cursor:pointer;position:relative;transition:all .15s;}
  .country-card:hover{border-color:#d9d2ff;}
  .country-card.selected{border-color:#7c6aff;background:#f8f7ff;box-shadow:0 4px 14px rgba(124,106,255,0.12);}
  .country-flag{width:30px;height:30px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:15px;flex-shrink:0;background:#f0f0f0;}
  .country-name{font-size:13px;font-weight:700;}
  .country-code{font-size:11.5px;color:#999;}
  .selected-check{position:absolute;top:8px;right:8px;width:16px;height:16px;border-radius:50%;background:#7c6aff;display:none;align-items:center;justify-content:center;}
  .selected-check svg{width:10px;height:10px;stroke:#fff;fill:none;stroke-width:3;}
  .country-card.selected .selected-check{display:flex;}

  /* SEARCH BUTTON */
  .search-btn{width:100%;padding:16px;border-radius:100px;border:none;background:linear-gradient(135deg,#7c6aff,#5dadff);color:#fff;font-weight:700;font-size:15px;cursor:pointer;box-shadow:0 12px 28px rgba(124,106,255,0.3);display:flex;align-items:center;justify-content:center;gap:8px;}
  .search-btn svg{width:16px;height:16px;stroke:#fff;fill:none;stroke-width:2;}
  .search-btn:hover{opacity:0.93;}
  .search-btn:disabled{opacity:0.6;cursor:not-allowed;}

  /* RESULTS */
  #resultsSection{display:none;}
  .number-item{display:flex;align-items:center;gap:14px;border:1.5px solid #eee;border-radius:13px;padding:14px 16px;margin-bottom:10px;cursor:pointer;transition:all .15s;}
  .number-item:hover{border-color:#d9d2ff;}
  .number-item.selected{border-color:#7c6aff;background:#f8f7ff;}
  .radio-dot{width:20px;height:20px;border-radius:50%;border:2px solid #ddd;flex-shrink:0;display:flex;align-items:center;justify-content:center;}
  .number-item.selected .radio-dot{border-color:#7c6aff;}
  .radio-dot::after{content:"";width:10px;height:10px;border-radius:50%;background:#7c6aff;display:none;}
  .number-item.selected .radio-dot::after{display:block;}
  .number-phone{font-size:15px;font-weight:700;}
  .number-region{font-size:12px;color:#999;text-align:right;}
  .number-tag{font-size:10.5px;font-weight:700;background:#f5f3ff;color:#7c6aff;padding:2px 9px;border-radius:100px;margin-left:8px;}

  .activate-btn{width:100%;padding:16px;border-radius:100px;border:none;background:linear-gradient(135deg,#7c6aff,#5dadff);color:#fff;font-weight:700;font-size:15px;cursor:pointer;box-shadow:0 12px 28px rgba(124,106,255,0.3);display:flex;align-items:center;justify-content:center;gap:8px;margin-top:16px;}
  .activate-btn svg{width:16px;height:16px;stroke:#fff;fill:none;stroke-width:2;}
  .activate-btn:disabled{opacity:0.5;cursor:not-allowed;}

  .privacy-bar{display:flex;align-items:center;gap:12px;margin-top:24px;padding:16px;background:#fafafa;border-radius:12px;}
  .privacy-bar svg{width:18px;height:18px;stroke:#7c6aff;fill:none;stroke-width:1.8;flex-shrink:0;}
  .privacy-bar b{display:block;font-size:13px;}
  .privacy-bar span{font-size:11.5px;color:#999;}

  #searchError, #buyError{display:none;font-size:13px;color:#c0392b;background:#fdecec;padding:10px 14px;border-radius:10px;margin-bottom:14px;}
  #searchLoading{display:none;text-align:center;padding:20px;font-size:13px;color:#888;}
  .spinner{width:18px;height:18px;border:2px solid #eee;border-top-color:#7c6aff;border-radius:50%;animation:spin 0.7s linear infinite;margin:0 auto 8px;}
  @keyframes spin{to{transform:rotate(360deg);}}

  /* RIGHT PANEL */
  .rightcol{width:290px;flex-shrink:0;padding:64px 24px 32px 0;display:flex;flex-direction:column;gap:16px;}
  .panel-card{background:#fff;border:1px solid #eee;border-radius:16px;padding:20px;}
  .panel-card h4{font-size:13.5px;font-weight:700;display:flex;align-items:center;gap:8px;margin-bottom:14px;}
  .panel-card h4 svg{width:16px;height:16px;stroke:#7c6aff;fill:none;stroke-width:1.8;}

  .tip{display:flex;align-items:center;gap:9px;font-size:12.5px;color:#555;padding:6px 0;}
  .tip svg{width:15px;height:15px;flex-shrink:0;stroke:#7c6aff;fill:#7c6aff;}

  .step-row{display:flex;gap:12px;position:relative;padding-bottom:18px;}
  .step-row:last-child{padding-bottom:0;}
  .step-row::before{content:"";position:absolute;left:11px;top:24px;bottom:0;width:1px;background:#eee;}
  .step-row:last-child::before{display:none;}
  .step-num{width:23px;height:23px;border-radius:50%;background:#f0f0f0;color:#999;font-size:11.5px;font-weight:700;display:flex;align-items:center;justify-content:center;flex-shrink:0;z-index:1;}
  .step-row.active .step-num{background:linear-gradient(135deg,#7c6aff,#5dadff);color:#fff;}
  .step-row.done .step-num{background:#22d3a0;color:#fff;}
  .step-title{font-size:13px;font-weight:700;}
  .step-sub{font-size:11.5px;color:#999;}

  .empty-number{text-align:center;padding:10px 0;}
  .empty-icon{width:64px;height:64px;border-radius:50%;background:#f5f3ff;display:flex;align-items:center;justify-content:center;margin:0 auto 14px;}
  .empty-icon svg{width:26px;height:26px;stroke:#c9c2ff;fill:none;stroke-width:1.6;}
  .empty-number b{display:block;font-size:13px;margin-bottom:4px;}
  .empty-number p{font-size:11.5px;color:#999;line-height:1.4;margin-bottom:10px;}
  .empty-number a{font-size:12.5px;color:#7c6aff;font-weight:700;text-decoration:none;}

  .active-number-tag{display:inline-block;font-size:10.5px;font-weight:700;background:#e8f8f0;color:#1e9e63;padding:3px 10px;border-radius:100px;margin-bottom:8px;}
  .active-number-phone{font-size:16px;font-weight:800;margin-bottom:4px;}
  .active-number-date{font-size:11.5px;color:#999;}

  @media (max-width: 1100px) {
    .main{flex-direction:column;}
    .rightcol{width:100%;padding:0 36px 32px;flex-direction:row;flex-wrap:wrap;}
    .panel-card{flex:1;min-width:220px;}
  }
  @media (max-width: 760px) {
    body{flex-direction:column;}
    .sidebar{width:100%;border-right:none;border-bottom:1px solid #eee;flex-direction:row;align-items:center;padding:12px 16px;overflow-x:auto;white-space:nowrap;}
    .sidebar-widget,.nav-section-label{display:none;}
    .logo{padding:0 14px 0 0;}
    .nav-item span.label{display:none;}
    .center{padding:20px 16px;}
    .center-head h1{font-size:21px;}
    .rightcol{padding:0 16px 24px;flex-direction:column;}
    .panel-card{min-width:0;}
    .number-item{flex-wrap:wrap;}
    .number-region{margin-left:auto;}
    .lang-switch-top{position:absolute !important;top:64px !important;right:12px !important;}
  }
</style>
</head>
<body>
<div class="bg-particles">
  <span style="left:6%;width:5px;height:5px;animation-duration:16s;animation-delay:0s;"></span>
  <span style="left:16%;width:3px;height:3px;animation-duration:12s;animation-delay:2s;"></span>
  <span style="left:28%;width:4px;height:4px;animation-duration:19s;animation-delay:4s;"></span>
  <span style="left:42%;width:3px;height:3px;animation-duration:14s;animation-delay:1s;"></span>
  <span style="left:58%;width:5px;height:5px;animation-duration:17s;animation-delay:6s;"></span>
  <span style="left:71%;width:3px;height:3px;animation-duration:13s;animation-delay:3s;"></span>
  <span style="left:83%;width:4px;height:4px;animation-duration:18s;animation-delay:5s;"></span>
  <span style="left:92%;width:3px;height:3px;animation-duration:15s;animation-delay:7s;"></span>
</div>

<div class="sidebar">
  <div class="logo"><span class="logo-dot"></span>EchoLine</div>
  <a class="nav-item{{ ' active' if active_page == 'dashboard' else '' }}" href="/dashboard">
    <i data-lucide="layout-dashboard" class="nav-icon"></i>
    <span class="label" data-i18n="nav_dashboard">Dashboard</span>
  </a>
  <a class="nav-item{{ ' active' if active_page == 'number' else '' }}" href="/numer-telefonu">
    <i data-lucide="phone" class="nav-icon"></i>
    <span class="label" data-i18n="nav_number">Numer telefonu</span>
  </a>
  <a class="nav-item{{ ' active' if active_page == 'voice' else '' }}" href="/moj-glos">
    <i data-lucide="mic" class="nav-icon"></i>
    <span class="label" data-i18n="nav_voice">Mój głos</span>
  </a>
  <a class="nav-item{{ ' active' if active_page == 'calls' else '' }}" href="/rozmowy">
    <i data-lucide="message-circle" class="nav-icon"></i>
    <span class="label" data-i18n="nav_calls">Rozmowy</span>
  </a>
  <a class="nav-item{{ ' active' if active_page == 'pricing' else '' }}" href="/cennik">
    <i data-lucide="credit-card" class="nav-icon"></i>
    <span class="label" data-i18n="nav_pricing">Cennik</span>
  </a>
  <div class="nav-section-label" data-i18n="nav_account">Konto</div>
  <a class="nav-item{{ ' active' if active_page == 'settings' else '' }}" href="/ustawienia">
    <i data-lucide="settings" class="nav-icon"></i>
    <span class="label" data-i18n="nav_settings">Ustawienia</span>
  </a>

  <div class="sidebar-widget">
    <div class="sw-title" id="swTitle">Twój asystent AI<br>24/7 gotowy do rozmów</div>
    <div class="sw-orbit"><div class="sw-ring"></div><div class="sw-sphere"></div></div>
    <a class="sw-link" href="/dashboard" data-i18n="widget_link">Zobacz statystyki →</a>
  </div>
</div>

<div class="main">
  <div class="lang-switch-top" style="display:flex;gap:4px;position:fixed;top:16px;right:24px;z-index:999;background:#fff;padding:5px;border-radius:100px;box-shadow:0 4px 16px -4px rgba(0,0,0,0.15);border:1px solid #f0f0f0;">
    <button id="langPl" onclick="setLang('pl')" class="langbtn" style="padding:4px 10px;border-radius:100px;font-size:11px;font-weight:700;cursor:pointer;">PL</button>
    <button id="langEn" onclick="setLang('en')" class="langbtn" style="padding:4px 10px;border-radius:100px;font-size:11px;font-weight:700;cursor:pointer;">EN</button>
  </div>
  <div class="center rise">
    <div class="center-head">
      <h1 data-i18n="page_title">Skonfiguruj numer telefonu</h1>
      <p data-i18n="page_sub">Wybierz kraj i uzyskaj własny numer dla swojego asystenta.</p>
    </div>

    <div class="step-label"><i data-lucide="globe"></i><span data-i18n="step_country">1. Wybierz kraj</span></div>
    <div class="country-row" id="countryRow">
      <div class="country-card selected" data-country="PL" data-name="Polska" onclick="selectCountry(this)">
        <div class="country-flag">🇵🇱</div>
        <div><div class="country-name" data-i18n="country_pl">Polska</div><div class="country-code">+48</div></div>
        <div class="selected-check"><svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg></div>
      </div>
      <div class="country-card" data-country="US" data-name="USA" onclick="selectCountry(this)">
        <div class="country-flag">🇺🇸</div>
        <div><div class="country-name">USA</div><div class="country-code">+1</div></div>
        <div class="selected-check"><svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg></div>
      </div>
      <div class="country-card" data-country="DE" data-name="Niemcy" onclick="selectCountry(this)">
        <div class="country-flag">🇩🇪</div>
        <div><div class="country-name" data-i18n="country_de">Niemcy</div><div class="country-code">+49</div></div>
        <div class="selected-check"><svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg></div>
      </div>
      <div class="country-card" data-country="GB" data-name="Wielka Brytania" onclick="selectCountry(this)">
        <div class="country-flag">🇬🇧</div>
        <div><div class="country-name" data-i18n="country_gb">Wielka Brytania</div><div class="country-code">+44</div></div>
        <div class="selected-check"><svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg></div>
      </div>
    </div>

    <div class="step-label"><i data-lucide="search"></i><span data-i18n="step_search">2. Znajdź dostępne numery</span></div>
    <div id="searchError"></div>
    <button class="search-btn" id="searchBtn" onclick="searchNumbers()">
      <i data-lucide="sparkles"></i><span data-i18n="search_btn">Wyszukaj dostępne numery</span>
    </button>

    <div id="searchLoading"><div class="spinner"></div><span data-i18n="searching_text">Szukamy dostępnych numerów...</span></div>

    <div id="resultsSection">
      <div class="step-label"><i data-lucide="phone-call"></i><span data-i18n="step_choose">3. Wybierz swój numer</span></div>
      <div id="numbersList"></div>

      <div id="buyError"></div>
      <button class="activate-btn" id="activateBtn" disabled onclick="activateNumber()">
        <span data-i18n="activate_btn">Aktywuj ten numer</span> <i data-lucide="arrow-right"></i>
      </button>
    </div>

    <div class="privacy-bar">
      <i data-lucide="lock"></i>
      <div>
        <b data-i18n="privacy_title">Twój numer jest w pełni zarządzany i zabezpieczony</b>
        <span data-i18n="privacy_sub">Szyfrowanie end-to-end · Ochrona prywatności · Zgodność z RODO</span>
      </div>
    </div>
  </div>

  <div class="rightcol rise">
    <div class="panel-card">
      <h4><i data-lucide="lightbulb"></i><span data-i18n="tips_title">Wskazówki</span></h4>
      <div class="tip"><svg viewBox="0 0 24 24" fill="none" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M9 12l2 2 4-4"/></svg><span data-i18n="tip_1">Wybierz kraj Twoich klientów</span></div>
      <div class="tip"><svg viewBox="0 0 24 24" fill="none" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M9 12l2 2 4-4"/></svg><span data-i18n="tip_2">Numer możesz zmienić później</span></div>
      <div class="tip"><svg viewBox="0 0 24 24" fill="none" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M9 12l2 2 4-4"/></svg><span data-i18n="tip_3">Aktywacja zajmuje kilka sekund</span></div>
    </div>

    <div class="panel-card">
      <h4><i data-lucide="list-checks"></i><span data-i18n="progress_title">Postęp konfiguracji</span></h4>
      <div class="step-row active" id="step1">
        <div class="step-num">1</div>
        <div><div class="step-title" data-i18n="pstep1_title">Wybierz kraj</div><div class="step-sub" data-i18n="pstep1_sub">Wybierz kraj dla swojego numeru</div></div>
      </div>
      <div class="step-row" id="step2">
        <div class="step-num">2</div>
        <div><div class="step-title" data-i18n="pstep2_title">Wyszukaj numery</div><div class="step-sub" data-i18n="pstep2_sub">Znajdź i wybierz dostępny numer</div></div>
      </div>
      <div class="step-row" id="step3">
        <div class="step-num">3</div>
        <div><div class="step-title" data-i18n="pstep3_title">Aktywuj numer</div><div class="step-sub" data-i18n="pstep3_sub">Aktywuj numer dla swojego bota</div></div>
      </div>
    </div>

    <div class="panel-card">
      <h4><i data-lucide="phone"></i><span data-i18n="your_number_title">Twój numer</span></h4>
      <div id="myNumberBox">
        <div class="empty-number">
          <div class="empty-icon"><svg viewBox="0 0 24 24"><path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6 19.8 19.8 0 0 1-3.1-8.6A2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .3 2 .6 3a2 2 0 0 1-.5 2.1L8 10a16 16 0 0 0 6 6l1.2-1.2a2 2 0 0 1 2.1-.5c1 .3 2 .5 3 .6a2 2 0 0 1 1.7 2z"/></svg></div>
          <b data-i18n="no_number_title">Nie masz jeszcze numeru</b>
          <p data-i18n="no_number_desc">Skonfiguruj swój pierwszy numer, aby Twój asystent mógł odbierać połączenia.</p>
        </div>
      </div>
    </div>
  </div>
</div>

<script>
  const NUMBER_I18N = {
    pl: {
      nav_dashboard: 'Dashboard', nav_number: 'Numer telefonu', nav_voice: 'Mój głos',
      nav_calls: 'Rozmowy', nav_pricing: 'Cennik', nav_account: 'Konto', nav_settings: 'Ustawienia',
      widget_title_html: 'Twój asystent AI<br>24/7 gotowy do rozmów',
      widget_link: 'Zobacz statystyki →',
      page_title: 'Skonfiguruj numer telefonu',
      page_sub: 'Wybierz kraj i uzyskaj własny numer dla swojego asystenta.',
      step_country: '1. Wybierz kraj',
      country_pl: 'Polska', country_de: 'Niemcy', country_gb: 'Wielka Brytania',
      step_search: '2. Znajdź dostępne numery',
      search_btn: 'Wyszukaj dostępne numery',
      searching_text: 'Szukamy dostępnych numerów...',
      step_choose: '3. Wybierz swój numer',
      activate_btn: 'Aktywuj ten numer',
      privacy_title: 'Twój numer jest w pełni zarządzany i zabezpieczony',
      privacy_sub: 'Szyfrowanie end-to-end - Ochrona prywatności - Zgodność z RODO',
      tips_title: 'Wskazówki',
      tip_1: 'Wybierz kraj Twoich klientów',
      tip_2: 'Numer możesz zmienić później',
      tip_3: 'Aktywacja zajmuje kilka sekund',
      progress_title: 'Postęp konfiguracji',
      pstep1_title: 'Wybierz kraj', pstep1_sub: 'Wybierz kraj dla swojego numeru',
      pstep2_title: 'Wyszukaj numery', pstep2_sub: 'Znajdź i wybierz dostępny numer',
      pstep3_title: 'Aktywuj numer', pstep3_sub: 'Aktywuj numer dla swojego bota',
      your_number_title: 'Twój numer',
      no_number_title: 'Nie masz jeszcze numeru',
      no_number_desc: 'Skonfiguruj swój pierwszy numer, aby Twój asystent mógł odbierać połączenia.',
      active_tag: 'Aktywny',
      activated_prefix: 'Aktywowano: ',
      just_now: 'przed chwila',
      searching_btn: 'Aktywowanie...',
      err_search_failed: 'Nie udalo sie wyszukac numerow.',
      err_no_numbers: 'Brak dostepnych numerow dla tego kraju. Sprobuj inny kraj.',
      err_connection: 'Blad polaczenia: ',
    },
    en: {
      nav_dashboard: 'Dashboard', nav_number: 'Phone number', nav_voice: 'My voice',
      nav_calls: 'Calls', nav_pricing: 'Pricing', nav_account: 'Account', nav_settings: 'Settings',
      widget_title_html: 'Your AI assistant<br>ready 24/7',
      widget_link: 'View statistics →',
      page_title: 'Set up phone number',
      page_sub: 'Choose a country and get your own number for your assistant.',
      step_country: '1. Choose a country',
      country_pl: 'Poland', country_de: 'Germany', country_gb: 'United Kingdom',
      step_search: '2. Find available numbers',
      search_btn: 'Search available numbers',
      searching_text: 'Searching for available numbers...',
      step_choose: '3. Choose your number',
      activate_btn: 'Activate this number',
      privacy_title: 'Your number is fully managed and secured',
      privacy_sub: 'End-to-end encryption - Privacy protection - GDPR compliant',
      tips_title: 'Tips',
      tip_1: 'Choose the country of your customers',
      tip_2: 'You can change the number later',
      tip_3: 'Activation takes a few seconds',
      progress_title: 'Setup progress',
      pstep1_title: 'Choose country', pstep1_sub: 'Choose a country for your number',
      pstep2_title: 'Search numbers', pstep2_sub: 'Find and choose an available number',
      pstep3_title: 'Activate number', pstep3_sub: 'Activate the number for your bot',
      your_number_title: 'Your number',
      no_number_title: 'You do not have a number yet',
      no_number_desc: 'Set up your first number so your assistant can answer calls.',
      active_tag: 'Active',
      activated_prefix: 'Activated: ',
      just_now: 'just now',
      searching_btn: 'Activating...',
      err_search_failed: 'Failed to search for numbers.',
      err_no_numbers: 'No numbers available for this country. Try another country.',
      err_connection: 'Connection error: ',
    }
  };

  let currentLang = (navigator.language || 'pl').slice(0, 2).toLowerCase() === 'pl' ? 'pl' : 'en';

  function nt(key){ return NUMBER_I18N[currentLang][key] || key; }

  function applyNumberLang(){
    document.querySelectorAll('[data-i18n]').forEach(function(el){
      el.textContent = nt(el.getAttribute('data-i18n'));
    });
    document.getElementById('swTitle').innerHTML = nt('widget_title_html');
    if (typeof window.refreshNumberBox === 'function') window.refreshNumberBox();
  }

  window.setLang = function(lang){
    currentLang = lang;
    document.getElementById('langPl').classList.toggle('active', lang === 'pl');
    document.getElementById('langEn').classList.toggle('active', lang === 'en');
    applyNumberLang();
  };

  setLang(currentLang);
</script>

<script type="module">
  import { initializeApp } from "https://www.gstatic.com/firebasejs/10.13.0/firebase-app.js";
  import { getAuth, onAuthStateChanged } from "https://www.gstatic.com/firebasejs/10.13.0/firebase-auth.js";
  import { getFirestore, doc, getDoc, updateDoc } from "https://www.gstatic.com/firebasejs/10.13.0/firebase-firestore.js";

  const firebaseConfig = {{ firebase_config | tojson }};
  const app = initializeApp(firebaseConfig);
  const auth = getAuth(app);
  const db = getFirestore(app);

  let currentUid = null;
  let selectedCountry = "PL";
  let selectedNumber = null;
  let lastPhoneData = null;

  onAuthStateChanged(auth, async (user) => {
    if (!user) return;
    currentUid = user.uid;
    const snap = await getDoc(doc(db, "users", user.uid));
    const data = snap.exists() ? snap.data() : {};
    if (data.phoneNumber) {
      lastPhoneData = data;
      renderMyNumber(data.phoneNumber, data.phoneNumberDate || "");
    }
  });

  window.refreshNumberBox = function(){
    if (lastPhoneData) renderMyNumber(lastPhoneData.phoneNumber, lastPhoneData.phoneNumberDate || "");
  };

  function renderMyNumber(phoneNumber, date){
    document.getElementById("myNumberBox").innerHTML = `
      <span class="active-number-tag">${nt("active_tag")}</span>
      <div class="active-number-phone">${phoneNumber}</div>
      <div class="active-number-date">${nt("activated_prefix")}${date || nt("just_now")}</div>
    `;
    setStep(3);
  }

  window.selectCountry = function(el){
    document.querySelectorAll(".country-card").forEach(c => c.classList.remove("selected"));
    el.classList.add("selected");
    selectedCountry = el.dataset.country;
    document.getElementById("resultsSection").style.display = "none";
    setStep(1);
  };

  function setStep(stage){
    for (let i = 1; i <= 3; i++) {
      const el = document.getElementById("step" + i);
      el.classList.remove("active", "done");
      if (i < stage) el.classList.add("done");
      if (i === stage) el.classList.add("active");
    }
  }

  window.searchNumbers = async function(){
    const btn = document.getElementById("searchBtn");
    const loading = document.getElementById("searchLoading");
    const errorBox = document.getElementById("searchError");
    const resultsSection = document.getElementById("resultsSection");
    errorBox.style.display = "none";
    resultsSection.style.display = "none";
    btn.disabled = true;
    loading.style.display = "block";
    setStep(2);

    try {
      const resp = await fetch("/search-numbers?country=" + selectedCountry);
      const result = await resp.json();
      loading.style.display = "none";
      btn.disabled = false;

      if (!resp.ok || result.error) {
        errorBox.textContent = result.error || nt("err_search_failed");
        errorBox.style.display = "block";
        return;
      }

      const numbers = result.numbers || [];
      if (numbers.length === 0) {
        errorBox.textContent = nt("err_no_numbers");
        errorBox.style.display = "block";
        return;
      }

      const list = document.getElementById("numbersList");
      list.innerHTML = numbers.map((n, i) => `
        <div class="number-item${i === 0 ? ' selected' : ''}" data-number="${n.phone_number}" onclick="selectNumber(this)">
          <div class="radio-dot"></div>
          <div style="flex:1;">
            <div class="number-phone">${n.friendly_name || n.phone_number}</div>
          </div>
          <div class="number-region">${n.locality || n.region || ""}</div>
        </div>
      `).join("");

      selectedNumber = numbers[0].phone_number;
      document.getElementById("activateBtn").disabled = false;
      resultsSection.style.display = "block";
    } catch (e) {
      loading.style.display = "none";
      btn.disabled = false;
      errorBox.textContent = nt("err_connection") + e.message;
      errorBox.style.display = "block";
    }
  };

  window.selectNumber = function(el){
    document.querySelectorAll(".number-item").forEach(n => n.classList.remove("selected"));
    el.classList.add("selected");
    selectedNumber = el.dataset.number;
  };

  window.activateNumber = async function(){
    const btn = document.getElementById("activateBtn");
    const errorBox = document.getElementById("buyError");
    errorBox.style.display = "none";
    btn.disabled = true;
    btn.textContent = nt("searching_btn");

    try {
      const resp = await fetch("/buy-number", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone_number: selectedNumber })
      });
      const result = await resp.json();

      if (!resp.ok || result.error) {
        errorBox.textContent = result.error || "Nie udalo sie aktywowac numeru.";
        errorBox.style.display = "block";
        btn.disabled = false;
        btn.innerHTML = nt('activate_btn') + ' <i data-lucide="arrow-right"></i>';
        lucide.createIcons();
        return;
      }

      await updateDoc(doc(db, "users", currentUid), {
        phoneNumber: result.phone_number,
        phoneNumberDate: new Date().toLocaleDateString("pl-PL")
      });
      renderMyNumber(result.phone_number, new Date().toLocaleDateString("pl-PL"));
      btn.textContent = "Numer aktywowany ✓";
    } catch (e) {
      errorBox.textContent = "Blad polaczenia: " + e.message;
      errorBox.style.display = "block";
      btn.disabled = false;
      btn.innerHTML = nt('activate_btn') + ' <i data-lucide="arrow-right"></i>';
      lucide.createIcons();
    }
  };
</script>
<script src="https://unpkg.com/lucide@latest/dist/umd/lucide.js"></script>
<script>lucide.createIcons();</script>
</body>
</html>
"""

PRICING_PAGE = """
<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>EchoLine - Cennik</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
  *{box-sizing:border-box;margin:0;padding:0;}
  .bg-particles{position:fixed;inset:0;overflow:hidden;pointer-events:none;z-index:0;}
  .bg-particles span{position:absolute;bottom:-10px;border-radius:50%;background:#7c6aff;opacity:0;animation:floatDust linear infinite;}
  @keyframes floatDust{
    0%{transform:translateY(0) translateX(0);opacity:0;}
    10%{opacity:0.4;}
    90%{opacity:0.4;}
    100%{transform:translateY(-105vh) translateX(30px);opacity:0;}
  }
  .langbtn{border:1px solid #eee;background:#fff;color:#999;}
  .langbtn.active{background:#111;color:#fff;border-color:#111;}
  body{font-family:'Inter',sans-serif;background:#fff;color:#111;display:flex;min-height:100vh;}

  @keyframes riseIn{from{opacity:0;transform:translateY(10px);}to{opacity:1;transform:none;}}
  .rise{animation:riseIn .5s cubic-bezier(.16,1,.3,1) both;}

  .sidebar{width:230px;flex-shrink:0;border-right:1px solid #eee;padding:20px 12px;display:flex;flex-direction:column;}
  .logo{font-size:15px;font-weight:800;padding:8px 8px 20px;letter-spacing:-0.01em;display:flex;align-items:center;gap:9px;}
  .logo-dot{width:22px;height:22px;border-radius:50%;background:radial-gradient(circle at 30% 30%,#a9c9ff,#7c6aff 60%,#5a4bd4);flex-shrink:0;box-shadow:0 0 14px rgba(124,106,255,0.4);}
  .nav-item{display:flex;align-items:center;gap:10px;padding:9px 10px;border-radius:9px;font-size:13.5px;font-weight:500;color:#555;text-decoration:none;margin-bottom:2px;cursor:pointer;}
  .nav-item:hover{background:#f5f5f7;}
  .nav-item.active{background:linear-gradient(135deg,#7c6aff,#5dadff);color:#fff;box-shadow:0 6px 16px rgba(124,106,255,0.3);}
  .nav-icon{width:17px;height:17px;flex-shrink:0;stroke:#666;fill:none;stroke-width:1.8;}
  .nav-item.active .nav-icon{stroke:#fff;}
  .nav-section-label{font-size:10.5px;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;color:#bbb;padding:16px 10px 6px;}

  .sidebar-widget{margin-top:auto;background:linear-gradient(160deg,#f2f0ff,#eef6ff);border-radius:16px;padding:18px;text-align:left;}
  .sidebar-widget .sw-title{font-size:12.5px;font-weight:700;color:#5a4bd4;line-height:1.4;margin-bottom:14px;}
  .sw-orbit{width:76px;height:76px;margin:6px auto 14px;position:relative;}
  .sw-sphere{width:44px;height:44px;border-radius:50%;background:radial-gradient(circle at 30% 30%,#c9d9ff,#7c6aff 55%,#4f3fcf);position:absolute;top:16px;left:16px;box-shadow:0 0 22px rgba(124,106,255,0.5);}
  .sw-ring{position:absolute;inset:0;border:1.5px solid rgba(124,106,255,0.35);border-radius:50%;transform:rotate(-20deg) scaleY(0.42);}
  .sw-link{display:flex;align-items:center;gap:6px;font-size:12px;font-weight:600;color:#5a4bd4;text-decoration:none;}

  @keyframes riseIn{from{opacity:0;transform:translateY(10px);}to{opacity:1;transform:none;}}
  .rise{animation:riseIn .5s cubic-bezier(.16,1,.3,1) both;}
  .rise2{animation:riseIn .5s .1s cubic-bezier(.16,1,.3,1) both;}
  .rise3{animation:riseIn .5s .2s cubic-bezier(.16,1,.3,1) both;}

  .main{flex:1;padding:40px 36px;max-width:1080px;position:relative;}
  .hero-glow{position:absolute;top:-40px;left:50%;transform:translateX(-50%);width:600px;height:280px;background:radial-gradient(ellipse,rgba(124,106,255,0.16),transparent 70%);pointer-events:none;z-index:0;}
  .center-head{text-align:center;margin-bottom:8px;position:relative;z-index:1;}
  .center-head h1{font-size:32px;font-weight:800;letter-spacing:-0.015em;margin-bottom:8px;background:linear-gradient(135deg,#111,#5a4bd4);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}
  .center-head p{font-size:14.5px;color:#888;}

  .toggle-wrap{display:flex;justify-content:center;margin:26px 0 36px;position:relative;z-index:1;}
  .toggle{display:flex;background:#f2f2f4;border-radius:100px;padding:4px;}
  .toggle button{padding:9px 20px;border-radius:100px;border:none;background:transparent;font-size:13.5px;font-weight:600;color:#888;cursor:pointer;transition:all .2s;}
  .toggle button.active{background:#fff;color:#111;box-shadow:0 2px 8px rgba(0,0,0,0.08);}
  .save-badge{font-size:10.5px;background:#e8f8f0;color:#1e9e63;padding:2px 8px;border-radius:100px;margin-left:6px;}

  .plans{display:grid;grid-template-columns:repeat(3,1fr);gap:20px;margin-bottom:40px;position:relative;z-index:1;}
  .plan-card{border:1.5px solid #eee;border-radius:20px;padding:28px 26px;position:relative;display:flex;flex-direction:column;transition:all .25s cubic-bezier(.16,1,.3,1);}
  .plan-card:hover{transform:translateY(-6px);box-shadow:0 24px 50px -24px rgba(0,0,0,0.18);border-color:#ddd;}
  .plan-card.featured{border-color:#7c6aff;box-shadow:0 20px 55px -20px rgba(124,106,255,0.4);background:linear-gradient(180deg,#fbfaff,#fff 40%);animation:featuredPulse 3.5s ease-in-out infinite;}
  @keyframes featuredPulse{0%,100%{box-shadow:0 20px 55px -20px rgba(124,106,255,0.4);}50%{box-shadow:0 20px 60px -18px rgba(124,106,255,0.55);}}
  .plan-card.featured:hover{transform:translateY(-8px) scale(1.015);}
  .plan-badge{position:absolute;top:-12px;left:50%;transform:translateX(-50%);background:linear-gradient(135deg,#7c6aff,#5dadff);color:#fff;font-size:10.5px;font-weight:800;letter-spacing:0.04em;padding:6px 16px;border-radius:100px;white-space:nowrap;box-shadow:0 6px 16px rgba(124,106,255,0.4);}
  .plan-name{font-size:15px;font-weight:700;color:#888;margin-bottom:10px;}
  .plan-price{font-size:38px;font-weight:800;letter-spacing:-0.01em;margin-bottom:4px;}
  .plan-price span{font-size:14px;color:#999;font-weight:500;}
  .plan-desc{font-size:12.5px;color:#999;margin-bottom:22px;min-height:32px;}
  .plan-features{list-style:none;display:flex;flex-direction:column;gap:11px;margin-bottom:26px;flex-grow:1;}
  .plan-features li{font-size:13.5px;color:#444;display:flex;gap:9px;align-items:flex-start;}
  .plan-features svg{width:15px;height:15px;stroke:#7c6aff;fill:none;stroke-width:2.2;flex-shrink:0;margin-top:1px;}
  .plan-btn{width:100%;padding:13px;border-radius:11px;font-weight:700;font-size:14px;cursor:pointer;text-align:center;transition:all .2s;}
  .plan-btn.outline{background:#fff;border:1.5px solid #ddd;color:#111;}
  .plan-btn.outline:hover{border-color:#7c6aff;color:#7c6aff;}
  .plan-btn.filled{background:linear-gradient(135deg,#7c6aff,#5dadff);border:none;color:#fff;box-shadow:0 10px 24px rgba(124,106,255,0.3);}
  .plan-btn.filled:hover{opacity:0.92;}

  .trust-bar{display:flex;justify-content:center;gap:26px;flex-wrap:wrap;padding:20px;background:#fafafa;border-radius:14px;margin-bottom:36px;}
  .trust-bar span{font-size:12.5px;color:#888;display:flex;align-items:center;gap:6px;}
  .trust-bar svg{width:14px;height:14px;stroke:#7c6aff;fill:none;stroke-width:2;}

  .faq{max-width:640px;margin:0 auto;}
  .faq h3{font-size:17px;font-weight:700;margin-bottom:16px;text-align:center;}
  .faq-item{border-bottom:1px solid #eee;padding:14px 0;}
  .faq-item summary{font-size:13.5px;font-weight:600;cursor:pointer;list-style:none;}
  .faq-item summary::-webkit-details-marker{display:none;}
  .faq-item p{font-size:13px;color:#888;margin-top:8px;line-height:1.5;}

  #actionMsg{display:none;text-align:center;font-size:13px;padding:10px 16px;border-radius:10px;margin-bottom:20px;background:#f5f3ff;color:#5a4bd4;}

  @media (max-width: 1100px) {
    .main{padding:32px 28px;}
  }
  @media (max-width: 900px) {
    .plans{grid-template-columns:1fr;}
    .plan-card.featured{order:-1;}
  }
  @media (max-width: 760px) {
    body{flex-direction:column;}
    .sidebar{width:100%;border-right:none;border-bottom:1px solid #eee;flex-direction:row;align-items:center;padding:12px 16px;overflow-x:auto;white-space:nowrap;}
    .sidebar-widget,.nav-section-label{display:none;}
    .logo{padding:0 14px 0 0;}
    .nav-item span.label{display:none;}
    .main{padding:24px 16px;}
    .center-head h1{font-size:23px;}
    .trust-bar{gap:12px;}
  }
</style>
</head>
<body>
<div class="bg-particles">
  <span style="left:6%;width:5px;height:5px;animation-duration:16s;animation-delay:0s;"></span>
  <span style="left:16%;width:3px;height:3px;animation-duration:12s;animation-delay:2s;"></span>
  <span style="left:28%;width:4px;height:4px;animation-duration:19s;animation-delay:4s;"></span>
  <span style="left:42%;width:3px;height:3px;animation-duration:14s;animation-delay:1s;"></span>
  <span style="left:58%;width:5px;height:5px;animation-duration:17s;animation-delay:6s;"></span>
  <span style="left:71%;width:3px;height:3px;animation-duration:13s;animation-delay:3s;"></span>
  <span style="left:83%;width:4px;height:4px;animation-duration:18s;animation-delay:5s;"></span>
  <span style="left:92%;width:3px;height:3px;animation-duration:15s;animation-delay:7s;"></span>
</div>

<div class="sidebar">
  <div class="logo"><span class="logo-dot"></span>EchoLine</div>
  <a class="nav-item{{ ' active' if active_page == 'dashboard' else '' }}" href="/dashboard">
    <i data-lucide="layout-dashboard" class="nav-icon"></i>
    <span class="label" data-i18n="nav_dashboard">Dashboard</span>
  </a>
  <a class="nav-item{{ ' active' if active_page == 'number' else '' }}" href="/numer-telefonu">
    <i data-lucide="phone" class="nav-icon"></i>
    <span class="label" data-i18n="nav_number">Numer telefonu</span>
  </a>
  <a class="nav-item{{ ' active' if active_page == 'voice' else '' }}" href="/moj-glos">
    <i data-lucide="mic" class="nav-icon"></i>
    <span class="label" data-i18n="nav_voice">Mój głos</span>
  </a>
  <a class="nav-item{{ ' active' if active_page == 'calls' else '' }}" href="/rozmowy">
    <i data-lucide="message-circle" class="nav-icon"></i>
    <span class="label" data-i18n="nav_calls">Rozmowy</span>
  </a>
  <a class="nav-item{{ ' active' if active_page == 'pricing' else '' }}" href="/cennik">
    <i data-lucide="credit-card" class="nav-icon"></i>
    <span class="label" data-i18n="nav_pricing">Cennik</span>
  </a>
  <div class="nav-section-label" data-i18n="nav_account">Konto</div>
  <a class="nav-item{{ ' active' if active_page == 'settings' else '' }}" href="/ustawienia">
    <i data-lucide="settings" class="nav-icon"></i>
    <span class="label" data-i18n="nav_settings">Ustawienia</span>
  </a>

  <div class="sidebar-widget">
    <div class="sw-title" id="swTitle">Twój asystent AI<br>24/7 gotowy do rozmów</div>
    <div class="sw-orbit"><div class="sw-ring"></div><div class="sw-sphere"></div></div>
    <a class="sw-link" href="/dashboard" data-i18n="widget_link">Zobacz statystyki →</a>
  </div>
</div>

<div class="main rise">
  <div class="hero-glow"></div>
  <div class="lang-switch-top" style="display:flex;justify-content:flex-end;gap:4px;margin-bottom:12px;position:relative;z-index:1;">
    <button id="langPl" onclick="setLang('pl')" class="langbtn" style="padding:4px 10px;border-radius:100px;font-size:11px;font-weight:700;cursor:pointer;">PL</button>
    <button id="langEn" onclick="setLang('en')" class="langbtn" style="padding:4px 10px;border-radius:100px;font-size:11px;font-weight:700;cursor:pointer;">EN</button>
  </div>
  <div class="center-head">
    <h1 data-i18n="page_title">Wybierz plan dla siebie</h1>
    <p data-i18n="page_sub">Zacznij mały, płać za rozmowy. Bez ukrytych opłat.</p>
  </div>

  <div class="toggle-wrap rise2">
    <div class="toggle">
      <button class="active" id="toggle-monthly" onclick="setBilling('monthly')" data-i18n="toggle_monthly">Miesięcznie</button>
      <button id="toggle-yearly" onclick="setBilling('yearly')"><span data-i18n="toggle_yearly">Rocznie</span> <span class="save-badge">-20%</span></button>
    </div>
  </div>

  <div id="actionMsg"></div>

  <div class="plans rise3">
    <div class="plan-card">
      <div class="plan-name">Start</div>
      <div class="plan-price"><span class="price-val" data-monthly="149" data-yearly="119">149 zł</span><span>/mies.</span></div>
      <div class="plan-desc" data-i18n="plan_start_desc">Dla jednoosobowych działalności testujących pierwszy raz</div>
      <ul class="plan-features">
        <li><svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg><span data-i18n="feat_start_1">1 numer telefonu</span></li>
        <li><svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg><span data-i18n="feat_start_2">100 minut rozmów miesięcznie</span></li>
        <li><svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg><span data-i18n="feat_start_3">1 sklonowany głos</span></li>
        <li><svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg><span data-i18n="feat_start_4">Podstawowy profil asystenta</span></li>
        <li><svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg><span data-i18n="feat_start_5">5 zleceń Zadzwoń za mnie / mies.</span></li>
      </ul>
      <button class="plan-btn outline" onclick="choosePlan('start')" data-i18n="btn_start">Wybierz Start</button>
    </div>

    <div class="plan-card featured">
      <div class="plan-badge" data-i18n="badge_popular">NAJPOPULARNIEJSZY</div>
      <div class="plan-name">Pro</div>
      <div class="plan-price"><span class="price-val" data-monthly="399" data-yearly="319">399 zł</span><span>/mies.</span></div>
      <div class="plan-desc" data-i18n="plan_pro_desc">Dla firm gotowych przekazać telefon botowi na stałe</div>
      <ul class="plan-features">
        <li><svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg><span data-i18n="feat_pro_1">1 numer telefonu</span></li>
        <li><svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg><span data-i18n="feat_pro_2">400 minut rozmów miesięcznie</span></li>
        <li><svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg><span data-i18n="feat_pro_3">Nielimitowane zmiany głosu</span></li>
        <li><svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg><span data-i18n="feat_pro_4">Sufler w czasie rzeczywistym</span></li>
        <li><svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg><span data-i18n="feat_pro_5">30 zleceń Zadzwoń za mnie / mies.</span></li>
        <li><svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg><span data-i18n="feat_pro_6">Priorytetowe wsparcie</span></li>
      </ul>
      <button class="plan-btn filled" onclick="choosePlan('pro')" data-i18n="btn_pro">Wybierz Pro</button>
    </div>

    <div class="plan-card">
      <div class="plan-name">Firma</div>
      <div class="plan-price"><span class="price-val" data-monthly="899" data-yearly="719">899 zł</span><span>/mies.</span></div>
      <div class="plan-desc" data-i18n="plan_firma_desc">Dla zespołów z wieloma liniami i większym wolumenem</div>
      <ul class="plan-features">
        <li><svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg><span data-i18n="feat_firma_1">Do 5 numerów telefonu</span></li>
        <li><svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg><span data-i18n="feat_firma_2">1000+ minut rozmów</span></li>
        <li><svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg><span data-i18n="feat_firma_3">Wszystko z planu Pro</span></li>
        <li><svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg><span data-i18n="feat_firma_4">Eksport historii rozmów</span></li>
        <li><svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg><span data-i18n="feat_firma_5">Opiekun wdrożenia</span></li>
      </ul>
      <button class="plan-btn outline" onclick="choosePlan('firma')" data-i18n="btn_firma">Wybierz Firmę</button>
    </div>
  </div>

  <div class="trust-bar">
    <span><svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg><span data-i18n="trust_1">Bez zobowiązań</span></span>
    <span><svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg><span data-i18n="trust_2">Anuluj w każdej chwili</span></span>
    <span><svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg><span data-i18n="trust_3">Płatność przez Stripe</span></span>
  </div>

  <div class="faq">
    <h3 data-i18n="faq_title">Najczęstsze pytania</h3>
    <details class="faq-item">
      <summary data-i18n="faq_q1">Co się stanie, jak przekroczę limit minut?</summary>
      <p data-i18n="faq_a1">Dostaniesz powiadomienie zanim to nastąpi. Możesz dokupić dodatkowe minuty albo przejść na wyższy plan w dowolnym momencie.</p>
    </details>
    <details class="faq-item">
      <summary data-i18n="faq_q2">Czy mogę zmienić plan później?</summary>
      <p data-i18n="faq_a2">Tak, w dowolnym momencie możesz przejść na wyższy lub niższy plan z panelu ustawień.</p>
    </details>
    <details class="faq-item">
      <summary data-i18n="faq_q3">Czy muszę mieć numer telefonu przed zakupem planu?</summary>
      <p data-i18n="faq_a3">Nie, najpierw wybierasz plan, a numer konfigurujesz od razu potem w zakładce Numer telefonu.</p>
    </details>
  </div>
</div>

<script>
  const PRICE_I18N = {
    pl: {
      nav_dashboard: 'Dashboard',
      nav_number: 'Numer telefonu',
      nav_voice: 'Mój głos',
      nav_calls: 'Rozmowy',
      nav_pricing: 'Cennik',
      nav_account: 'Konto',
      nav_settings: 'Ustawienia',
      widget_title_html: 'Twój asystent AI<br>24/7 gotowy do rozmów',
      widget_link: 'Zobacz statystyki →',
      page_title: 'Wybierz plan dla siebie',
      page_sub: 'Zacznij mały, płać za rozmowy. Bez ukrytych opłat.',
      toggle_monthly: 'Miesięcznie',
      toggle_yearly: 'Rocznie',
      plan_start_desc: 'Dla jednoosobowych działalności testujących pierwszy raz',
      feat_start_1: '1 numer telefonu',
      feat_start_2: '100 minut rozmów miesięcznie',
      feat_start_3: '1 sklonowany głos',
      feat_start_4: 'Podstawowy profil asystenta',
      feat_start_5: '5 zleceń Zadzwoń za mnie / mies.',
      btn_start: 'Wybierz Start',
      badge_popular: 'NAJPOPULARNIEJSZY',
      plan_pro_desc: 'Dla firm gotowych przekazać telefon botowi na stałe',
      feat_pro_1: '1 numer telefonu',
      feat_pro_2: '400 minut rozmów miesięcznie',
      feat_pro_3: 'Nielimitowane zmiany głosu',
      feat_pro_4: 'Sufler w czasie rzeczywistym',
      feat_pro_5: '30 zleceń Zadzwoń za mnie / mies.',
      feat_pro_6: 'Priorytetowe wsparcie',
      btn_pro: 'Wybierz Pro',
      plan_firma_desc: 'Dla zespołów z wieloma liniami i większym wolumenem',
      feat_firma_1: 'Do 5 numerów telefonu',
      feat_firma_2: '1000+ minut rozmów',
      feat_firma_3: 'Wszystko z planu Pro',
      feat_firma_4: 'Eksport historii rozmów',
      feat_firma_5: 'Opiekun wdrożenia',
      btn_firma: 'Wybierz Firmę',
      trust_1: 'Bez zobowiązań',
      trust_2: 'Anuluj w każdej chwili',
      trust_3: 'Płatność przez Stripe',
      faq_title: 'Najczęstsze pytania',
      faq_q1: 'Co się stanie, jak przekroczę limit minut?',
      faq_a1: 'Dostaniesz powiadomienie zanim to nastąpi. Możesz dokupić dodatkowe minuty albo przejść na wyższy plan w dowolnym momencie.',
      faq_q2: 'Czy mogę zmienić plan później?',
      faq_a2: 'Tak, w dowolnym momencie możesz przejść na wyższy lub niższy plan z panelu ustawień.',
      faq_q3: 'Czy muszę mieć numer telefonu przed zakupem planu?',
      faq_a3: 'Nie, najpierw wybierasz plan, a numer konfigurujesz od razu potem w zakładce Numer telefonu.',
      msg_contact: 'Ten plan wymaga kontaktu, napisz do nas.',
      msg_must_login: 'Musisz być zalogowany, żeby wykupić plan.',
      msg_redirecting: 'Przekierowuję do bezpiecznej płatności Stripe...',
      msg_payment_received: 'Płatność przyjęta! Aktywujemy Twój plan (to zwykle zajmuje kilka sekund)...',
      msg_plan_prefix: 'Plan (',
      msg_plan_suffix: ') został aktywowany! Możesz teraz korzystać z EchoLine.',
      msg_cancelled: 'Płatność anulowana. Możesz spróbować ponownie w dowolnym momencie.',
    },
    en: {
      nav_dashboard: 'Dashboard',
      nav_number: 'Phone number',
      nav_voice: 'My voice',
      nav_calls: 'Calls',
      nav_pricing: 'Pricing',
      nav_account: 'Account',
      nav_settings: 'Settings',
      widget_title_html: 'Your AI assistant<br>ready 24/7',
      widget_link: 'View statistics →',
      page_title: 'Choose your plan',
      page_sub: 'Start small, pay for calls. No hidden fees.',
      toggle_monthly: 'Monthly',
      toggle_yearly: 'Yearly',
      plan_start_desc: 'For solo businesses trying it out for the first time',
      feat_start_1: '1 phone number',
      feat_start_2: '100 call minutes per month',
      feat_start_3: '1 cloned voice',
      feat_start_4: 'Basic assistant profile',
      feat_start_5: '5 Call for me requests / month',
      btn_start: 'Choose Start',
      badge_popular: 'MOST POPULAR',
      plan_pro_desc: 'For businesses ready to hand off the phone to the bot',
      feat_pro_1: '1 phone number',
      feat_pro_2: '400 call minutes per month',
      feat_pro_3: 'Unlimited voice changes',
      feat_pro_4: 'Real-time prompter',
      feat_pro_5: '30 Call for me requests / month',
      feat_pro_6: 'Priority support',
      btn_pro: 'Choose Pro',
      plan_firma_desc: 'For teams with multiple lines and higher volume',
      feat_firma_1: 'Up to 5 phone numbers',
      feat_firma_2: '1000+ call minutes',
      feat_firma_3: 'Everything in Pro',
      feat_firma_4: 'Call history export',
      feat_firma_5: 'Onboarding support',
      btn_firma: 'Choose Business',
      trust_1: 'No commitment',
      trust_2: 'Cancel anytime',
      trust_3: 'Payment via Stripe',
      faq_title: 'Frequently asked questions',
      faq_q1: 'What happens if I exceed my minute limit?',
      faq_a1: 'You will get a notification before that happens. You can buy extra minutes or upgrade your plan anytime.',
      faq_q2: 'Can I change my plan later?',
      faq_a2: 'Yes, you can upgrade or downgrade your plan anytime from the settings panel.',
      faq_q3: 'Do I need a phone number before buying a plan?',
      faq_a3: 'No, you choose a plan first, then set up your number right after in the Phone number tab.',
      msg_contact: 'This plan requires contacting us, get in touch.',
      msg_must_login: 'You must be logged in to purchase a plan.',
      msg_redirecting: 'Redirecting to secure Stripe payment...',
      msg_payment_received: 'Payment received! Activating your plan (usually takes a few seconds)...',
      msg_plan_prefix: 'Plan (',
      msg_plan_suffix: ') has been activated! You can now use EchoLine.',
      msg_cancelled: 'Payment cancelled. You can try again anytime.',
    }
  };

  let currentLang = (navigator.language || 'pl').slice(0, 2).toLowerCase() === 'pl' ? 'pl' : 'en';

  function pt(key){ return PRICE_I18N[currentLang][key] || key; }

  function applyPriceLang(){
    document.querySelectorAll('[data-i18n]').forEach(function(el){
      el.textContent = pt(el.getAttribute('data-i18n'));
    });
    document.getElementById('swTitle').innerHTML = pt('widget_title_html');
  }

  window.setLang = function(lang){
    currentLang = lang;
    document.getElementById('langPl').classList.toggle('active', lang === 'pl');
    document.getElementById('langEn').classList.toggle('active', lang === 'en');
    applyPriceLang();
  };

  setLang(currentLang);
</script>

<script type="module">
  import { initializeApp } from "https://www.gstatic.com/firebasejs/10.13.0/firebase-app.js";
  import { getAuth, onAuthStateChanged } from "https://www.gstatic.com/firebasejs/10.13.0/firebase-auth.js";
  import { getFirestore, doc, onSnapshot } from "https://www.gstatic.com/firebasejs/10.13.0/firebase-firestore.js";

  const firebaseConfig = {{ firebase_config | tojson }};
  const app = initializeApp(firebaseConfig);
  const auth = getAuth(app);
  const db = getFirestore(app);

  let billing = 'monthly';
  let currentUid = null;

  const PAYMENT_LINKS = {
    start: 'https://buy.stripe.com/6oU8wO6n48FdgTp9VLcV204',
    pro: 'https://buy.stripe.com/fZu6oG7r8cVtdHd3xncV205',
    firma: 'https://buy.stripe.com/8x28wOcLsbRp6eLfg5cV203'
  };

  onAuthStateChanged(auth, (user) => {
    if (user) currentUid = user.uid;
  });

  window.setBilling = function(mode){
    billing = mode;
    document.getElementById('toggle-monthly').classList.toggle('active', mode === 'monthly');
    document.getElementById('toggle-yearly').classList.toggle('active', mode === 'yearly');
    document.querySelectorAll('.price-val').forEach(el => {
      const val = mode === 'monthly' ? el.dataset.monthly : el.dataset.yearly;
      el.textContent = val + ' zł';
    });
  };

  window.choosePlan = function(plan){
    const link = PAYMENT_LINKS[plan];
    const msg = document.getElementById('actionMsg');
    if (!link) {
      msg.style.display = 'block';
      msg.textContent = pt('msg_contact');
      return;
    }
    if (!currentUid) {
      msg.style.display = 'block';
      msg.textContent = pt('msg_must_login');
      return;
    }
    msg.style.display = 'block';
    msg.textContent = pt('msg_redirecting');
    // Dolaczamy client_reference_id (Twoje UID) - dzieki temu Stripe przekaze
    // je z powrotem do naszego webhooka, ktory jako jedyny aktywuje plan po realnej platnosci.
    window.location.href = link + '?client_reference_id=' + encodeURIComponent(currentUid);
  };

  // Obsluga powrotu ze Stripe - NIE ustawiamy tu planu samodzielnie (to robilo
  // by mozliwe oszustwo przez wpisanie ?payment=success w adres recznie).
  // Zamiast tego czekamy az webhook (ktory faktycznie zweryfikowal platnosc)
  // zapisze subscriptionActive=true w bazie, i nasluchujemy na ta zmiane na zywo.
  const params = new URLSearchParams(window.location.search);
  if (params.get('payment') === 'success') {
    const msg = document.getElementById('actionMsg');
    msg.style.display = 'block';
    msg.textContent = pt('msg_payment_received');
    window.history.replaceState({}, document.title, '/cennik');

    onAuthStateChanged(auth, (user) => {
      if (!user) return;
      onSnapshot(doc(db, "users", user.uid), (snap) => {
        const data = snap.data() || {};
        if (data.subscriptionActive) {
          msg.style.background = '#e8f8f0';
          msg.style.color = '#1e9e63';
          msg.textContent = pt('msg_plan_prefix') + (data.plan || '') + pt('msg_plan_suffix');
        }
      });
    });
  } else if (params.get('payment') === 'cancel') {
    const msg = document.getElementById('actionMsg');
    msg.style.display = 'block';
    msg.textContent = pt('msg_cancelled');
  }
</script>
<script src="https://unpkg.com/lucide@latest/dist/umd/lucide.js"></script>
<script>lucide.createIcons();</script>
</body>
</html>
"""

CALLS_PAGE = """
<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>EchoLine - Rozmowy</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
  *{box-sizing:border-box;margin:0;padding:0;}
  .bg-particles{position:fixed;inset:0;overflow:hidden;pointer-events:none;z-index:0;}
  .bg-particles span{position:absolute;bottom:-10px;border-radius:50%;background:#7c6aff;opacity:0;animation:floatDust linear infinite;}
  @keyframes floatDust{
    0%{transform:translateY(0) translateX(0);opacity:0;}
    10%{opacity:0.4;}
    90%{opacity:0.4;}
    100%{transform:translateY(-105vh) translateX(30px);opacity:0;}
  }
  .langbtn{border:1px solid #eee;background:#fff;color:#999;}
  .langbtn.active{background:#111;color:#fff;border-color:#111;}
  body{font-family:'Inter',sans-serif;background:#fff;color:#111;display:flex;min-height:100vh;}

  @keyframes riseIn{from{opacity:0;transform:translateY(10px);}to{opacity:1;transform:none;}}
  .rise{animation:riseIn .5s cubic-bezier(.16,1,.3,1) both;}

  .sidebar{width:230px;flex-shrink:0;border-right:1px solid #eee;padding:20px 12px;display:flex;flex-direction:column;}
  .logo{font-size:15px;font-weight:800;padding:8px 8px 20px;letter-spacing:-0.01em;display:flex;align-items:center;gap:9px;}
  .logo-dot{width:22px;height:22px;border-radius:50%;background:radial-gradient(circle at 30% 30%,#a9c9ff,#7c6aff 60%,#5a4bd4);flex-shrink:0;box-shadow:0 0 14px rgba(124,106,255,0.4);}
  .nav-item{display:flex;align-items:center;gap:10px;padding:9px 10px;border-radius:9px;font-size:13.5px;font-weight:500;color:#555;text-decoration:none;margin-bottom:2px;cursor:pointer;}
  .nav-item:hover{background:#f5f5f7;}
  .nav-item.active{background:linear-gradient(135deg,#7c6aff,#5dadff);color:#fff;box-shadow:0 6px 16px rgba(124,106,255,0.3);}
  .nav-icon{width:17px;height:17px;flex-shrink:0;stroke:#666;fill:none;stroke-width:1.8;}
  .nav-item.active .nav-icon{stroke:#fff;}
  .nav-section-label{font-size:10.5px;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;color:#bbb;padding:16px 10px 6px;}

  .sidebar-widget{margin-top:auto;background:linear-gradient(160deg,#f2f0ff,#eef6ff);border-radius:16px;padding:18px;text-align:left;}
  .sidebar-widget .sw-title{font-size:12.5px;font-weight:700;color:#5a4bd4;line-height:1.4;margin-bottom:14px;}
  .sw-orbit{width:76px;height:76px;margin:6px auto 14px;position:relative;}
  .sw-sphere{width:44px;height:44px;border-radius:50%;background:radial-gradient(circle at 30% 30%,#c9d9ff,#7c6aff 55%,#4f3fcf);position:absolute;top:16px;left:16px;box-shadow:0 0 22px rgba(124,106,255,0.5);}
  .sw-ring{position:absolute;inset:0;border:1.5px solid rgba(124,106,255,0.35);border-radius:50%;transform:rotate(-20deg) scaleY(0.42);}
  .sw-link{display:flex;align-items:center;gap:6px;font-size:12px;font-weight:600;color:#5a4bd4;text-decoration:none;}

  @keyframes riseIn{from{opacity:0;transform:translateY(10px);}to{opacity:1;transform:none;}}
  .rise{animation:riseIn .5s cubic-bezier(.16,1,.3,1) both;}
  .rise2{animation:riseIn .5s .08s cubic-bezier(.16,1,.3,1) both;}
  .rise3{animation:riseIn .5s .16s cubic-bezier(.16,1,.3,1) both;}
  .rise4{animation:riseIn .5s .24s cubic-bezier(.16,1,.3,1) both;}

  .main{flex:1;padding:36px;max-width:1100px;position:relative;}
  .hero-glow{position:absolute;top:-30px;left:10%;width:500px;height:220px;background:radial-gradient(ellipse,rgba(124,106,255,0.12),transparent 70%);pointer-events:none;z-index:0;}
  .head{display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:26px;flex-wrap:wrap;gap:12px;position:relative;z-index:1;}
  .head h1{font-size:27px;font-weight:800;letter-spacing:-0.015em;margin-bottom:6px;}
  .head p{font-size:14px;color:#888;}

  .stat-row{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:26px;position:relative;z-index:1;}
  .stat-card{border:1px solid #eee;border-radius:14px;padding:18px 20px;display:flex;align-items:center;gap:14px;transition:all .2s;}
  .stat-card:hover{border-color:#d9d2ff;box-shadow:0 10px 24px -12px rgba(124,106,255,0.2);transform:translateY(-2px);}
  .stat-icon{width:40px;height:40px;border-radius:11px;display:flex;align-items:center;justify-content:center;flex-shrink:0;}
  .stat-icon svg{width:19px;height:19px;fill:none;stroke-width:1.8;}
  .stat-icon.purple{background:rgba(124,106,255,0.1);}
  .stat-icon.purple svg{stroke:#7c6aff;}
  .stat-icon.teal{background:rgba(34,211,160,0.1);}
  .stat-icon.teal svg{stroke:#1e9e78;}
  .stat-icon.amber{background:rgba(245,166,35,0.12);}
  .stat-icon.amber svg{stroke:#c9840f;}
  .stat-card .lbl{font-size:11.5px;color:#999;font-weight:600;margin-bottom:3px;}
  .stat-card .val{font-size:22px;font-weight:800;}

  .filters{display:flex;gap:10px;margin-bottom:18px;flex-wrap:wrap;position:relative;z-index:1;}
  .filter-btn{padding:8px 16px;border-radius:100px;border:1px solid #eee;background:#fff;font-size:12.5px;font-weight:600;color:#666;cursor:pointer;transition:all .15s;}
  .filter-btn:hover{border-color:#d9d2ff;}
  .filter-btn.active{background:linear-gradient(135deg,#7c6aff,#5dadff);color:#fff;border-color:transparent;box-shadow:0 6px 16px rgba(124,106,255,0.3);}

  .calls-table{border:1px solid #eee;border-radius:16px;overflow:hidden;position:relative;z-index:1;}
  table{width:100%;border-collapse:collapse;}
  th{background:#fafafa;color:#999;font-weight:600;text-transform:uppercase;font-size:10.5px;letter-spacing:0.04em;padding:12px 16px;text-align:left;}
  td{padding:14px 16px;border-top:1px solid #f5f5f5;font-size:13px;}
  tr.datarow{transition:background .15s;}
  tr.datarow:hover{background:#fafaff;}
  .tag{display:inline-block;padding:3px 10px;border-radius:100px;font-size:11px;font-weight:700;}
  .tag.ok{background:#e8f8f0;color:#1e9e63;}
  .tag.missed{background:#fdf3e3;color:#c9840f;}
  .call-type{display:flex;align-items:center;gap:6px;}
  .call-type svg{width:14px;height:14px;stroke:#7c6aff;fill:none;stroke-width:2;}

  .empty-state{text-align:center;padding:70px 20px;}
  .empty-icon{width:70px;height:70px;border-radius:50%;background:linear-gradient(135deg,rgba(124,106,255,0.12),rgba(93,173,255,0.12));display:flex;align-items:center;justify-content:center;margin:0 auto 18px;box-shadow:0 0 30px rgba(124,106,255,0.15);}
  .empty-icon svg{width:28px;height:28px;stroke:#7c6aff;fill:none;stroke-width:1.6;}
  .empty-state b{display:block;font-size:15px;margin-bottom:6px;}
  .empty-state p{font-size:13px;color:#999;}

  @media (max-width: 760px) {
    body{flex-direction:column;}
    .sidebar{width:100%;border-right:none;border-bottom:1px solid #eee;flex-direction:row;align-items:center;padding:12px 16px;overflow-x:auto;white-space:nowrap;}
    .sidebar-widget,.nav-section-label{display:none;}
    .logo{padding:0 14px 0 0;}
    .nav-item span.label{display:none;}
    .main{padding:20px 16px;}
    .head h1{font-size:21px;}
    .stat-row{grid-template-columns:1fr;}
    .calls-table{overflow-x:auto;}
    table{font-size:11.5px;}
    td,th{padding:10px 8px;}
  }
</style>
</head>
<body>
<div class="bg-particles">
  <span style="left:6%;width:5px;height:5px;animation-duration:16s;animation-delay:0s;"></span>
  <span style="left:16%;width:3px;height:3px;animation-duration:12s;animation-delay:2s;"></span>
  <span style="left:28%;width:4px;height:4px;animation-duration:19s;animation-delay:4s;"></span>
  <span style="left:42%;width:3px;height:3px;animation-duration:14s;animation-delay:1s;"></span>
  <span style="left:58%;width:5px;height:5px;animation-duration:17s;animation-delay:6s;"></span>
  <span style="left:71%;width:3px;height:3px;animation-duration:13s;animation-delay:3s;"></span>
  <span style="left:83%;width:4px;height:4px;animation-duration:18s;animation-delay:5s;"></span>
  <span style="left:92%;width:3px;height:3px;animation-duration:15s;animation-delay:7s;"></span>
</div>

<div class="sidebar">
  <div class="logo"><span class="logo-dot"></span>EchoLine</div>
  <a class="nav-item{{ ' active' if active_page == 'dashboard' else '' }}" href="/dashboard">
    <i data-lucide="layout-dashboard" class="nav-icon"></i>
    <span class="label" data-i18n="nav_dashboard">Dashboard</span>
  </a>
  <a class="nav-item{{ ' active' if active_page == 'number' else '' }}" href="/numer-telefonu">
    <i data-lucide="phone" class="nav-icon"></i>
    <span class="label" data-i18n="nav_number">Numer telefonu</span>
  </a>
  <a class="nav-item{{ ' active' if active_page == 'voice' else '' }}" href="/moj-glos">
    <i data-lucide="mic" class="nav-icon"></i>
    <span class="label" data-i18n="nav_voice">Mój głos</span>
  </a>
  <a class="nav-item{{ ' active' if active_page == 'calls' else '' }}" href="/rozmowy">
    <i data-lucide="message-circle" class="nav-icon"></i>
    <span class="label" data-i18n="nav_calls">Rozmowy</span>
  </a>
  <a class="nav-item{{ ' active' if active_page == 'pricing' else '' }}" href="/cennik">
    <i data-lucide="credit-card" class="nav-icon"></i>
    <span class="label" data-i18n="nav_pricing">Cennik</span>
  </a>
  <div class="nav-section-label" data-i18n="nav_account">Konto</div>
  <a class="nav-item{{ ' active' if active_page == 'settings' else '' }}" href="/ustawienia">
    <i data-lucide="settings" class="nav-icon"></i>
    <span class="label" data-i18n="nav_settings">Ustawienia</span>
  </a>

  <div class="sidebar-widget">
    <div class="sw-title" id="swTitle">Twój asystent AI<br>24/7 gotowy do rozmów</div>
    <div class="sw-orbit"><div class="sw-ring"></div><div class="sw-sphere"></div></div>
    <a class="sw-link" href="/dashboard" data-i18n="widget_link">Zobacz statystyki →</a>
  </div>
</div>

<div class="main rise">
  <div class="hero-glow"></div>
  <div class="lang-switch-top" style="display:flex;justify-content:flex-end;gap:4px;margin-bottom:12px;position:relative;z-index:1;">
    <button id="langPl" onclick="setLang('pl')" class="langbtn" style="padding:4px 10px;border-radius:100px;font-size:11px;font-weight:700;cursor:pointer;">PL</button>
    <button id="langEn" onclick="setLang('en')" class="langbtn" style="padding:4px 10px;border-radius:100px;font-size:11px;font-weight:700;cursor:pointer;">EN</button>
  </div>
  <div class="head">
    <div>
      <h1 data-i18n="page_title">Rozmowy</h1>
      <p data-i18n="page_sub">Historia i transkrypcje wszystkich połączeń Twojego asystenta.</p>
    </div>
  </div>

  <div class="stat-row rise2">
    <div class="stat-card">
      <div class="stat-icon purple"><svg viewBox="0 0 24 24"><path d="M21 11.5a8.4 8.4 0 0 1-9 8.5 8.7 8.7 0 0 1-4-1L3 20l1-4a8.4 8.4 0 0 1-1-4 8.4 8.4 0 0 1 9-8.5 8.5 8.5 0 0 1 9 8.5z"/></svg></div>
      <div><div class="lbl" data-i18n="stat_calls_month">Rozmowy w tym miesiącu</div><div class="val">{{ calls|length }}</div></div>
    </div>
    <div class="stat-card">
      <div class="stat-icon teal"><svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg></div>
      <div><div class="lbl" data-i18n="stat_completed">Zakończone pomyślnie</div><div class="val">{{ calls|length }}</div></div>
    </div>
    <div class="stat-card">
      <div class="stat-icon amber"><svg viewBox="0 0 24 24"><path d="M10.68 13.31a16 16 0 0 0 3.41 2.6l1.27-1.27a2 2 0 0 1 2.11-.45c.86.31 1.77.53 2.71.65A2 2 0 0 1 22 16.92z"/><line x1="23" y1="1" x2="1" y2="23"/><path d="M16 8l4-4"/><path d="M20 8l-4-4"/></svg></div>
      <div><div class="lbl" data-i18n="stat_missed">Nieodebrane</div><div class="val">0</div></div>
    </div>
  </div>

  <div class="filters rise3">
    <button class="filter-btn active" data-filter="all" onclick="filterCalls('all', this)" data-i18n="filter_all">Wszystkie</button>
    <button class="filter-btn" data-filter="incoming" onclick="filterCalls('incoming', this)" data-i18n="filter_incoming">Przychodzące</button>
    <button class="filter-btn" data-filter="outbound" onclick="filterCalls('outbound', this)" data-i18n="filter_outbound">Zadzwoń za mnie</button>
    <button class="filter-btn" data-filter="missed" onclick="filterCalls('missed', this)" data-i18n="filter_missed">Nieodebrane</button>
  </div>

  {% if calls %}
  <div class="calls-table rise4">
    <table>
      <tr><th data-i18n="th_date">Data</th><th data-i18n="th_type">Typ</th><th data-i18n="th_with">Z kim</th><th data-i18n="th_summary">Podsumowanie</th><th data-i18n="th_status">Status</th></tr>
      {% for call in calls %}
      <tr class="datarow" data-type="incoming" data-status="ok">
        <td>{{ call.data }}</td>
        <td><div class="call-type"><svg viewBox="0 0 24 24"><path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6 19.8 19.8 0 0 1-3.1-8.6A2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .3 2 .6 3a2 2 0 0 1-.5 2.1L8 10a16 16 0 0 0 6 6l1.2-1.2a2 2 0 0 1 2.1-.5c1 .3 2 .5 3 .6a2 2 0 0 1 1.7 2z"/></svg><span data-i18n="incoming_label">Przychodząca</span></div></td>
        <td>{{ call.z_kim }}</td>
        <td>{{ call.podsumowanie }}</td>
        <td><span class="tag ok" data-i18n="status_completed">Zakończona</span></td>
      </tr>
      {% endfor %}
    </table>

  </div>
  {% else %}
  <div class="calls-table">
    <div class="empty-state">
      <div class="empty-icon"><svg viewBox="0 0 24 24"><path d="M21 11.5a8.4 8.4 0 0 1-9 8.5 8.7 8.7 0 0 1-4-1L3 20l1-4a8.4 8.4 0 0 1-1-4 8.4 8.4 0 0 1 9-8.5 8.5 8.5 0 0 1 9 8.5z"/></svg></div>
      <b data-i18n="empty_title">Nie masz jeszcze żadnych rozmów</b>
      <p data-i18n="empty_desc">Gdy Twój asystent odbierze pierwsze połączenie, pojawi się tutaj.</p>
    </div>
  </div>
  {% endif %}
</div>

<script>
  function filterCalls(type, btn){
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');

    document.querySelectorAll('.datarow').forEach(row => {
      const rowType = row.dataset.type;
      const rowStatus = row.dataset.status;
      let show = true;
      if (type === 'incoming') show = rowType === 'incoming';
      else if (type === 'outbound') show = rowType === 'outbound';
      else if (type === 'missed') show = rowStatus === 'missed';
      row.style.display = show ? '' : 'none';
    });
  }

  const CALLS_I18N = {
    pl: {
      nav_dashboard: 'Dashboard',
      nav_number: 'Numer telefonu',
      nav_voice: 'Mój głos',
      nav_calls: 'Rozmowy',
      nav_pricing: 'Cennik',
      nav_account: 'Konto',
      nav_settings: 'Ustawienia',
      widget_title_html: 'Twój asystent AI<br>24/7 gotowy do rozmów',
      widget_link: 'Zobacz statystyki →',
      page_title: 'Rozmowy',
      page_sub: 'Historia i transkrypcje wszystkich połączeń Twojego asystenta.',
      stat_calls_month: 'Rozmowy w tym miesiącu',
      stat_completed: 'Zakończone pomyślnie',
      stat_missed: 'Nieodebrane',
      filter_all: 'Wszystkie',
      filter_incoming: 'Przychodzące',
      filter_outbound: 'Zadzwoń za mnie',
      filter_missed: 'Nieodebrane',
      th_date: 'Data',
      th_type: 'Typ',
      th_with: 'Z kim',
      th_summary: 'Podsumowanie',
      th_status: 'Status',
      incoming_label: 'Przychodząca',
      status_completed: 'Zakończona',
      empty_title: 'Nie masz jeszcze żadnych rozmów',
      empty_desc: 'Gdy Twój asystent odbierze pierwsze połączenie, pojawi się tutaj.',
    },
    en: {
      nav_dashboard: 'Dashboard',
      nav_number: 'Phone number',
      nav_voice: 'My voice',
      nav_calls: 'Calls',
      nav_pricing: 'Pricing',
      nav_account: 'Account',
      nav_settings: 'Settings',
      widget_title_html: 'Your AI assistant<br>ready 24/7',
      widget_link: 'View statistics →',
      page_title: 'Calls',
      page_sub: 'History and transcripts of all your assistant calls.',
      stat_calls_month: 'Calls this month',
      stat_completed: 'Completed successfully',
      stat_missed: 'Missed',
      filter_all: 'All',
      filter_incoming: 'Incoming',
      filter_outbound: 'Call for me',
      filter_missed: 'Missed',
      th_date: 'Date',
      th_type: 'Type',
      th_with: 'With',
      th_summary: 'Summary',
      th_status: 'Status',
      incoming_label: 'Incoming',
      status_completed: 'Completed',
      empty_title: 'You do not have any calls yet',
      empty_desc: 'Once your assistant answers its first call, it will appear here.',
    }
  };

  let currentLang = (navigator.language || 'pl').slice(0, 2).toLowerCase() === 'pl' ? 'pl' : 'en';

  function ct(key){ return CALLS_I18N[currentLang][key] || key; }

  function applyCallsLang(){
    document.querySelectorAll('[data-i18n]').forEach(function(el){
      el.textContent = ct(el.getAttribute('data-i18n'));
    });
    document.getElementById('swTitle').innerHTML = ct('widget_title_html');
  }

  window.setLang = function(lang){
    currentLang = lang;
    document.getElementById('langPl').classList.toggle('active', lang === 'pl');
    document.getElementById('langEn').classList.toggle('active', lang === 'en');
    applyCallsLang();
  };

  setLang(currentLang);
</script>
<script src="https://unpkg.com/lucide@latest/dist/umd/lucide.js"></script>
<script>lucide.createIcons();</script>
</body>
</html>
"""

SETTINGS_PAGE = """
<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>EchoLine - Ustawienia</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
  *{box-sizing:border-box;margin:0;padding:0;}
  .bg-particles{position:fixed;inset:0;overflow:hidden;pointer-events:none;z-index:0;}
  .bg-particles span{position:absolute;bottom:-10px;border-radius:50%;background:#7c6aff;opacity:0;animation:floatDust linear infinite;}
  @keyframes floatDust{
    0%{transform:translateY(0) translateX(0);opacity:0;}
    10%{opacity:0.4;}
    90%{opacity:0.4;}
    100%{transform:translateY(-105vh) translateX(30px);opacity:0;}
  }
  .langbtn{border:1px solid #eee;background:#fff;color:#999;}
  .langbtn.active{background:#111;color:#fff;border-color:#111;}
  body{font-family:'Inter',sans-serif;background:#fff;color:#111;display:flex;min-height:100vh;}

  @keyframes riseIn{from{opacity:0;transform:translateY(10px);}to{opacity:1;transform:none;}}
  .rise{animation:riseIn .5s cubic-bezier(.16,1,.3,1) both;}
  .rise2{animation:riseIn .5s .08s cubic-bezier(.16,1,.3,1) both;}
  .rise3{animation:riseIn .5s .16s cubic-bezier(.16,1,.3,1) both;}
  .rise4{animation:riseIn .5s .24s cubic-bezier(.16,1,.3,1) both;}

  .sidebar{width:230px;flex-shrink:0;border-right:1px solid #eee;padding:20px 12px;display:flex;flex-direction:column;}
  .logo{font-size:15px;font-weight:800;padding:8px 8px 20px;letter-spacing:-0.01em;display:flex;align-items:center;gap:9px;}
  .logo-dot{width:22px;height:22px;border-radius:50%;background:radial-gradient(circle at 30% 30%,#a9c9ff,#7c6aff 60%,#5a4bd4);flex-shrink:0;box-shadow:0 0 14px rgba(124,106,255,0.4);}
  .nav-item{display:flex;align-items:center;gap:10px;padding:9px 10px;border-radius:9px;font-size:13.5px;font-weight:500;color:#555;text-decoration:none;margin-bottom:2px;cursor:pointer;}
  .nav-item:hover{background:#f5f5f7;}
  .nav-item.active{background:linear-gradient(135deg,#7c6aff,#5dadff);color:#fff;box-shadow:0 6px 16px rgba(124,106,255,0.3);}
  .nav-icon{width:17px;height:17px;flex-shrink:0;stroke:#666;fill:none;stroke-width:1.8;}
  .nav-item.active .nav-icon{stroke:#fff;}
  .nav-section-label{font-size:10.5px;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;color:#bbb;padding:16px 10px 6px;}

  .sidebar-widget{margin-top:auto;background:linear-gradient(160deg,#f2f0ff,#eef6ff);border-radius:16px;padding:18px;text-align:left;}
  .sidebar-widget .sw-title{font-size:12.5px;font-weight:700;color:#5a4bd4;line-height:1.4;margin-bottom:14px;}
  .sw-orbit{width:76px;height:76px;margin:6px auto 14px;position:relative;}
  .sw-sphere{width:44px;height:44px;border-radius:50%;background:radial-gradient(circle at 30% 30%,#c9d9ff,#7c6aff 55%,#4f3fcf);position:absolute;top:16px;left:16px;box-shadow:0 0 22px rgba(124,106,255,0.5);}
  .sw-ring{position:absolute;inset:0;border:1.5px solid rgba(124,106,255,0.35);border-radius:50%;transform:rotate(-20deg) scaleY(0.42);}
  .sw-link{display:flex;align-items:center;gap:6px;font-size:12px;font-weight:600;color:#5a4bd4;text-decoration:none;}

  .main{flex:1;padding:36px;max-width:760px;position:relative;}
  .hero-glow{position:absolute;top:-30px;left:20%;width:500px;height:220px;background:radial-gradient(ellipse,rgba(124,106,255,0.12),transparent 70%);pointer-events:none;z-index:0;}
  .head{margin-bottom:26px;position:relative;z-index:1;}
  .head h1{font-size:27px;font-weight:800;letter-spacing:-0.015em;margin-bottom:6px;}
  .head p{font-size:14px;color:#888;}

  .card{background:#fff;border:1px solid #eee;border-radius:16px;padding:24px;margin-bottom:18px;position:relative;z-index:1;transition:all .2s;}
  .card:hover{border-color:#e4e0ff;box-shadow:0 12px 30px -18px rgba(124,106,255,0.2);transform:translateY(-2px);}
  .card-head{display:flex;align-items:center;gap:11px;margin-bottom:20px;}
  .card-icon{width:34px;height:34px;border-radius:10px;display:flex;align-items:center;justify-content:center;flex-shrink:0;}
  .card-icon svg{width:16px;height:16px;fill:none;stroke-width:1.8;}
  .card-icon.purple{background:rgba(124,106,255,0.1);}
  .card-icon.purple svg{stroke:#7c6aff;}
  .card-icon.teal{background:rgba(34,211,160,0.1);}
  .card-icon.teal svg{stroke:#1e9e78;}
  .card-icon.blue{background:rgba(93,173,255,0.1);}
  .card-icon.blue svg{stroke:#3b8fe0;}
  .card-icon.red{background:rgba(239,68,68,0.1);}
  .card-icon.red svg{stroke:#dc2626;}
  .card-head h3{font-size:14.5px;font-weight:700;}

  .profile-row{display:flex;align-items:center;gap:16px;margin-bottom:6px;}
  .avatar-lg{width:56px;height:56px;border-radius:50%;background:radial-gradient(circle at 30% 30%,#a9c9ff,#7c6aff 55%,#4f3fcf);color:#fff;display:flex;align-items:center;justify-content:center;font-size:22px;font-weight:700;flex-shrink:0;box-shadow:0 0 30px rgba(124,106,255,0.4);}
  .profile-info b{display:block;font-size:15px;}
  .profile-info span{font-size:12.5px;color:#999;}

  .field-row{display:flex;justify-content:space-between;align-items:center;padding:13px 0;border-top:1px solid #f5f5f5;}
  .field-row:first-of-type{border-top:none;}
  .field-row .lbl{font-size:13px;color:#666;}
  .field-row .val{font-size:13px;font-weight:600;}
  .field-row input:focus{outline:none;border-color:#7c6aff !important;box-shadow:0 0 0 3px rgba(124,106,255,0.1);}

  .plan-banner{display:flex;justify-content:space-between;align-items:center;background:linear-gradient(135deg,#f8f7ff,#eef6ff);border-radius:14px;padding:18px 20px;position:relative;overflow:hidden;animation:planGlow 3.5s ease-in-out infinite;}
  @keyframes planGlow{0%,100%{box-shadow:0 0 0 rgba(124,106,255,0);}50%{box-shadow:0 8px 30px -10px rgba(124,106,255,0.3);}}
  .plan-banner b{font-size:16px;display:block;margin-bottom:2px;}
  .plan-banner span{font-size:12px;color:#888;}
  .plan-banner a{font-size:12.5px;font-weight:700;color:#fff;background:linear-gradient(135deg,#7c6aff,#5dadff);padding:10px 20px;border-radius:10px;text-decoration:none;white-space:nowrap;box-shadow:0 8px 20px rgba(124,106,255,0.3);transition:opacity .2s;}
  .plan-banner a:hover{opacity:0.9;}

  .btn-outline{padding:10px 18px;border-radius:10px;border:1.5px solid #ddd;background:#fff;font-weight:600;font-size:13px;cursor:pointer;color:#333;text-decoration:none;display:inline-block;transition:all .15s;}
  .btn-outline:hover{border-color:#7c6aff;color:#7c6aff;box-shadow:0 4px 12px rgba(124,106,255,0.12);}
  .btn-danger{padding:10px 18px;border-radius:10px;border:1.5px solid #fdecec;background:#fff;font-weight:600;font-size:13px;cursor:pointer;color:#c0392b;}
  .btn-danger:hover{background:#fdecec;}

  .danger-zone{border-color:#fde3e3;background:linear-gradient(180deg,#fffafa,#fff);}
  .danger-row{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;}
  .danger-row p{font-size:12.5px;color:#999;max-width:400px;}

  #saveMsg{display:none;font-size:12.5px;color:#1e9e63;margin-top:10px;}

  @media (max-width: 760px) {
    body{flex-direction:column;}
    .sidebar{width:100%;border-right:none;border-bottom:1px solid #eee;flex-direction:row;align-items:center;padding:12px 16px;overflow-x:auto;white-space:nowrap;}
    .sidebar-widget,.nav-section-label{display:none;}
    .logo{padding:0 14px 0 0;}
    .nav-item span.label{display:none;}
    .main{padding:20px 16px;}
    .head h1{font-size:21px;}
    .plan-banner{flex-direction:column;align-items:flex-start;gap:12px;}
    .danger-row{flex-direction:column;align-items:flex-start;}
  }
</style>
</head>
<body>
<div class="bg-particles">
  <span style="left:6%;width:5px;height:5px;animation-duration:16s;animation-delay:0s;"></span>
  <span style="left:16%;width:3px;height:3px;animation-duration:12s;animation-delay:2s;"></span>
  <span style="left:28%;width:4px;height:4px;animation-duration:19s;animation-delay:4s;"></span>
  <span style="left:42%;width:3px;height:3px;animation-duration:14s;animation-delay:1s;"></span>
  <span style="left:58%;width:5px;height:5px;animation-duration:17s;animation-delay:6s;"></span>
  <span style="left:71%;width:3px;height:3px;animation-duration:13s;animation-delay:3s;"></span>
  <span style="left:83%;width:4px;height:4px;animation-duration:18s;animation-delay:5s;"></span>
  <span style="left:92%;width:3px;height:3px;animation-duration:15s;animation-delay:7s;"></span>
</div>

<div class="sidebar">
  <div class="logo"><span class="logo-dot"></span>EchoLine</div>
  <a class="nav-item{{ ' active' if active_page == 'dashboard' else '' }}" href="/dashboard">
    <i data-lucide="layout-dashboard" class="nav-icon"></i>
    <span class="label" data-i18n="nav_dashboard">Dashboard</span>
  </a>
  <a class="nav-item{{ ' active' if active_page == 'number' else '' }}" href="/numer-telefonu">
    <i data-lucide="phone" class="nav-icon"></i>
    <span class="label" data-i18n="nav_number">Numer telefonu</span>
  </a>
  <a class="nav-item{{ ' active' if active_page == 'voice' else '' }}" href="/moj-glos">
    <i data-lucide="mic" class="nav-icon"></i>
    <span class="label" data-i18n="nav_voice">Mój głos</span>
  </a>
  <a class="nav-item{{ ' active' if active_page == 'calls' else '' }}" href="/rozmowy">
    <i data-lucide="message-circle" class="nav-icon"></i>
    <span class="label" data-i18n="nav_calls">Rozmowy</span>
  </a>
  <a class="nav-item{{ ' active' if active_page == 'pricing' else '' }}" href="/cennik">
    <i data-lucide="credit-card" class="nav-icon"></i>
    <span class="label" data-i18n="nav_pricing">Cennik</span>
  </a>
  <div class="nav-section-label" data-i18n="nav_account">Konto</div>
  <a class="nav-item{{ ' active' if active_page == 'settings' else '' }}" href="/ustawienia">
    <i data-lucide="settings" class="nav-icon"></i>
    <span class="label" data-i18n="nav_settings">Ustawienia</span>
  </a>

  <div class="sidebar-widget">
    <div class="sw-title" id="swTitle">Twój asystent AI<br>24/7 gotowy do rozmów</div>
    <div class="sw-orbit"><div class="sw-ring"></div><div class="sw-sphere"></div></div>
    <a class="sw-link" href="/dashboard" data-i18n="widget_link">Zobacz statystyki →</a>
  </div>
</div>

<div class="main rise">
  <div class="hero-glow"></div>
  <div class="lang-switch-top" style="display:flex;justify-content:flex-end;gap:4px;margin-bottom:12px;position:relative;z-index:1;">
    <button id="langPl" onclick="setLang('pl')" class="langbtn" style="padding:4px 10px;border-radius:100px;font-size:11px;font-weight:700;cursor:pointer;">PL</button>
    <button id="langEn" onclick="setLang('en')" class="langbtn" style="padding:4px 10px;border-radius:100px;font-size:11px;font-weight:700;cursor:pointer;">EN</button>
  </div>
  <div class="head">
    <h1 data-i18n="page_title">Ustawienia</h1>
    <p data-i18n="page_sub">Zarządzaj swoim kontem, subskrypcją i preferencjami.</p>
  </div>

  <div class="card rise2">
    <div class="card-head"><div class="card-icon purple"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 8v4l3 2"/></svg></div><h3 data-i18n="card_profile">Profil</h3></div>
    <div class="profile-row">
      <div class="avatar-lg" id="avatarLg">{{ user_email[0]|upper if user_email else "U" }}</div>
      <div class="profile-info">
        <b id="profileName">{{ user_email }}</b>
        <span id="profileEmail">{{ user_email }}</span>
      </div>
    </div>
    <div class="field-row">
      <span class="lbl" data-i18n="field_display_name">Imię wyświetlane</span>
      <input type="text" id="nameInput" data-i18n-ph="name_placeholder" placeholder="Twoje imię" style="border:1px solid #ddd;border-radius:8px;padding:7px 10px;font-size:13px;font-family:inherit;width:160px;text-align:right;">
    </div>
    <button class="btn-outline" onclick="saveProfile()" style="margin-top:12px;" data-i18n="btn_save_changes">Zapisz zmiany</button>
    <div id="saveMsg" data-i18n="save_confirm">Zapisano ✓</div>
  </div>

  <div class="card rise3">
    <div class="card-head"><div class="card-icon teal"><svg viewBox="0 0 24 24"><rect x="1" y="4" width="22" height="16" rx="2"/><line x1="1" y1="10" x2="23" y2="10"/></svg></div><h3 data-i18n="card_subscription">Subskrypcja</h3></div>
    <div class="plan-banner">
      <div>
        <b id="currentPlanName" data-i18n="checking_plan">Sprawdzam plan...</b>
        <span id="currentPlanDesc" data-i18n="loading_account">Ładowanie danych konta</span>
      </div>
      <a href="/cennik" data-i18n="change_plan_link">Zmień plan</a>
    </div>

    <div id="usageSection" style="margin-top:18px;">
      <div style="margin-bottom:14px;">
        <div style="display:flex;justify-content:space-between;font-size:12.5px;margin-bottom:6px;">
          <span style="color:#666;font-weight:600;" data-i18n="label_minutes">Minuty rozmów</span>
          <span id="minutesText" style="color:#999;">— / —</span>
        </div>
        <div style="background:#f0f0f0;border-radius:100px;height:8px;overflow:hidden;">
          <div id="minutesBar" style="background:linear-gradient(135deg,#7c6aff,#5dadff);height:100%;width:0%;border-radius:100px;transition:width .4s;"></div>
        </div>
      </div>
      <div>
        <div style="display:flex;justify-content:space-between;font-size:12.5px;margin-bottom:6px;">
          <span style="color:#666;font-weight:600;" data-i18n="label_quickcalls">Zlecenia Zadzwoń za mnie</span>
          <span id="quickCallsText" style="color:#999;">— / —</span>
        </div>
        <div style="background:#f0f0f0;border-radius:100px;height:8px;overflow:hidden;">
          <div id="quickCallsBar" style="background:linear-gradient(135deg,#22d3a0,#1e9e78);height:100%;width:0%;border-radius:100px;transition:width .4s;"></div>
        </div>
      </div>
      <div id="resetInfo" style="font-size:11.5px;color:#aaa;margin-top:10px;"></div>
    </div>
  </div>

  <div class="card rise3">
    <div class="card-head"><div class="card-icon blue"><svg viewBox="0 0 24 24"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg></div><h3 data-i18n="card_security">Bezpieczeństwo</h3></div>
    <div class="field-row">
      <span class="lbl" data-i18n="label_password">Hasło</span>
      <button class="btn-outline" onclick="resetPassword()" data-i18n="btn_reset_password">Zresetuj hasło</button>
    </div>
    <div id="resetMsg" style="font-size:12.5px;color:#1e9e63;margin-top:8px;display:none;"></div>
  </div>

  <div class="card danger-zone rise4">
    <div class="card-head"><div class="card-icon red"><svg viewBox="0 0 24 24"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg></div><h3 style="color:#c0392b;" data-i18n="card_danger">Strefa zagrożenia</h3></div>
    <div class="danger-row">
      <div>
        <b style="font-size:13.5px;" data-i18n="danger_title">Wyloguj się ze wszystkich urządzeń</b>
        <p data-i18n="danger_desc">Zakończy Twoją sesję na tym i innych urządzeniach.</p>
      </div>
      <a href="/logout" class="btn-outline" data-i18n="btn_logout">Wyloguj</a>
    </div>
  </div>
</div>

<script>
  const SETTINGS_I18N = {
    pl: {
      nav_dashboard: 'Dashboard', nav_number: 'Numer telefonu', nav_voice: 'Mój głos',
      nav_calls: 'Rozmowy', nav_pricing: 'Cennik', nav_account: 'Konto', nav_settings: 'Ustawienia',
      widget_title_html: 'Twój asystent AI<br>24/7 gotowy do rozmów',
      widget_link: 'Zobacz statystyki →',
      page_title: 'Ustawienia',
      page_sub: 'Zarządzaj swoim kontem, subskrypcją i preferencjami.',
      card_profile: 'Profil',
      field_display_name: 'Imię wyświetlane',
      name_placeholder: 'Twoje imię',
      btn_save_changes: 'Zapisz zmiany',
      save_confirm: 'Zapisano ✓',
      card_subscription: 'Subskrypcja',
      checking_plan: 'Sprawdzam plan...',
      loading_account: 'Ładowanie danych konta',
      change_plan_link: 'Zmień plan',
      label_minutes: 'Minuty rozmów',
      label_quickcalls: 'Zlecenia Zadzwoń za mnie',
      card_security: 'Bezpieczeństwo',
      label_password: 'Hasło',
      btn_reset_password: 'Zresetuj hasło',
      card_danger: 'Strefa zagrożenia',
      danger_title: 'Wyloguj się ze wszystkich urządzeń',
      danger_desc: 'Zakończy Twoją sesję na tym i innych urządzeniach.',
      btn_logout: 'Wyloguj',
      plan_start_name: 'Plan Start',
      plan_start_desc: '149 zł/mies. - 100 minut rozmów',
      plan_pro_name: 'Plan Pro',
      plan_pro_desc: '399 zł/mies. - 400 minut rozmów',
      plan_firma_name: 'Plan Firma',
      plan_firma_desc: '899 zł/mies. - 1000+ minut rozmów',
      plan_free_name: 'Brak aktywnego planu',
      plan_free_desc: 'Wybierz plan, aby aktywować asystenta',
      min_left: ' min zostało (',
      of_slash: ' / ',
      close_paren: ')',
      reset_prefix: 'Orientacyjny termin odnowienia: ',
      reset_suffix: ' (dokladna data zalezy od Twojego cyklu rozliczeniowego w Stripe)',
      reset_link_sent: 'Link do resetu hasla wyslany na ',
      error_prefix: 'Blad: ',
    },
    en: {
      nav_dashboard: 'Dashboard', nav_number: 'Phone number', nav_voice: 'My voice',
      nav_calls: 'Calls', nav_pricing: 'Pricing', nav_account: 'Account', nav_settings: 'Settings',
      widget_title_html: 'Your AI assistant<br>ready 24/7',
      widget_link: 'View statistics →',
      page_title: 'Settings',
      page_sub: 'Manage your account, subscription and preferences.',
      card_profile: 'Profile',
      field_display_name: 'Display name',
      name_placeholder: 'Your name',
      btn_save_changes: 'Save changes',
      save_confirm: 'Saved ✓',
      card_subscription: 'Subscription',
      checking_plan: 'Checking plan...',
      loading_account: 'Loading account data',
      change_plan_link: 'Change plan',
      label_minutes: 'Call minutes',
      label_quickcalls: 'Call for me requests',
      card_security: 'Security',
      label_password: 'Password',
      btn_reset_password: 'Reset password',
      card_danger: 'Danger zone',
      danger_title: 'Log out of all devices',
      danger_desc: 'Ends your session on this and other devices.',
      btn_logout: 'Log out',
      plan_start_name: 'Start plan',
      plan_start_desc: '149 PLN/mo - 100 call minutes',
      plan_pro_name: 'Pro plan',
      plan_pro_desc: '399 PLN/mo - 400 call minutes',
      plan_firma_name: 'Business plan',
      plan_firma_desc: '899 PLN/mo - 1000+ call minutes',
      plan_free_name: 'No active plan',
      plan_free_desc: 'Choose a plan to activate your assistant',
      min_left: ' min left (',
      of_slash: ' / ',
      close_paren: ')',
      reset_prefix: 'Estimated renewal date: ',
      reset_suffix: ' (exact date depends on your Stripe billing cycle)',
      reset_link_sent: 'Password reset link sent to ',
      error_prefix: 'Error: ',
    }
  };

  let currentLang = (navigator.language || 'pl').slice(0, 2).toLowerCase() === 'pl' ? 'pl' : 'en';

  function st(key){ return SETTINGS_I18N[currentLang][key] || key; }

  function applySettingsLang(){
    document.querySelectorAll('[data-i18n]').forEach(function(el){
      el.textContent = st(el.getAttribute('data-i18n'));
    });
    document.querySelectorAll('[data-i18n-ph]').forEach(function(el){
      el.placeholder = st(el.getAttribute('data-i18n-ph'));
    });
    document.getElementById('swTitle').innerHTML = st('widget_title_html');
    if (typeof window.refreshPlanTexts === 'function') window.refreshPlanTexts();
  }

  window.setLang = function(lang){
    currentLang = lang;
    document.getElementById('langPl').classList.toggle('active', lang === 'pl');
    document.getElementById('langEn').classList.toggle('active', lang === 'en');
    applySettingsLang();
  };

  setLang(currentLang);
</script>

<script type="module">
  import { initializeApp } from "https://www.gstatic.com/firebasejs/10.13.0/firebase-app.js";
  import { getAuth, onAuthStateChanged, sendPasswordResetEmail, updateProfile } from "https://www.gstatic.com/firebasejs/10.13.0/firebase-auth.js";
  import { getFirestore, doc, getDoc, updateDoc } from "https://www.gstatic.com/firebasejs/10.13.0/firebase-firestore.js";

  const firebaseConfig = {{ firebase_config | tojson }};
  const app = initializeApp(firebaseConfig);
  const auth = getAuth(app);
  const db = getFirestore(app);

  let currentUser = null;
  let lastUserData = null;

  const PLAN_KEYS = {
    start: ['plan_start_name', 'plan_start_desc'],
    pro: ['plan_pro_name', 'plan_pro_desc'],
    firma: ['plan_firma_name', 'plan_firma_desc'],
    free: ['plan_free_name', 'plan_free_desc']
  };

  const PLAN_LIMITS = {
    start: { minutes: 100, quickCalls: 5 },
    pro: { minutes: 400, quickCalls: 30 },
    firma: { minutes: 1000, quickCalls: 999 },
    free: { minutes: 0, quickCalls: 0 }
  };

  window.refreshPlanTexts = function(){
    if (!lastUserData) return;
    const data = lastUserData;
    const plan = data.subscriptionActive ? (data.plan || 'free') : 'free';
    const keys = PLAN_KEYS[plan] || PLAN_KEYS['free'];
    document.getElementById('currentPlanName').textContent = st(keys[0]);
    document.getElementById('currentPlanDesc').textContent = st(keys[1]);

    const limits = PLAN_LIMITS[plan] || PLAN_LIMITS['free'];
    const minutesUsed = data.minutesUsed || 0;
    const quickCallsUsed = data.quickCallsUsed || 0;
    const minutesLeft = Math.max(limits.minutes - minutesUsed, 0);
    const quickCallsLeft = Math.max(limits.quickCalls - quickCallsUsed, 0);

    document.getElementById('minutesText').textContent = minutesLeft + st('min_left') + minutesUsed + st('of_slash') + limits.minutes + st('close_paren');
    document.getElementById('minutesBar').style.width = limits.minutes > 0 ? Math.min((minutesUsed / limits.minutes) * 100, 100) + '%' : '0%';

    document.getElementById('quickCallsText').textContent = quickCallsLeft + st('min_left').replace(' min', '') + quickCallsUsed + st('of_slash') + limits.quickCalls + st('close_paren');
    document.getElementById('quickCallsBar').style.width = limits.quickCalls > 0 ? Math.min((quickCallsUsed / limits.quickCalls) * 100, 100) + '%' : '0%';

    const resetInfoEl = document.getElementById('resetInfo');
    if (data.planActivatedAt) {
      const activated = new Date(data.planActivatedAt);
      const nextReset = new Date(activated.getTime() + 30 * 24 * 60 * 60 * 1000);
      resetInfoEl.textContent = st('reset_prefix') + nextReset.toLocaleDateString() + st('reset_suffix');
    } else {
      resetInfoEl.textContent = '';
    }
  };

  onAuthStateChanged(auth, async (user) => {
    if (!user) return;
    currentUser = user;

    if (user.displayName) {
      document.getElementById("profileName").textContent = user.displayName;
      document.getElementById("nameInput").value = user.displayName;
      document.getElementById("avatarLg").textContent = user.displayName[0].toUpperCase();
    }

    const snap = await getDoc(doc(db, "users", user.uid));
    const data = snap.exists() ? snap.data() : {};
    lastUserData = data;
    window.refreshPlanTexts();
  });

  window.saveProfile = async function(){
    if (!currentUser) return;
    const name = document.getElementById("nameInput").value.trim();
    if (!name) return;
    await updateProfile(currentUser, { displayName: name });
    await updateDoc(doc(db, "users", currentUser.uid), { name: name });
    document.getElementById("profileName").textContent = name;
    document.getElementById("avatarLg").textContent = name[0].toUpperCase();
    const msg = document.getElementById("saveMsg");
    msg.style.display = "block";
    setTimeout(() => { msg.style.display = "none"; }, 2500);
  };

  window.resetPassword = async function(){
    if (!currentUser || !currentUser.email) return;
    const msg = document.getElementById("resetMsg");
    try {
      await sendPasswordResetEmail(auth, currentUser.email);
      msg.textContent = st('reset_link_sent') + currentUser.email;
      msg.style.display = "block";
    } catch (e) {
      msg.textContent = st('error_prefix') + e.message;
      msg.style.color = "#c0392b";
      msg.style.display = "block";
    }
  };
</script>
<script src="https://unpkg.com/lucide@latest/dist/umd/lucide.js"></script>
<script>lucide.createIcons();</script>
</body>
</html>
"""

ADMIN_PAGE = """
<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>EchoLine - Panel administracyjny</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
  *{box-sizing:border-box;margin:0;padding:0;}
  body{font-family:'Inter',sans-serif;background:#fafafa;color:#111;padding:36px;}
  .head{margin-bottom:26px;}
  .head h1{font-size:26px;font-weight:800;letter-spacing:-0.01em;margin-bottom:6px;}
  .head p{font-size:14px;color:#888;}
  .head a{font-size:13px;color:#7c6aff;text-decoration:none;font-weight:600;}

  .stat-row{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:26px;}
  .stat-card{background:#fff;border:1px solid #eee;border-radius:14px;padding:18px 20px;}
  .stat-card .lbl{font-size:11.5px;color:#999;font-weight:600;margin-bottom:6px;}
  .stat-card .val{font-size:24px;font-weight:800;}

  .table-wrap{background:#fff;border:1px solid #eee;border-radius:16px;overflow:hidden;overflow-x:auto;}
  table{width:100%;border-collapse:collapse;min-width:800px;}
  th{background:#fafafa;color:#999;font-weight:600;text-transform:uppercase;font-size:10.5px;letter-spacing:0.04em;padding:12px 16px;text-align:left;}
  td{padding:14px 16px;border-top:1px solid #f5f5f5;font-size:13px;}
  tr:hover{background:#fafaff;}
  .tag{display:inline-block;padding:3px 10px;border-radius:100px;font-size:11px;font-weight:700;}
  .tag.ok{background:#e8f8f0;color:#1e9e63;}
  .tag.off{background:#f5f5f5;color:#999;}
  .bar-mini{width:80px;height:6px;background:#f0f0f0;border-radius:100px;overflow:hidden;display:inline-block;vertical-align:middle;margin-right:6px;}
  .bar-mini-fill{height:100%;background:linear-gradient(135deg,#7c6aff,#5dadff);}

  @media (max-width: 760px) {
    body{padding:20px 16px;}
    .stat-row{grid-template-columns:repeat(2,1fr);}
  }
</style>
</head>
<body>

<div class="head">
  <h1>Panel administracyjny</h1>
  <p>Wszyscy klienci EchoLine i ich zużycie. <a href="/dashboard">← Wróć do dashboardu</a></p>
</div>

<div class="stat-row">
  <div class="stat-card"><div class="lbl">Wszystkich kont</div><div class="val">{{ total_users }}</div></div>
  <div class="stat-card"><div class="lbl">Aktywne subskrypcje</div><div class="val">{{ active_subs }}</div></div>
  <div class="stat-card"><div class="lbl">Plan Start</div><div class="val">{{ plan_counts.start }}</div></div>
  <div class="stat-card"><div class="lbl">Plan Pro / Firma</div><div class="val">{{ plan_counts.pro_firma }}</div></div>
</div>

<div class="table-wrap">
  <table>
    <tr>
      <th>Email</th>
      <th>Plan</th>
      <th>Status</th>
      <th>Minuty</th>
      <th>Zlecenia</th>
      <th>Numer</th>
      <th>Konto utworzone</th>
    </tr>
    {% for u in users %}
    <tr>
      <td>{{ u.email }}</td>
      <td>{{ u.plan }}</td>
      <td>
        {% if u.subscriptionActive %}<span class="tag ok">Aktywny</span>{% else %}<span class="tag off">Nieaktywny</span>{% endif %}
      </td>
      <td>
        <span class="bar-mini"><span class="bar-mini-fill" style="width:{{ u.minutes_pct }}%;"></span></span>
        {{ u.minutesUsed }} / {{ u.minutes_limit }}
      </td>
      <td>{{ u.quickCallsUsed }} / {{ u.quick_calls_limit }}</td>
      <td>{{ u.phoneNumber or "—" }}</td>
      <td>{{ u.createdAt }}</td>
    </tr>
    {% endfor %}
  </table>
</div>

</body>
</html>
"""

LEGAL_PAGE = """
<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>EchoLine - {{ page_title }}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
  *{box-sizing:border-box;margin:0;padding:0;}
  body{font-family:'Inter',sans-serif;background:#fafafa;color:#222;line-height:1.65;}
  .top{border-bottom:1px solid #eee;padding:18px 24px;display:flex;align-items:center;justify-content:space-between;background:#fff;}
  .logo{font-size:15px;font-weight:800;display:flex;align-items:center;gap:9px;color:#111;text-decoration:none;}
  .logo-dot{width:20px;height:20px;border-radius:50%;background:radial-gradient(circle at 30% 30%,#a9c9ff,#7c6aff 60%,#5a4bd4);}
  .top a.back{font-size:13px;color:#7c6aff;text-decoration:none;font-weight:600;}
  .wrap{max-width:740px;margin:0 auto;padding:48px 24px 80px;}
  .wrap h1{font-size:28px;font-weight:800;letter-spacing:-0.01em;margin-bottom:8px;}
  .updated{font-size:12.5px;color:#999;margin-bottom:32px;}
  .disclaimer{background:#fff8e6;border:1px solid #f5e0a3;border-radius:12px;padding:16px 18px;font-size:13px;color:#8a6d1f;margin-bottom:36px;line-height:1.55;}
  .wrap h2{font-size:18px;font-weight:700;margin:32px 0 12px;color:#111;}
  .wrap p{font-size:14.5px;color:#444;margin-bottom:12px;}
  .wrap ul{margin:0 0 12px 20px;}
  .wrap li{font-size:14.5px;color:#444;margin-bottom:6px;}
  .wrap strong{color:#111;}
  .wrap a{color:#7c6aff;}
  @media (max-width:600px){.wrap{padding:32px 18px 60px;} .wrap h1{font-size:23px;}}
</style>
</head>
<body>

<div class="top">
  <a class="logo" href="/"><span class="logo-dot"></span>EchoLine</a>
  <a class="back" href="/login">← Wróć do logowania</a>
</div>

<div class="wrap">
{{ content | safe }}
</div>

</body>
</html>
"""

@app.route("/")
def home():
    return "EchoLine test server running"

@app.route("/login")
def login():
    return render_template_string(LOGIN_PAGE, firebase_config=FIREBASE_CONFIG)

@app.route("/session-login", methods=["POST"])
def session_login():
    data = request.get_json()
    session["logged_in"] = True
    session["email"] = data.get("email")
    session["name"] = data.get("name")
    session["uid"] = data.get("uid")
    return {"ok": True}

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/dashboard")
def dashboard():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    real_calls = get_user_calls(session.get("uid", ""), limit=10)
    return render_template_string(
        DASHBOARD_PAGE,
        calls=real_calls if real_calls else FAKE_CALLS,
        user_email=session.get("email", ""),
        user_name=session.get("name") or (session.get("email", "").split("@")[0] if session.get("email") else ""),
        user_uid=session.get("uid", ""),
        firebase_config=FIREBASE_CONFIG,
        profile={},
        active_page="dashboard"
    )

@app.route("/moj-glos")
def moj_glos():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    return render_template_string(
        VOICE_PAGE,
        user_email=session.get("email", ""),
        firebase_config=FIREBASE_CONFIG,
        active_page="voice"
    )

@app.route("/numer-telefonu")
def numer_telefonu():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    return render_template_string(
        NUMBER_PAGE,
        user_email=session.get("email", ""),
        firebase_config=FIREBASE_CONFIG,
        active_page="number"
    )

@app.route("/cennik")
def cennik():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    return render_template_string(
        PRICING_PAGE,
        user_email=session.get("email", ""),
        firebase_config=FIREBASE_CONFIG,
        active_page="pricing"
    )

@app.route("/stripe-webhook", methods=["POST"])
def stripe_webhook():
    """
    Stripe wywoluje ten endpoint przy kazdym zdarzeniu platnosci.
    To jedyne miejsce, ktore naprawde wie czy klient zaplacil - dzieki temu
    nie polegamy juz na "zgadywaniu po czasie", tylko na realnym potwierdzeniu.
    """
    payload = request.data
    sig_header = request.headers.get("Stripe-Signature")

    if not STRIPE_WEBHOOK_SECRET:
        return {"error": "Brak skonfigurowanego STRIPE_WEBHOOK_SECRET"}, 500

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except Exception as e:
        return {"error": f"Nieprawidlowy webhook: {e}"}, 400

    event_type = event["type"]
    obj = event["data"]["object"]

    if not db_admin:
        return ("", 200)

    if event_type == "checkout.session.completed":
        uid = obj.get("client_reference_id")
        customer_id = obj.get("customer")
        subscription_id = obj.get("subscription")

        plan = "start"
        try:
            line_items = stripe.checkout.Session.list_line_items(obj["id"], limit=1)
            price_id = line_items["data"][0]["price"]["id"]
            plan = PLAN_PRICE_MAP.get(price_id, "start")
        except Exception as e:
            print("Nie udalo sie ustalic planu z line_items:", e)

        if uid:
            db_admin.collection("users").document(uid).set({
                "plan": plan,
                "subscriptionActive": True,
                "planActivatedAt": datetime.utcnow().isoformat(),
                "minutesUsed": 0,
                "quickCallsUsed": 0,
                "stripeCustomerId": customer_id,
                "stripeSubscriptionId": subscription_id,
            }, merge=True)

    elif event_type == "invoice.payment_succeeded":
        subscription_id = obj.get("subscription")
        if subscription_id:
            query = db_admin.collection("users").where("stripeSubscriptionId", "==", subscription_id).limit(1).stream()
            for doc in query:
                doc.reference.set({
                    "subscriptionActive": True,
                    "minutesUsed": 0,
                    "quickCallsUsed": 0,
                    "planActivatedAt": datetime.utcnow().isoformat(),
                    "lowUsageWarningSent": False,
                }, merge=True)

    elif event_type in ("invoice.payment_failed", "customer.subscription.deleted"):
        subscription_id = obj.get("subscription") or obj.get("id")
        if subscription_id:
            query = db_admin.collection("users").where("stripeSubscriptionId", "==", subscription_id).limit(1).stream()
            for doc in query:
                doc.reference.set({"subscriptionActive": False}, merge=True)

    return ("", 200)

@app.route("/rozmowy")
def rozmowy():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    real_calls = get_user_calls(session.get("uid", ""), limit=50)
    return render_template_string(
        CALLS_PAGE,
        calls=real_calls,
        user_email=session.get("email", ""),
        firebase_config=FIREBASE_CONFIG,
        active_page="calls"
    )

@app.route("/ustawienia")
def ustawienia():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    return render_template_string(
        SETTINGS_PAGE,
        user_email=session.get("email", ""),
        firebase_config=FIREBASE_CONFIG,
        active_page="settings"
    )

REGULAMIN_CONTENT = """
<h1>Regulamin świadczenia usług EchoLine</h1>
<div class="updated">Ostatnia aktualizacja: 8 lipca 2026</div>

<div class="disclaimer">
⚠️ <strong>Uwaga:</strong> to jest wzorcowy regulamin przygotowany jako punkt wyjścia. Przed rozpoczęciem realnej sprzedaży zdecydowanie zalecamy konsultację z prawnikiem, żeby dopasować go do Twojej konkretnej sytuacji (formy działalności, zakresu usług) i mieć pewność zgodności z aktualnymi przepisami.
</div>

<h2>§1. Postanowienia ogólne</h2>
<p>1. Niniejszy regulamin określa zasady korzystania z usługi EchoLine (dalej: "Usługa"), świadczonej przez Jakub Bąk (dalej: "Usługodawca").</p>
<p>2. Usługa polega na udostępnieniu użytkownikom (dalej: "Użytkownik") wirtualnego asystenta głosowego opartego na sztucznej inteligencji, który odbiera i/lub wykonuje połączenia telefoniczne w imieniu Użytkownika.</p>
<p>3. Korzystanie z Usługi oznacza akceptację niniejszego regulaminu w całości.</p>

<h2>§2. Warunki korzystania z Usługi</h2>
<p>1. Z Usługi mogą korzystać wyłącznie osoby pełnoletnie (18+), posiadające pełną zdolność do czynności prawnych, lub podmioty prowadzące działalność gospodarczą.</p>
<p>2. Użytkownik zobowiązany jest do podania prawdziwych danych podczas rejestracji konta.</p>
<p>3. Użytkownik ponosi pełną odpowiedzialność za treści przekazywane asystentowi AI oraz za sposób wykorzystania Usługi.</p>

<h2>§3. Obowiązek informowania o wykorzystaniu AI</h2>
<p>1. Zgodnie z wymogami unijnego Rozporządzenia w sprawie sztucznej inteligencji (AI Act), asystent głosowy EchoLine informuje rozmówcę na początku każdej rozmowy, że jest systemem sztucznej inteligencji.</p>
<p>2. Użytkownik nie może modyfikować asystenta w sposób, który ukrywałby ten fakt przed rozmówcą.</p>
<p>3. Rozmowy prowadzone przez asystenta mogą być nagrywane i transkrybowane w celu świadczenia Usługi (dokumentacja, historia rozmów, poprawa jakości).</p>

<h2>§4. Plany subskrypcyjne i płatności</h2>
<p>1. Usługa dostępna jest w ramach planów subskrypcyjnych (Start, Pro, Firma), których szczegóły i ceny dostępne są na stronie <a href="/cennik">Cennik</a>.</p>
<p>2. Płatności realizowane są cyklicznie (miesięcznie) za pośrednictwem operatora płatności Stripe.</p>
<p>3. Subskrypcja odnawia się automatycznie, chyba że Użytkownik ją anuluje przed końcem bieżącego okresu rozliczeniowego.</p>
<p>4. Każdy plan posiada limity (minuty rozmów, liczba zleceń) opisane w Cenniku. Przekroczenie limitu skutkuje czasowym ograniczeniem funkcjonalności do czasu odnowienia okresu rozliczeniowego lub zmiany planu.</p>
<p>5. Usługodawca zastrzega sobie prawo do zmiany cennika, o czym Użytkownicy zostaną poinformowani z odpowiednim wyprzedzeniem.</p>

<h2>§5. Odpowiedzialność</h2>
<p>1. Usługodawca dokłada należytej staranności, aby Usługa działała nieprzerwanie, jednak nie gwarantuje 100% dostępności (np. z powodu przerw technicznych, działania podmiotów trzecich takich jak dostawcy telekomunikacyjni).</p>
<p>2. Usługodawca nie ponosi odpowiedzialności za treść rozmów prowadzonych przez asystenta w zakresie, w jakim wynikają one z instrukcji przekazanych przez Użytkownika.</p>
<p>3. Użytkownik ponosi wyłączną odpowiedzialność za zgodność z prawem sposobu wykorzystania Usługi, w tym za wykorzystanie asystenta do kontaktu z osobami trzecimi.</p>

<h2>§6. Reklamacje</h2>
<p>1. Reklamacje dotyczące działania Usługi można zgłaszać na adres e-mail: jakub.bak111@gmail.com.</p>
<p>2. Usługodawca rozpatruje reklamacje w terminie 14 dni roboczych od ich otrzymania.</p>

<h2>§7. Rozwiązanie umowy</h2>
<p>1. Użytkownik może w każdej chwili zrezygnować z Usługi, anulując subskrypcję w panelu Ustawień.</p>
<p>2. Usługodawca zastrzega sobie prawo do zawieszenia lub usunięcia konta Użytkownika w przypadku naruszenia niniejszego regulaminu, w szczególności wykorzystania Usługi do celów niezgodnych z prawem.</p>

<h2>§8. Postanowienia końcowe</h2>
<p>1. Usługodawca zastrzega sobie prawo do zmiany niniejszego regulaminu. O zmianach Użytkownicy zostaną poinformowani drogą elektroniczną.</p>
<p>2. W sprawach nieuregulowanych niniejszym regulaminem zastosowanie mają przepisy prawa polskiego.</p>
<p>3. Kontakt: jakub.bak111@gmail.com</p>
"""

PRIVACY_CONTENT = """
<h1>Polityka Prywatności EchoLine</h1>
<div class="updated">Ostatnia aktualizacja: 8 lipca 2026</div>

<div class="disclaimer">
⚠️ <strong>Uwaga:</strong> to jest wzorcowa polityka prywatności przygotowana jako punkt wyjścia. Przed rozpoczęciem realnej sprzedaży zdecydowanie zalecamy konsultację z prawnikiem specjalizującym się w RODO, żeby mieć pewność pełnej zgodności z przepisami.
</div>

<h2>1. Administrator danych</h2>
<p>Administratorem danych osobowych zbieranych w ramach usługi EchoLine jest Jakub Bąk, kontakt: jakub.bak111@gmail.com.</p>

<h2>2. Jakie dane zbieramy</h2>
<ul>
  <li>Dane konta: adres e-mail, imię, identyfikator użytkownika.</li>
  <li>Dane głosowe: nagrania głosu przesyłane w celu sklonowania głosu asystenta.</li>
  <li>Dane rozmów: transkrypcje i podsumowania połączeń obsługiwanych przez asystenta.</li>
  <li>Dane rozliczeniowe: przetwarzane przez operatora płatności Stripe (EchoLine nie przechowuje pełnych danych kart płatniczych).</li>
  <li>Dane techniczne: adres IP, informacje o urządzeniu, w zakresie niezbędnym do działania Usługi.</li>
</ul>

<h2>3. Cel przetwarzania danych</h2>
<p>Dane przetwarzane są w celu: świadczenia Usługi (obsługa połączeń, klonowanie głosu, generowanie transkrypcji), realizacji płatności, kontaktu z Użytkownikiem, oraz wypełnienia obowiązków prawnych.</p>

<h2>4. Podstawa prawna przetwarzania</h2>
<p>Dane przetwarzane są na podstawie: (a) zgody Użytkownika, (b) niezbędności do wykonania umowy o świadczenie Usługi, (c) uzasadnionego interesu Administratora (np. zapobieganie nadużyciom), zgodnie z Rozporządzeniem Parlamentu Europejskiego i Rady (UE) 2016/679 (RODO).</p>

<h2>5. Podmioty przetwarzające dane (podwykonawcy)</h2>
<p>W celu świadczenia Usługi korzystamy z następujących zewnętrznych dostawców, którzy mogą przetwarzać dane w naszym imieniu:</p>
<ul>
  <li><strong>Google Firebase</strong> — uwierzytelnianie i baza danych.</li>
  <li><strong>Twilio</strong> — obsługa połączeń telefonicznych.</li>
  <li><strong>ElevenLabs</strong> — klonowanie i synteza głosu.</li>
  <li><strong>OpenAI</strong> — generowanie odpowiedzi asystenta AI.</li>
  <li><strong>Stripe</strong> — obsługa płatności.</li>
  <li><strong>Resend</strong> — wysyłka powiadomień e-mail.</li>
</ul>
<p>Każdy z tych podmiotów posiada własną politykę prywatności i odpowiednie zabezpieczenia danych.</p>

<h2>6. Okres przechowywania danych</h2>
<p>Dane przechowywane są przez czas trwania umowy o świadczenie Usługi oraz przez okres wymagany przepisami prawa (np. dla celów podatkowo-rachunkowych). Po usunięciu konta dane są usuwane lub anonimizowane, z zastrzeżeniem obowiązków prawnych wymagających dłuższego przechowywania.</p>

<h2>7. Prawa Użytkownika</h2>
<p>Zgodnie z RODO, Użytkownikowi przysługuje prawo do: dostępu do swoich danych, ich sprostowania, usunięcia ("prawo do bycia zapomnianym"), ograniczenia przetwarzania, przenoszenia danych oraz wniesienia sprzeciwu wobec przetwarzania. Użytkownik ma również prawo wniesienia skargi do Prezesa Urzędu Ochrony Danych Osobowych.</p>

<h2>8. Pliki cookies</h2>
<p>Serwis wykorzystuje pliki cookies niezbędne do prawidłowego działania (np. utrzymania sesji logowania). Nie wykorzystujemy plików cookies do celów reklamowych.</p>

<h2>9. Bezpieczeństwo danych</h2>
<p>Stosujemy odpowiednie środki techniczne i organizacyjne w celu ochrony danych, w tym szyfrowanie połączeń oraz ograniczony dostęp do danych wyłącznie dla upoważnionych osób.</p>

<h2>10. Kontakt</h2>
<p>W sprawach związanych z ochroną danych osobowych prosimy o kontakt: jakub.bak111@gmail.com.</p>
"""

@app.route("/regulamin")
def regulamin():
    return render_template_string(LEGAL_PAGE, page_title="Regulamin", content=REGULAMIN_CONTENT)

@app.route("/polityka-prywatnosci")
def polityka_prywatnosci():
    return render_template_string(LEGAL_PAGE, page_title="Polityka Prywatności", content=PRIVACY_CONTENT)

@app.route("/admin")
def admin():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    if not ADMIN_EMAIL or session.get("email", "").lower() != ADMIN_EMAIL.lower():
        return "Brak dostepu - ta strona jest tylko dla administratora.", 403

    if not db_admin:
        return "Baza danych niedostepna.", 500

    users_list = []
    total_users = 0
    active_subs = 0
    plan_counts = {"start": 0, "pro_firma": 0}

    for doc in db_admin.collection("users").stream():
        d = doc.to_dict()
        total_users += 1
        limits, plan = get_plan_limits(d)
        if d.get("subscriptionActive"):
            active_subs += 1
            if plan == "start":
                plan_counts["start"] += 1
            elif plan in ("pro", "firma"):
                plan_counts["pro_firma"] += 1

        minutes_used = d.get("minutesUsed", 0)
        minutes_pct = min((minutes_used / limits["minutes"]) * 100, 100) if limits["minutes"] > 0 else 0

        created_at = d.get("createdAt", "")
        try:
            created_at = datetime.fromisoformat(created_at).strftime("%Y-%m-%d") if created_at else "—"
        except Exception:
            created_at = "—"

        users_list.append({
            "email": d.get("email", "—"),
            "plan": plan,
            "subscriptionActive": d.get("subscriptionActive", False),
            "minutesUsed": round(minutes_used, 1),
            "minutes_limit": limits["minutes"],
            "minutes_pct": round(minutes_pct, 1),
            "quickCallsUsed": d.get("quickCallsUsed", 0),
            "quick_calls_limit": limits["quick_calls"],
            "phoneNumber": d.get("phoneNumber"),
            "createdAt": created_at,
        })

    return render_template_string(
        ADMIN_PAGE,
        users=users_list,
        total_users=total_users,
        active_subs=active_subs,
        plan_counts=plan_counts,
    )

@app.route("/search-numbers", methods=["GET"])
def search_numbers():
    if not session.get("logged_in"):
        return {"error": "not logged in"}, 401

    country = request.args.get("country", "PL")
    sid = os.environ.get("TWILIO_ACCOUNT_SID")
    token = os.environ.get("TWILIO_AUTH_TOKEN")
    if not sid or not token:
        return {"error": "Brak skonfigurowanych danych Twilio (TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN) na serwerze."}, 500

    # Niektore kraje nie oferuja numerow "Local" przez API - probujemy po kolei kilka typow
    number_types = ["Local", "National", "Mobile"]
    r = None
    last_error = None
    for number_type in number_types:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/AvailablePhoneNumbers/{country}/{number_type}.json"
        r = requests.get(url, auth=(sid, token), params={"PageSize": 6})
        if r.status_code == 200:
            break
        try:
            last_error = r.json().get("message", r.text)
        except Exception:
            last_error = r.text

    if r is None or r.status_code != 200:
        return {"error": f"Brak dostepnych numerow dla tego kraju (probowano: {', '.join(number_types)}). Blad: {last_error}"}, 500

    data = r.json()
    numbers = [
        {
            "phone_number": n.get("phone_number"),
            "friendly_name": n.get("friendly_name"),
            "locality": n.get("locality"),
            "region": n.get("region"),
        }
        for n in data.get("available_phone_numbers", [])
    ]
    return {"numbers": numbers}

@app.route("/buy-number", methods=["POST"])
def buy_number():
    if not session.get("logged_in"):
        return {"error": "not logged in"}, 401

    data = request.get_json()
    phone_number = data.get("phone_number")
    if not phone_number:
        return {"error": "brak numeru do aktywacji"}, 400

    sid = os.environ.get("TWILIO_ACCOUNT_SID")
    token = os.environ.get("TWILIO_AUTH_TOKEN")
    if not sid or not token:
        return {"error": "Brak skonfigurowanych danych Twilio na serwerze."}, 500

    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/IncomingPhoneNumbers.json"
    voice_url = request.url_root + "incoming-call"
    r = requests.post(url, auth=(sid, token), data={"PhoneNumber": phone_number, "VoiceUrl": voice_url})

    if r.status_code not in (200, 201):
        try:
            err = r.json().get("message", r.text)
        except Exception:
            err = r.text
        return {"error": err}, 500

    result = r.json()
    return {"phone_number": result.get("phone_number", phone_number)}

@app.route("/voice-library")
def voice_library():
    if not session.get("logged_in"):
        return {"error": "not logged in"}, 401

    lang = request.args.get("lang", "pl")
    headers = {"xi-api-key": ELEVENLABS_API_KEY}

    # Najpierw probujemy biblioteki spolecznosciowej (rozne jezyki/akcenty)
    url = "https://api.elevenlabs.io/v1/shared-voices"
    r = requests.get(url, headers=headers, params={"language": lang, "page_size": 8})

    voices_raw = []
    if r.status_code == 200:
        voices_raw = r.json().get("voices", [])

    result = [
        {
            "voice_id": v.get("voice_id"),
            "name": v.get("name"),
            "preview_url": v.get("preview_url"),
            "gender": v.get("gender", ""),
            "language": v.get("language", lang),
            "accent": v.get("accent", ""),
        }
        for v in voices_raw
    ]

    # Jesli brak wynikow dla danego jezyka - pokaz domyslne (premade) glosy jako fallback
    if not result:
        url2 = "https://api.elevenlabs.io/v1/voices"
        r2 = requests.get(url2, headers=headers)
        if r2.status_code == 200:
            voices = r2.json().get("voices", [])
            result = [
                {
                    "voice_id": v.get("voice_id"),
                    "name": v.get("name"),
                    "preview_url": v.get("preview_url"),
                    "gender": v.get("labels", {}).get("gender", ""),
                    "language": "multilingual",
                    "accent": v.get("labels", {}).get("accent", ""),
                }
                for v in voices if v.get("category") == "premade"
            ][:8]

    return {"voices": result[:8]}

@app.route("/test-voice", methods=["POST"])
def test_voice():
    if not session.get("logged_in"):
        return {"error": "not logged in"}, 401
    data = request.get_json()
    voice_id = data.get("voice_id")
    if not voice_id:
        return {"error": "brak voice_id"}, 400

    text = "Dzien dobry, tu Twoj asystent EchoLine. Tak brzmi Twoj sklonowany glos."
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"}
    payload = {"text": text, "model_id": "eleven_multilingual_v2"}

    r = requests.post(url, json=payload, headers=headers)
    if r.status_code == 200:
        return Response(r.content, mimetype="audio/mpeg")
    return {"error": r.text}, 500

@app.route("/clone-voice", methods=["POST"])
def clone_voice():
    if not session.get("logged_in"):
        return {"error": "not logged in"}, 401
    if "audio" not in request.files:
        return {"error": "brak pliku audio"}, 400
    audio_file = request.files["audio"]
    uid = session.get("uid", "unknown")
    old_voice_id = request.form.get("old_voice_id", "").strip()

    headers = {"xi-api-key": ELEVENLABS_API_KEY}

    # Usun poprzedni glos tego uzytkownika, jesli istnieje - zeby nie zapychac limitu kont
    if old_voice_id:
        try:
            requests.delete(f"https://api.elevenlabs.io/v1/voices/{old_voice_id}", headers=headers)
        except Exception:
            pass

    url = "https://api.elevenlabs.io/v1/voices/add"
    files = {"files": (audio_file.filename or "sample.webm", audio_file.stream, audio_file.mimetype)}
    data = {"name": f"echoline_user_{uid}"}

    r = requests.post(url, headers=headers, data=data, files=files)
    if r.status_code == 200:
        voice_id = r.json().get("voice_id")
        return {"voice_id": voice_id}
    return {"error": r.text}, 500

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
TWILIO_FROM_NUMBER = os.environ.get("TWILIO_FROM_NUMBER", "+12292139403")

# Przechowuje historie rozmow per polaczenie (CallSid -> dane)
CALL_CONTEXT = {}


def generate_speech_url(text, filename, voice_id=None):
    """Generuje mowe przez ElevenLabs (uzywajac konkretnego glosu jesli podany), zwraca publiczny URL."""
    vid = voice_id or ELEVENLABS_VOICE_ID
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{vid}"
    headers = {"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"}
    payload = {"text": text, "model_id": "eleven_multilingual_v2"}
    r = requests.post(url, json=payload, headers=headers)
    if r.status_code == 200:
        with open(f"static/{filename}", "wb") as f:
            f.write(r.content)
        return request.url_root + f"static/{filename}"
    return None


def ask_ai(messages):
    """Wysyla historie rozmowy do OpenAI, zwraca odpowiedz tekstowa."""
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": "gpt-4o-mini", "messages": messages, "max_tokens": 150}
    r = requests.post(url, json=payload, headers=headers)
    if r.status_code == 200:
        return r.json()["choices"][0]["message"]["content"].strip()
    return "Przepraszam, wystapil blad techniczny."


def gather_response_twiml(audio_url, action, lang_code="pl-PL", no_response_text="Nie uslyszalem odpowiedzi. Dziekuje za telefon, do uslyszenia."):
    """Buduje TwiML: odtwarza audio, potem sluchaj odpowiedzi (Gather ze speech recognition)."""
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather input="speech" action="{action}" method="POST" language="{lang_code}" speechTimeout="auto">
        <Play>{audio_url}</Play>
    </Gather>
    <Say language="{lang_code}">{no_response_text}</Say>
    <Hangup/>
</Response>'''


def limit_exceeded_twiml(reason, lang_code="pl-PL", text="Dzien dobry, przepraszam, ale w tej chwili nie moge przyjac polaczenia. Prosze sprobowac zadzwonic pozniej, lub napisac wiadomosc. Dziekuje."):
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say language="{lang_code}">{text}</Say>
    <Hangup/>
</Response>'''


SUFLER_INSTRUCTION = (
    " WAZNE: Jesli rozmowca zapyta o cos, czego nie wiesz na podstawie powyzszych "
    "informacji (np. szczegoly ktorych nie masz, decyzja wymagajaca wlasciciela firmy), "
    "NIE zgaduj i NIE wymyslaj odpowiedzi. Zamiast tego odpowiedz WYLACZNIE dokladnie w tym "
    "formacie: POTRZEBUJE_POMOCY: [krotki opis o co pyta rozmowca, w jezyku rozmowcy]"
)


def build_profile_prompt(user_data):
    """Buduje instrukcje systemowe na podstawie profilu asystenta konkretnego uzytkownika."""
    company = user_data.get("companyName") or "firmy"
    pricing = user_data.get("pricing") or "brak ustalonego cennika"
    hours = user_data.get("hours") or "brak ustalonych godzin"
    rules = user_data.get("rules") or "brak dodatkowych zasad"
    bot_lang = get_bot_language(user_data)
    return (
        f"Jestes asystentem AI odbierajacym telefon w imieniu: {company}. "
        f"{bot_lang['instruction']} Badz krotki, uprzejmy i konkretny. "
        f"Cennik i oferta: {pricing}. "
        f"Godziny pracy: {hours}. "
        f"Zasady i ograniczenia: {rules}."
        + SUFLER_INSTRUCTION
    )


def create_hint_request(uid, call_sid, question):
    """Zapisuje w bazie pytanie do wlasciciela - dashboard pokaze je na zywo."""
    if not db_admin or not uid:
        return
    db_admin.collection("hints").document(call_sid).set({
        "uid": uid,
        "call_sid": call_sid,
        "question": question,
        "hint": None,
        "answered": False,
        "created_at": datetime.utcnow().isoformat(),
    })


def check_hint_answer(call_sid):
    """Sprawdza czy wlasciciel juz odpowiedzial na pytanie suflera."""
    if not db_admin:
        return None
    doc = db_admin.collection("hints").document(call_sid).get()
    if doc.exists:
        data = doc.to_dict()
        if data.get("answered") and data.get("hint"):
            return data["hint"]
    return None


@app.route("/incoming-call", methods=["POST"])
def incoming_call():
    call_sid = request.form.get("CallSid", "unknown")
    called_number = request.form.get("To", "")

    owner_uid, owner_data = get_user_by_phone(called_number)

    remaining_minutes = None
    if owner_uid and owner_data:
        bot_lang = get_bot_language(owner_data)
        # Sprawdz limit minut wlasciciela tego numeru przed rozpoczeciem rozmowy
        ok, limit, used, plan = minutes_available(owner_data)
        if not ok:
            return Response(limit_exceeded_twiml("minutes", bot_lang["twilio"], bot_lang["limit_before"]), mimetype="text/xml")
        remaining_minutes = max(limit - used, 0)
        system_prompt = build_profile_prompt(owner_data)
        voice_id = owner_data.get("voiceId") or ELEVENLABS_VOICE_ID
        company_name = owner_data.get("companyName") or "firmy"
    else:
        # Fallback dla naszego wlasnego numeru testowego (bez przypisanego wlasciciela w bazie)
        bot_lang = BOT_LANGUAGES["pl"]
        system_prompt = (
            "Jestes asystentem AI odbierajacym telefon w imieniu firmy. "
            "Rozmawiaj po polsku, krotko, uprzejmie i konkretnie. "
            "Oto instrukcje jak masz sie zachowywac: " + bot_instructions["text"]
        )
        voice_id = ELEVENLABS_VOICE_ID
        company_name = None

    CALL_CONTEXT[call_sid] = {
        "messages": [{"role": "system", "content": system_prompt}],
        "voice_id": voice_id,
        "owner_uid": owner_uid,
        "started_at": time.time(),
        "remaining_minutes": remaining_minutes,
        "lang": bot_lang,
    }

    if company_name:
        greeting = f"{bot_lang['greeting_with_company'].format(company=company_name)} {bot_lang['greeting_disclosure']} {bot_lang['greeting_suffix']}"
    else:
        greeting = f"{bot_lang['greeting_generic']} {bot_lang['greeting_disclosure']} {bot_lang['greeting_suffix']}"
    CALL_CONTEXT[call_sid]["messages"].append({"role": "assistant", "content": greeting})

    audio_url = generate_speech_url(greeting, f"greet_{call_sid}.mp3", voice_id)
    if not audio_url:
        return Response(
            f'<?xml version="1.0" encoding="UTF-8"?><Response><Say language="{bot_lang["twilio"]}">{bot_lang["error"]}</Say></Response>',
            mimetype="text/xml"
        )
    return Response(gather_response_twiml(audio_url, "/handle-speech", bot_lang["twilio"], bot_lang["no_response"]), mimetype="text/xml")


@app.route("/handle-speech", methods=["POST"])
def handle_speech():
    call_sid = request.form.get("CallSid", "unknown")
    speech_result = request.form.get("SpeechResult", "")

    ctx = CALL_CONTEXT.get(call_sid)
    if not ctx:
        return Response(
            '<?xml version="1.0" encoding="UTF-8"?><Response><Say language="pl-PL">Sesja wygasla.</Say><Hangup/></Response>',
            mimetype="text/xml"
        )

    bot_lang = ctx.get("lang", BOT_LANGUAGES["pl"])

    # Sprawdz na biezaco czy nie przekroczylismy pozostalego limitu minut w trakcie rozmowy
    remaining = ctx.get("remaining_minutes")
    if remaining is not None:
        elapsed_minutes = (time.time() - ctx.get("started_at", time.time())) / 60
        if elapsed_minutes >= remaining:
            CALL_CONTEXT.pop(call_sid, None)
            return Response(
                f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say language="{bot_lang['twilio']}">{bot_lang['limit_during']}</Say>
    <Hangup/>
</Response>''',
                mimetype="text/xml"
            )

    ctx["messages"].append({"role": "user", "content": speech_result})
    reply = ask_ai(ctx["messages"])

    # Sufler: jesli AI sygnalizuje ze nie wie odpowiedzi, pytamy wlasciciela
    if reply.strip().startswith("POTRZEBUJE_POMOCY:") and ctx.get("owner_uid"):
        question = reply.split("POTRZEBUJE_POMOCY:", 1)[1].strip()
        create_hint_request(ctx["owner_uid"], call_sid, question)
        stall_text = bot_lang["stall"]
        ctx["messages"].append({"role": "assistant", "content": stall_text})
        audio_url = generate_speech_url(stall_text, f"stall_{call_sid}.mp3", ctx.get("voice_id"))
        if audio_url:
            return Response(f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>{audio_url}</Play>
    <Pause length="4"/>
    <Redirect method="POST">/check-hint?call_sid={call_sid}&amp;attempt=1</Redirect>
</Response>''', mimetype="text/xml")

    ctx["messages"].append({"role": "assistant", "content": reply})

    audio_url = generate_speech_url(reply, f"reply_{call_sid}_{len(ctx['messages'])}.mp3", ctx.get("voice_id"))
    if not audio_url:
        return Response(
            f'<?xml version="1.0" encoding="UTF-8"?><Response><Say language="{bot_lang["twilio"]}">{bot_lang["error"]}</Say><Hangup/></Response>',
            mimetype="text/xml"
        )
    ctx["last_audio_url"] = audio_url
    return Response(gather_response_twiml(audio_url, "/handle-speech", bot_lang["twilio"], bot_lang["no_response"]), mimetype="text/xml")


def summarize_call(messages):
    """Prosi AI o krotkie, jednozdaniowe podsumowanie calej rozmowy."""
    try:
        transcript_text = "\n".join(f"{m['role']}: {m['content']}" for m in messages if m["role"] != "system")
        summary_messages = [
            {"role": "system", "content": "Podsumuj ponizsza rozmowe telefoniczna w jednym, krotkim zdaniu po polsku."},
            {"role": "user", "content": transcript_text}
        ]
        return ask_ai(summary_messages)
    except Exception:
        return "Rozmowa zakonczona."


def save_call_record(owner_uid, ctx, from_number, to_number, duration_seconds, call_type):
    """Zapisuje pelny zapis rozmowy (transkrypcja + podsumowanie) do bazy danych."""
    if not db_admin or not owner_uid:
        return
    messages = ctx.get("messages", [])
    transcript = [m for m in messages if m["role"] != "system"]
    summary = summarize_call(messages) if len(transcript) > 1 else "Krotkie polaczenie testowe."

    db_admin.collection("calls").add({
        "uid": owner_uid,
        "from_number": from_number,
        "to_number": to_number,
        "transcript": transcript,
        "summary": summary,
        "duration_seconds": duration_seconds,
        "call_type": call_type,
        "created_at": datetime.utcnow().isoformat(),
    })


@app.route("/check-hint", methods=["GET", "POST"])
def check_hint():
    """Sprawdza czy wlasciciel juz odpowiedzial na pytanie suflera - jesli nie, czeka dalej (max ~24s)."""
    call_sid = request.values.get("call_sid", "unknown")
    attempt = int(request.values.get("attempt", 1))

    ctx = CALL_CONTEXT.get(call_sid)
    if not ctx:
        return Response(
            '<?xml version="1.0" encoding="UTF-8"?><Response><Say language="pl-PL">Sesja wygasla.</Say><Hangup/></Response>',
            mimetype="text/xml"
        )

    bot_lang = ctx.get("lang", BOT_LANGUAGES["pl"])
    hint = check_hint_answer(call_sid)

    if hint:
        # Wlasciciel odpowiedzial - bot mowi podpowiedz dalej rozmowcy
        ctx["messages"].append({"role": "assistant", "content": hint})
        audio_url = generate_speech_url(hint, f"hint_{call_sid}.mp3", ctx.get("voice_id"))
        if db_admin:
            db_admin.collection("hints").document(call_sid).delete()
        if audio_url:
            return Response(gather_response_twiml(audio_url, "/handle-speech", bot_lang["twilio"], bot_lang["no_response"]), mimetype="text/xml")

    if attempt >= 6:
        # Uplynelo ~24s bez odpowiedzi - bot kontynuuje sam, uprzejmie
        fallback_text = bot_lang["hint_fallback"]
        ctx["messages"].append({"role": "assistant", "content": fallback_text})
        audio_url = generate_speech_url(fallback_text, f"fallback_{call_sid}.mp3", ctx.get("voice_id"))
        if db_admin:
            db_admin.collection("hints").document(call_sid).delete()
        if audio_url:
            return Response(gather_response_twiml(audio_url, "/handle-speech", bot_lang["twilio"], bot_lang["no_response"]), mimetype="text/xml")

    # Wciaz czekamy - kolejna krotka pauza i ponowne sprawdzenie
    return Response(f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Pause length="4"/>
    <Redirect method="POST">/check-hint?call_sid={call_sid}&amp;attempt={attempt + 1}</Redirect>
</Response>''', mimetype="text/xml")


@app.route("/call-status", methods=["POST"])
def call_status():
    """Twilio wywoluje ten endpoint gdy polaczenie sie konczy - zapisujemy zuzyte minuty i transkrypcje."""
    call_sid = request.form.get("CallSid", "unknown")
    call_status_value = request.form.get("CallStatus", "")
    duration_seconds = int(request.form.get("CallDuration", 0) or 0)
    from_number = request.form.get("From", "")
    to_number = request.form.get("To", "")

    ctx = CALL_CONTEXT.get(call_sid)
    if ctx and call_status_value == "completed":
        owner_uid = ctx.get("owner_uid")
        if owner_uid and duration_seconds > 0:
            minutes = round(duration_seconds / 60, 2)
            add_minutes_used(owner_uid, minutes)
            updated_data = get_user_doc_by_uid(owner_uid)
            maybe_notify_low_usage(owner_uid, updated_data)

        call_type = "outbound" if ctx.get("is_outbound") else "incoming"
        save_call_record(owner_uid, ctx, from_number, to_number, duration_seconds, call_type)

        CALL_CONTEXT.pop(call_sid, None)

    return ("", 204)


@app.route("/outbound-twiml", methods=["GET", "POST"])
def outbound_twiml():
    call_sid = request.values.get("CallSid", "unknown")
    task = request.values.get("task", "Przekaz uprzejmie ze to test systemu EchoLine.")
    owner_uid = request.values.get("uid", "")
    voice_id = request.values.get("voice_id") or ELEVENLABS_VOICE_ID

    owner_data = get_user_doc_by_uid(owner_uid) if owner_uid else None
    bot_lang = get_bot_language(owner_data)

    system_prompt = (
        "Dzwonisz w imieniu uzytkownika EchoLine, zeby zalatwic konkretna sprawe. "
        f"{bot_lang['instruction']} Badz krotki i uprzejmy. Twoje zadanie: " + task
    )
    CALL_CONTEXT[call_sid] = {
        "messages": [{"role": "system", "content": system_prompt}],
        "voice_id": voice_id,
        "owner_uid": owner_uid or None,
        "is_outbound": True,
        "lang": bot_lang,
    }

    greeting = "Dzien dobry, dzwonie w imieniu mojego uzytkownika w nastepujacej sprawie: " + task
    CALL_CONTEXT[call_sid]["messages"].append({"role": "assistant", "content": greeting})

    audio_url = generate_speech_url(greeting, f"outbound_{call_sid}.mp3", voice_id)
    if not audio_url:
        return Response(
            f'<?xml version="1.0" encoding="UTF-8"?><Response><Say language="{bot_lang["twilio"]}">{bot_lang["error"]}</Say></Response>',
            mimetype="text/xml"
        )
    return Response(gather_response_twiml(audio_url, "/handle-speech", bot_lang["twilio"], bot_lang["no_response"]), mimetype="text/xml")


@app.route("/start-outbound-call", methods=["POST"])
def start_outbound_call():
    if not session.get("logged_in"):
        return {"error": "not logged in"}, 401

    uid = session.get("uid", "")
    user_data = get_user_doc_by_uid(uid) or {}

    ok, limit, used, plan = quick_calls_available(user_data)
    if not ok:
        return {"error": f"Wykorzystano limit zlecen 'Zadzwon za mnie' dla planu {plan} ({used}/{limit}). Zmien plan w Cenniku."}, 403

    data = request.get_json()
    to_number = data.get("phone_number")
    task = data.get("task")
    if not to_number or not task:
        return {"error": "brak numeru lub zadania"}, 400

    sid = os.environ.get("TWILIO_ACCOUNT_SID")
    token = os.environ.get("TWILIO_AUTH_TOKEN")
    if not sid or not token:
        return {"error": "Brak skonfigurowanych danych Twilio na serwerze."}, 500

    voice_id = user_data.get("voiceId") or ELEVENLABS_VOICE_ID
    twiml_url = (
        request.url_root + "outbound-twiml?task=" + requests.utils.quote(task) +
        "&uid=" + requests.utils.quote(uid) +
        "&voice_id=" + requests.utils.quote(voice_id)
    )
    status_callback_url = request.url_root + "call-status"

    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Calls.json"
    r = requests.post(url, auth=(sid, token), data={
        "To": to_number,
        "From": TWILIO_FROM_NUMBER,
        "Url": twiml_url,
        "StatusCallback": status_callback_url,
        "StatusCallbackEvent": "completed",
    })

    if r.status_code not in (200, 201):
        try:
            err = r.json().get("message", r.text)
        except Exception:
            err = r.text
        return {"error": err}, 500

    increment_quick_calls(uid)
    updated_data = get_user_doc_by_uid(uid)
    maybe_notify_low_usage(uid, updated_data)
    return {"ok": True, "call_sid": r.json().get("sid")}


if __name__ == "__main__":
    os.makedirs("static", exist_ok=True)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
