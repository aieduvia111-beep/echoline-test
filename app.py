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
</style>
</head>
<body>
<div class="wrap">
  <div class="logo"><span class="logo-dot"></span>EchoLine</div>
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
  <div class="field" style="position:relative;">
    <input type="password" id="fP" placeholder="••••••••" style="padding-right:40px;">
    <button type="button" onclick="togglePw()" style="position:absolute;right:10px;top:50%;transform:translateY(-50%);background:none;border:none;cursor:pointer;padding:4px;display:flex;">
      <svg id="eyeIcon" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#888" stroke-width="1.8"><path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7z"/><circle cx="12" cy="12" r="3"/></svg>
    </button>
  </div>

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
        createdAt: serverTimestamp()
      });
    }
  }

  let mode = 'login';

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
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>EchoLine - panel</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
  *{box-sizing:border-box;margin:0;padding:0;}
  body{font-family:'Inter',sans-serif;background:#fff;color:#111;display:flex;min-height:100vh;}

  /* SIDEBAR */
  .sidebar{width:220px;flex-shrink:0;border-right:1px solid #eee;padding:20px 12px;display:flex;flex-direction:column;}
  .logo{font-size:15px;font-weight:800;padding:8px 8px 20px;letter-spacing:-0.01em;display:flex;align-items:center;gap:8px;}
  .logo-dot{width:10px;height:10px;border-radius:50%;background:linear-gradient(135deg,#7c6aff,#22d3a0);flex-shrink:0;}
  .nav-item{display:flex;align-items:center;gap:10px;padding:9px 10px;border-radius:8px;font-size:13.5px;font-weight:500;color:#555;text-decoration:none;margin-bottom:2px;cursor:pointer;}
  .nav-item:hover{background:#f5f5f5;}
  .nav-item.active{background:#111;color:#fff;}
  .nav-item.active svg{stroke:#fff;}
  .nav-icon{width:17px;height:17px;flex-shrink:0;stroke:#666;fill:none;stroke-width:1.8;}
  .nav-item.active .nav-icon{stroke:#fff;}
  .nav-section-label{font-size:10.5px;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;color:#bbb;padding:16px 10px 6px;}

  /* TOPBAR */
  .main{flex:1;display:flex;flex-direction:column;min-width:0;}
  .topbar{display:flex;align-items:center;justify-content:space-between;padding:16px 32px;border-bottom:1px solid #eee;}
  .topbar h2{font-size:15px;font-weight:600;}
  .topbar-right{display:flex;align-items:center;gap:14px;}
  .avatar{width:30px;height:30px;border-radius:50%;background:linear-gradient(135deg,#7c6aff,#4f3fcf);color:#fff;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:700;flex-shrink:0;}
  a.logout{color:#888;font-size:13px;text-decoration:none;}
  a.logout:hover{text-decoration:underline;}

  .content{padding:32px;max-width:900px;}
  .content h1{font-size:22px;font-weight:800;letter-spacing:-0.01em;margin-bottom:24px;}

  /* ACTION CARDS */
  .cards{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:32px;}
  .action-card{border:1px solid #eee;border-radius:14px;padding:20px;cursor:pointer;transition:border-color .15s;}
  .action-card:hover{border-color:#ccc;}
  .action-card .icon-box{width:100%;height:64px;border-radius:10px;margin-bottom:14px;display:flex;align-items:center;justify-content:center;}
  .action-card .icon-box svg{width:26px;height:26px;fill:none;stroke-width:1.7;}
  .icon-box.purple{background:rgba(124,106,255,0.1);}
  .icon-box.purple svg{stroke:#7c6aff;}
  .icon-box.teal{background:rgba(34,211,160,0.1);}
  .icon-box.teal svg{stroke:#1e9e78;}
  .icon-box.amber{background:rgba(245,166,35,0.12);}
  .icon-box.amber svg{stroke:#c9840f;}
  .action-card h3{font-size:14px;font-weight:700;margin-bottom:4px;}
  .action-card p{font-size:12.5px;color:#888;line-height:1.4;}

  /* CARD (form/table containers) */
  .card{background:#fff;border:1px solid #eee;border-radius:14px;padding:24px;margin-bottom:20px;}
  .card h3{font-size:14px;font-weight:700;margin-bottom:14px;}
  textarea{width:100%;padding:12px;border-radius:9px;border:1px solid #ddd;font-family:inherit;font-size:14px;min-height:90px;}
  button.save{padding:9px 18px;border-radius:9px;border:none;background:#7c6aff;color:#fff;font-weight:600;font-size:13.5px;cursor:pointer;margin-top:10px;transition:background .15s;}
  button.save:hover{background:#6a56ef;}
  table{width:100%;border-collapse:collapse;}
  td,th{padding:10px 6px;border-bottom:1px solid #f0f0f0;text-align:left;font-size:13px;}
  th{color:#999;font-weight:600;text-transform:uppercase;font-size:10.5px;letter-spacing:0.04em;}

  /* RESPONSIVE - TELEFON */
  @media (max-width: 760px) {
    body{flex-direction:column;}
    .sidebar{width:100%;border-right:none;border-bottom:1px solid #eee;flex-direction:row;align-items:center;padding:12px 16px;overflow-x:auto;white-space:nowrap;}
    .logo{padding:0 14px 0 0;}
    .nav-section-label{display:none;}
    .nav-item{flex-shrink:0;}
    .nav-item span.label{display:none;}
    .content{padding:20px;}
    .content h1{font-size:19px;}
    .cards{grid-template-columns:1fr;}
    .topbar{padding:14px 20px;}
    table{font-size:12px;}
    td,th{padding:8px 4px;}
  }
</style>
</head>
<body>

<div class="sidebar">
  <div class="logo"><span class="logo-dot"></span>EchoLine</div>
  <div class="nav-item active">
    <svg class="nav-icon" viewBox="0 0 24 24"><path d="M3 11l9-8 9 8"/><path d="M5 10v10h14V10"/></svg>
    <span class="label">Dashboard</span>
  </div>
  <div class="nav-item">
    <svg class="nav-icon" viewBox="0 0 24 24"><path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6 19.8 19.8 0 0 1-3.1-8.6A2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .3 2 .6 3a2 2 0 0 1-.5 2.1L8 10a16 16 0 0 0 6 6l1.2-1.2a2 2 0 0 1 2.1-.5c1 .3 2 .5 3 .6a2 2 0 0 1 1.7 2z"/></svg>
    <span class="label">Numer telefonu</span>
  </div>
  <div class="nav-item">
    <svg class="nav-icon" viewBox="0 0 24 24"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>
    <span class="label">Mój głos</span>
  </div>
  <div class="nav-item">
    <svg class="nav-icon" viewBox="0 0 24 24"><path d="M21 11.5a8.4 8.4 0 0 1-9 8.5 8.7 8.7 0 0 1-4-1L3 20l1-4a8.4 8.4 0 0 1-1-4 8.4 8.4 0 0 1 9-8.5 8.5 8.5 0 0 1 9 8.5z"/></svg>
    <span class="label">Rozmowy</span>
  </div>
  <div class="nav-section-label">Konto</div>
  <div class="nav-item">
    <svg class="nav-icon" viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 0 1-4 0v-.1a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.5-1H3a2 2 0 0 1 0-4h.1a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.9.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 0 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.9V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 0 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/></svg>
    <span class="label">Ustawienia</span>
  </div>
</div>

<div class="main">
  <div class="topbar">
    <h2>Dashboard</h2>
    <div class="topbar-right">
      <a class="logout" href="/logout">Wyloguj</a>
      <div class="avatar">{{ user_email[0]|upper if user_email else "U" }}</div>
    </div>
  </div>

  <div class="content">
    <h1>Co chcesz dziś zrobić?</h1>

    <div class="cards">
      <div class="action-card">
        <div class="icon-box purple"><svg viewBox="0 0 24 24"><path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6 19.8 19.8 0 0 1-3.1-8.6A2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .3 2 .6 3a2 2 0 0 1-.5 2.1L8 10a16 16 0 0 0 6 6l1.2-1.2a2 2 0 0 1 2.1-.5c1 .3 2 .5 3 .6a2 2 0 0 1 1.7 2z"/></svg></div>
        <h3>Skonfiguruj numer</h3>
        <p>Wybierz kraj i uzyskaj numer telefonu dla swojego asystenta</p>
      </div>
      <div class="action-card">
        <div class="icon-box teal"><svg viewBox="0 0 24 24"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg></div>
        <h3>Sklonuj swój głos</h3>
        <p>Nagraj krótką próbkę, żeby bot mówił Twoim głosem</p>
      </div>
      <div class="action-card">
        <div class="icon-box amber"><svg viewBox="0 0 24 24"><path d="M21 11.5a8.4 8.4 0 0 1-9 8.5 8.7 8.7 0 0 1-4-1L3 20l1-4a8.4 8.4 0 0 1-1-4 8.4 8.4 0 0 1 9-8.5 8.5 8.5 0 0 1 9 8.5z"/></svg></div>
        <h3>Zobacz rozmowy</h3>
        <p>Przeglądaj transkrypcje i podsumowania połączeń</p>
      </div>
    </div>

    <div class="card" id="voice-card">
      <h3>Twój głos</h3>
      <p id="voiceStatus" style="font-size:13px;color:#888;margin-bottom:14px;">Sprawdzam status...</p>

      <div id="waveWrap" style="display:none;align-items:center;gap:12px;margin-bottom:16px;padding:14px 16px;background:#fafafa;border-radius:12px;">
        <div id="recDot" style="width:10px;height:10px;border-radius:50%;background:#e74c3c;flex-shrink:0;animation:recPulse 1.2s infinite;"></div>
        <canvas id="waveCanvas" width="240" height="40" style="flex:1;"></canvas>
        <span id="recTimer" style="font-size:12.5px;color:#888;font-variant-numeric:tabular-nums;flex-shrink:0;">0:00</span>
      </div>

      <div id="processingWrap" style="display:none;align-items:center;gap:10px;margin-bottom:16px;">
        <div class="spinner"></div>
        <span style="font-size:13px;color:#888;">Klonowanie głosu przez AI...</span>
      </div>

      <button class="save" id="recordBtn" onclick="toggleRecording()">Nagraj próbkę głosu</button>
      <p style="font-size:12px;color:#aaa;margin-top:8px;">Nagraj ok. 30-60 sekund swobodnej wypowiedzi, w cichym miejscu.</p>
    </div>

    <div class="card">
      <h3>Instrukcje dla bota</h3>
      <form method="POST" action="/save-instructions">
        <textarea name="instructions">{{ instructions }}</textarea>
        <button class="save" type="submit">Zapisz</button>
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
  </div>
</div>

<style>
  @keyframes recPulse{0%,100%{opacity:1;}50%{opacity:0.25;}}
  .spinner{width:16px;height:16px;border:2px solid #eee;border-top-color:#7c6aff;border-radius:50%;animation:spin 0.7s linear infinite;}
  @keyframes spin{to{transform:rotate(360deg);}}
  .voice-ready{color:#1e8449 !important;}
  .voice-ready-dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:#22d3a0;margin-right:6px;box-shadow:0 0 0 3px rgba(34,211,160,0.15);}
</style>

<script type="module">
  import { initializeApp } from "https://www.gstatic.com/firebasejs/10.13.0/firebase-app.js";
  import { getAuth, onAuthStateChanged } from "https://www.gstatic.com/firebasejs/10.13.0/firebase-auth.js";
  import { getFirestore, doc, getDoc, updateDoc } from "https://www.gstatic.com/firebasejs/10.13.0/firebase-firestore.js";

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
  });

  function setVoiceStatus(ready){
    const statusEl = document.getElementById("voiceStatus");
    const btn = document.getElementById("recordBtn");
    if (ready) {
      statusEl.innerHTML = '<span class="voice-ready-dot"></span>Głos sklonowany i gotowy do użycia';
      statusEl.className = "voice-ready";
      btn.textContent = "Nagraj ponownie";
    } else {
      statusEl.textContent = "Nie masz jeszcze sklonowanego głosu.";
      statusEl.className = "";
      btn.textContent = "Nagraj próbkę głosu";
    }
  }

  let mediaRecorder, chunks = [], recording = false;
  let audioCtx, analyser, dataArray, animId, startTime, timerInterval;

  function drawWave(){
    const canvas = document.getElementById("waveCanvas");
    const ctx = canvas.getContext("2d");
    analyser.getByteFrequencyData(dataArray);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const barCount = 28;
    const step = Math.floor(dataArray.length / barCount);
    for (let i = 0; i < barCount; i++) {
      const v = dataArray[i * step] / 255;
      const h = Math.max(3, v * canvas.height);
      const x = i * (canvas.width / barCount);
      ctx.fillStyle = "#7c6aff";
      ctx.fillRect(x, (canvas.height - h) / 2, (canvas.width / barCount) - 3, h);
    }
    animId = requestAnimationFrame(drawWave);
  }

  window.toggleRecording = async function(){
    const btn = document.getElementById("recordBtn");
    const waveWrap = document.getElementById("waveWrap");
    const processingWrap = document.getElementById("processingWrap");

    if (!recording) {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        const source = audioCtx.createMediaStreamSource(stream);
        analyser = audioCtx.createAnalyser();
        analyser.fftSize = 256;
        dataArray = new Uint8Array(analyser.frequencyBinCount);
        source.connect(analyser);
        drawWave();

        mediaRecorder = new MediaRecorder(stream);
        chunks = [];
        mediaRecorder.ondataavailable = (e) => chunks.push(e.data);
        mediaRecorder.onstop = uploadRecording;
        mediaRecorder.start();
        recording = true;

        waveWrap.style.display = "flex";
        btn.textContent = "Zatrzymaj nagrywanie";

        startTime = Date.now();
        timerInterval = setInterval(() => {
          const s = Math.floor((Date.now() - startTime) / 1000);
          document.getElementById("recTimer").textContent = Math.floor(s/60) + ":" + String(s%60).padStart(2,"0");
        }, 200);
      } catch (e) {
        alert("Nie udalo sie uzyskac dostepu do mikrofonu: " + e.message);
      }
    } else {
      mediaRecorder.stop();
      recording = false;
      cancelAnimationFrame(animId);
      clearInterval(timerInterval);
      waveWrap.style.display = "none";
      processingWrap.style.display = "flex";
      btn.style.display = "none";
    }
  };

  async function uploadRecording(){
    const blob = new Blob(chunks, { type: "audio/webm" });
    const formData = new FormData();
    formData.append("audio", blob, "sample.webm");

    const resp = await fetch("/clone-voice", { method: "POST", body: formData });
    const result = await resp.json();

    const btn = document.getElementById("recordBtn");
    const processingWrap = document.getElementById("processingWrap");
    processingWrap.style.display = "none";
    btn.style.display = "inline-block";

    if (result.voice_id && currentUid) {
      await updateDoc(doc(db, "users", currentUid), { voiceId: result.voice_id });
      setVoiceStatus(true);
    } else {
      document.getElementById("voiceStatus").textContent = "Blad klonowania: " + (result.error || "nieznany blad");
      document.getElementById("voiceStatus").style.color = "#c0392b";
    }
  }
</script>
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
    return render_template_string(
        DASHBOARD_PAGE,
        instructions=bot_instructions["text"],
        calls=FAKE_CALLS,
        user_email=session.get("email", ""),
        user_uid=session.get("uid", ""),
        firebase_config=FIREBASE_CONFIG
    )

@app.route("/save-instructions", methods=["POST"])
def save_instructions():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    bot_instructions["text"] = request.form.get("instructions", "")
    return redirect(url_for("dashboard"))

@app.route("/clone-voice", methods=["POST"])
def clone_voice():
    if not session.get("logged_in"):
        return {"error": "not logged in"}, 401
    if "audio" not in request.files:
        return {"error": "brak pliku audio"}, 400
    audio_file = request.files["audio"]
    uid = session.get("uid", "unknown")

    url = "https://api.elevenlabs.io/v1/voices/add"
    headers = {"xi-api-key": ELEVENLABS_API_KEY}
    files = {"files": (audio_file.filename or "sample.webm", audio_file.stream, audio_file.mimetype)}
    data = {"name": f"echoline_user_{uid}"}

    r = requests.post(url, headers=headers, data=data, files=files)
    if r.status_code == 200:
        voice_id = r.json().get("voice_id")
        return {"voice_id": voice_id}
    return {"error": r.text}, 500

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
