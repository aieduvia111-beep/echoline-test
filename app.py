from flask import Flask, request, Response, session, redirect, url_for, render_template_string
import requests
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-key-zmien-to")

ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")

bot_instructions = {"text": "Umawiaj wizyty i podawaj cennik uslug."}

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
  body{font-family:'Inter',sans-serif;background:#fff;color:#111;display:flex;flex-direction:column;align-items:center;padding:60px 20px;min-height:100vh;}
  .wrap{width:100%;max-width:360px;}
  .logo{text-align:center;font-size:16px;font-weight:800;margin-bottom:36px;letter-spacing:-0.01em;}
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

  button.submit{width:100%;padding:12px;border-radius:9px;border:none;background:#111;color:#fff;font-family:inherit;font-size:14.5px;font-weight:600;cursor:pointer;margin:8px 0 20px;}
  button.submit:hover{background:#333;}

  .switch{text-align:center;font-size:13.5px;color:#888;}
  .switch a{color:#111;font-weight:600;text-decoration:none;cursor:pointer;}
  .switch a:hover{text-decoration:underline;}

  .msg{padding:9px 12px;border-radius:8px;font-size:12.5px;margin-bottom:14px;display:none;}
  .msg.err{background:#fdecec;color:#c0392b;}
  .msg.ok{background:#eaf7ef;color:#1e8449;}

  .name-field{display:none;}
  .name-field.show{display:block;}
</style>
</head>
<body>
<div class="wrap">
  <div class="logo">● EchoLine</div>
  <h1 id="heading">Witaj ponownie</h1>

  <div class="msg err" id="err"></div>
  <div class="msg ok" id="ok"></div>

  <button class="social" onclick="doGoogle()">
    <svg viewBox="0 0 48 48"><path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.8 32.9 29.3 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.9 1.2 8 3.1l5.7-5.7C34.5 6.1 29.5 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.7-.4-3.5z"/><path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.6 16 18.9 13 24 13c3.1 0 5.9 1.2 8 3.1l5.7-5.7C34.5 6.1 29.5 4 24 4c-7.7 0-14.3 4.3-17.7 10.7z"/><path fill="#4CAF50" d="M24 44c5.3 0 10.1-1.8 13.8-4.9l-6.4-5.4C29.3 35.4 26.8 36 24 36c-5.3 0-9.7-3.4-11.3-8.1l-6.6 5.1C9.6 39.6 16.2 44 24 44z"/><path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.1-4 5.5l6.4 5.4C41.8 35.5 44 30.1 44 24c0-1.3-.1-2.7-.4-3.5z"/></svg>
    Kontynuuj z Google
  </button>

  <div class="divider">lub</div>

  <div class="name-field" id="nameField">
    <label>Imię</label>
    <div class="field"><input type="text" id="rN" placeholder="Jak masz na imię"></div>
  </div>

  <label>Email</label>
  <div class="field"><input type="email" id="fE" placeholder="ty@przyklad.pl"></div>

  <div class="row-label">
    <label style="margin-bottom:0;">Hasło</label>
    <a onclick="doReset()" id="forgotLink">Zapomniałem hasła</a>
  </div>
  <div class="field"><input type="password" id="fP" placeholder="••••••••"></div>

  <button class="submit" id="submitBtn" onclick="doLogin()">Zaloguj się</button>

  <div class="switch" id="switchText">
    Nie masz konta? <a onclick="toggleMode()">Zarejestruj się</a>
  </div>
</div>

<script type="module">
  import { initializeApp } from "https://www.gstatic.com/firebasejs/10.13.0/firebase-app.js";
  import {
    getAuth, GoogleAuthProvider, signInWithPopup,
    signInWithEmailAndPassword, createUserWithEmailAndPassword,
    sendPasswordResetEmail, updateProfile
  } from "https://www.gstatic.com/firebasejs/10.13.0/firebase-auth.js";

  const firebaseConfig = {{ firebase_config | tojson }};
  const app = initializeApp(firebaseConfig);
  const auth = getAuth(app);

  let mode = 'login';

  window.toggleMode = function(){
    mode = (mode === 'login') ? 'register' : 'login';
    document.getElementById('heading').textContent = mode === 'login' ? 'Witaj ponownie' : 'Utwórz konto';
    document.getElementById('nameField').classList.toggle('show', mode === 'register');
    document.getElementById('forgotLink').style.visibility = mode === 'register' ? 'hidden' : 'visible';
    document.getElementById('submitBtn').textContent = mode === 'login' ? 'Zaloguj się' : 'Utwórz konto';
    document.getElementById('submitBtn').onclick = mode === 'login' ? doLogin : doReg;
    document.getElementById('switchText').innerHTML = mode === 'login'
      ? 'Nie masz konta? <a onclick="toggleMode()">Zarejestruj się</a>'
      : 'Masz już konto? <a onclick="toggleMode()">Zaloguj się</a>';
    hideMsgs();
  };

  function hideMsgs(){
    document.getElementById('err').style.display='none';
    document.getElementById('ok').style.display='none';
  }
  function showErr(msg){ hideMsgs(); const e=document.getElementById('err'); e.textContent=msg; e.style.display='block'; }
  function showOk(msg){ hideMsgs(); const o=document.getElementById('ok'); o.textContent=msg; o.style.display='block'; }

  function friendlyError(code){
    if(code === 'auth/invalid-credential' || code === 'auth/wrong-password') return 'Nieprawidlowy email lub haslo.';
    if(code === 'auth/user-not-found') return 'Nie znaleziono konta z tym emailem.';
    if(code === 'auth/email-already-in-use') return 'Konto z tym emailem juz istnieje.';
    if(code === 'auth/weak-password') return 'Haslo musi miec min. 6 znakow.';
    if(code === 'auth/invalid-email') return 'Nieprawidlowy adres email.';
    return 'Wystapil blad: ' + code;
  }

  async function finishLogin(user){
    const resp = await fetch("/session-login", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({email: user.email, name: user.displayName})
    });
    if (resp.ok) window.location.href = "/dashboard";
    else showErr("Nie udalo sie zalogowac po stronie serwera.");
  }

  window.doLogin = async function(){
    const email = document.getElementById('fE').value.trim();
    const pass = document.getElementById('fP').value;
    if(!email || !pass){ showErr('Wpisz email i haslo.'); return; }
    try{
      const r = await signInWithEmailAndPassword(auth, email, pass);
      await finishLogin(r.user);
    }catch(e){ showErr(friendlyError(e.code)); }
  };

  window.doReg = async function(){
    const name = document.getElementById('rN').value.trim();
    const email = document.getElementById('fE').value.trim();
    const pass = document.getElementById('fP').value;
    if(!email || !pass){ showErr('Wpisz email i haslo.'); return; }
    if(pass.length < 6){ showErr('Haslo musi miec min. 6 znakow.'); return; }
    try{
      const r = await createUserWithEmailAndPassword(auth, email, pass);
      if(name) await updateProfile(r.user, {displayName: name});
      await finishLogin(r.user);
    }catch(e){ showErr(friendlyError(e.code)); }
  };

  window.doReset = async function(){
    if(mode !== 'login') return;
    const email = document.getElementById('fE').value.trim();
    if(!email){ showErr('Wpisz email powyzej, potem kliknij "Zapomnialem hasla".'); return; }
    try{
      await sendPasswordResetEmail(auth, email);
      showOk('Link do resetu hasla wyslany na ' + email + '.');
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
</script>
</body>
</html>
"""

DASHBOARD_PAGE = """
<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="UTF-8">
<title>EchoLine - panel</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  *{box-sizing:border-box;margin:0;padding:0;}
  body{font-family:'Inter',sans-serif;background:#fafafa;color:#111;padding:40px;}
  .topbar{display:flex;justify-content:space-between;align-items:center;margin-bottom:32px;max-width:800px;}
  h1{font-size:22px;font-weight:700;}
  .user{color:#888;font-size:14px;}
  a.logout{color:#888;font-size:13px;text-decoration:underline;}
  .card{background:#fff;border:1px solid #eee;border-radius:16px;padding:28px;margin-bottom:20px;max-width:800px;box-shadow:0 2px 12px rgba(0,0,0,0.03);}
  .card h3{font-size:15px;font-weight:600;margin-bottom:16px;}
  textarea{width:100%;padding:12px;border-radius:10px;border:1px solid #ddd;font-family:inherit;font-size:14px;min-height:90px;}
  button{padding:10px 20px;border-radius:10px;border:none;background:#111;color:#fff;font-weight:600;font-size:14px;cursor:pointer;margin-top:12px;}
  button:hover{background:#333;}
  table{width:100%;border-collapse:collapse;}
  td,th{padding:10px 6px;border-bottom:1px solid #f0f0f0;text-align:left;font-size:13.5px;}
  th{color:#999;font-weight:600;text-transform:uppercase;font-size:11px;letter-spacing:0.04em;}
</style>
</head>
<body>
<div class="topbar">
  <h1>Panel EchoLine</h1>
  <div>
    <span class="user">{{ user_email }}</span> ·
    <a class="logout" href="/logout">Wyloguj</a>
  </div>
</div>

<div class="card">
  <h3>Instrukcje dla bota</h3>
  <form method="POST" action="/save-instructions">
    <textarea name="instructions">{{ instructions }}</textarea>
    <button type="submit">Zapisz</button>
  </form>
</div>

<div class="card">
  <h3>Ostatnie rozmowy</h3>
  <table>
    <tr><th>Data</th><th>Z kim</th><th>Podsumowanie</th></tr>
    {% for call in calls %}
    <tr><td>{{ call.data }}</td><td>{{ call.z_kim }}</td><td>{{ call.podsumowanie }}</td></tr>
    {% endfor %}
  </table>
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
    return {"ok": True}

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/dashboard")
def dashboard():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    return render_template_string(
        DASHBOARD_PAGE,
        instructions=bot_instructions["text"],
        calls=FAKE_CALLS,
        user_email=session.get("email", "")
    )

@app.route("/save-instructions", methods=["POST"])
def save_instructions():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    bot_instructions["text"] = request.form.get("instructions", "")
    return redirect(url_for("dashboard"))

@app.route("/incoming-call", methods=["POST"])
def incoming_call():
    text = bot_instructions["text"]
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
    headers = {"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"}
    payload = {"text": "Dzien dobry, tu automatyczny asystent EchoLine. To jest test systemu.", "model_id": "eleven_multilingual_v2"}
    r = requests.post(url, json=payload, headers=headers)
    if r.status_code == 200:
        with open("static/powitanie.mp3", "wb") as f:
            f.write(r.content)
        audio_url = request.url_root + "static/powitanie.mp3"
        twiml = f'<?xml version="1.0" encoding="UTF-8"?><Response><Play>{audio_url}</Play></Response>'
    else:
        twiml = '<?xml version="1.0" encoding="UTF-8"?><Response><Say language="pl-PL">Wystapil blad.</Say></Response>'
    return Response(twiml, mimetype="text/xml")

if __name__ == "__main__":
    os.makedirs("static", exist_ok=True)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
