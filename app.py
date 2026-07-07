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
  .bg-particles{position:fixed;inset:0;overflow:hidden;pointer-events:none;z-index:0;}
  .bg-particles span{position:absolute;bottom:-10px;border-radius:50%;background:#7c6aff;opacity:0;animation:floatDust linear infinite;}
  @keyframes floatDust{
    0%{transform:translateY(0) translateX(0);opacity:0;}
    10%{opacity:0.4;}
    90%{opacity:0.4;}
    100%{transform:translateY(-105vh) translateX(30px);opacity:0;}
  }
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
      <i data-lucide="eye" id="eyeIcon" style="width:18px;height:18px;color:#888;"></i>
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
        onboardingDone: false,
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
    <span class="label">Dashboard</span>
  </a>
  <a class="nav-item{{ ' active' if active_page == 'number' else '' }}" href="/numer-telefonu">
    <i data-lucide="phone" class="nav-icon"></i>
    <span class="label">Numer telefonu</span>
  </a>
  <a class="nav-item{{ ' active' if active_page == 'voice' else '' }}" href="/moj-glos">
    <i data-lucide="mic" class="nav-icon"></i>
    <span class="label">Mój głos</span>
  </a>
  <a class="nav-item{{ ' active' if active_page == 'calls' else '' }}" href="/rozmowy">
    <i data-lucide="message-circle" class="nav-icon"></i>
    <span class="label">Rozmowy</span>
  </a>
  <a class="nav-item{{ ' active' if active_page == 'pricing' else '' }}" href="/cennik">
    <i data-lucide="credit-card" class="nav-icon"></i>
    <span class="label">Cennik</span>
  </a>
  <div class="nav-section-label">Konto</div>
  <a class="nav-item{{ ' active' if active_page == 'settings' else '' }}" href="/ustawienia">
    <i data-lucide="settings" class="nav-icon"></i>
    <span class="label">Ustawienia</span>
  </a>

  <div class="sidebar-widget">
    <div class="sw-title">Twój asystent AI<br>24/7 gotowy do rozmów</div>
    <div class="sw-orbit"><div class="sw-ring"></div><div class="sw-sphere"></div></div>
    <a class="sw-link" href="#">Zobacz statystyki →</a>
  </div>
</div>

<div class="main">
  <div class="topbar">
    <h2 class="mobile-title">Dashboard</h2>
    <div class="bell"><i data-lucide="bell"></i><div class="bell-dot"></div></div>
    <a class="logout" href="/logout"><i data-lucide="log-out" class="logout-icon"></i><span class="logout-text">Wyloguj</span></a>
    <div class="avatar">{{ user_email[0]|upper if user_email else "U" }}</div>
  </div>

  <div class="content">

    <div class="hero rise">
      <div>
        <div class="eyebrow">WITAJ PONOWNIE</div>
        <h1>Cześć, {{ user_name or "tam" }}</h1>
        <p>Oto co dzieje się z Twoim asystentem</p>
      </div>
      <div class="chart-box">
        <div class="chart-box-top"><span class="lbl">Rozmowy w tym tygodniu</span><span class="val">{{ calls|length }}</span></div>
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
        <div style="display:flex;justify-content:space-between;font-size:10.5px;color:#aaa;margin-top:2px;">
          <span>Pon</span><span>Wt</span><span>Śr</span><span>Czw</span><span>Pt</span><span>Sob</span><span>Ndz</span>
        </div>
      </div>
    </div>

    <div class="tabs rise2">
      <div class="tabbtn active" id="tab-assistant" onclick="showTab('assistant')">
        <div class="ic"><svg viewBox="0 0 24 24"><path d="M12 8V4H8"/><rect width="16" height="12" x="4" y="8" rx="2"/><path d="M2 14h2"/><path d="M20 14h2"/><path d="M15 13v2"/><path d="M9 13v2"/></svg></div>
        <div class="txt"><b>Mój asystent</b><small>Bot odbiera połączenia przychodzące</small></div>
      </div>
      <div class="tabbtn" id="tab-quickcall" onclick="showTab('quickcall')">
        <div class="ic"><svg viewBox="0 0 24 24"><path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6 19.8 19.8 0 0 1-3.1-8.6A2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .3 2 .6 3a2 2 0 0 1-.5 2.1L8 10a16 16 0 0 0 6 6l1.2-1.2a2 2 0 0 1 2.1-.5c1 .3 2 .5 3 .6a2 2 0 0 1 1.7 2z"/></svg></div>
        <div class="txt"><b>Zadzwoń za mnie</b><small>Jednorazowe zlecenie rozmowy</small></div>
      </div>
    </div>

    <div id="section-assistant">
      <div class="cards rise3">
        <div class="action-card" onclick="location.href='/numer-telefonu';">
          <div class="glow-icon glow-purple"><i data-lucide="phone"></i></div>
          <h3>Skonfiguruj numer <i data-lucide="chevron-right"></i></h3>
          <p>Wybierz kraj i uzyskaj swój numer telefonu</p>
        </div>
        <div class="action-card" onclick="location.href='/moj-glos';">
          <div class="glow-icon glow-blue"><i data-lucide="mic"></i></div>
          <h3>Sklonuj swój głos <i data-lucide="chevron-right"></i></h3>
          <p>Nagraj próbkę, aby bot mówił Twoim głosem</p>
        </div>
        <div class="action-card" onclick="location.href='/rozmowy';">
          <div class="glow-icon glow-pink"><i data-lucide="message-circle"></i></div>
          <h3>Zobacz rozmowy <i data-lucide="chevron-right"></i></h3>
          <p>Przeglądaj transkrypcje i historię połączeń</p>
        </div>
      </div>

      <div class="grid2 rise4">
        <div class="card" id="voice-card">
          <div class="card-head"><h3><svg viewBox="0 0 24 24"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>Status głosu</h3></div>
          <p id="voiceStatus" style="font-size:13px;color:#888;margin-bottom:16px;">Sprawdzam status...</p>
          <button class="save-inline" onclick="location.href='/moj-glos';">Zarządzaj głosem</button>
        </div>

        <div class="card">
          <div class="card-head"><h3><svg viewBox="0 0 24 24"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4Z"/></svg>Profil asystenta</h3></div>

          <div class="profile-field">
            <div style="flex:1;">
              <div class="pf-label">Nazwa firmy / kim jest bot</div>
              <div class="pf-value" data-field="companyName">{{ profile.companyName or "Nie ustawiono" }}</div>
              <textarea data-input="companyName">{{ profile.companyName or "" }}</textarea>
              <button class="pf-save" data-savebtn="companyName" onclick="saveField('companyName')">Zapisz</button>
            </div>
            <button class="pf-edit" onclick="editField('companyName')"><i data-lucide="pencil"></i></button>
          </div>

          <div class="profile-field">
            <div style="flex:1;">
              <div class="pf-label">Cennik i oferta</div>
              <div class="pf-value" data-field="pricing">{{ profile.pricing or "Nie ustawiono" }}</div>
              <textarea data-input="pricing">{{ profile.pricing or "" }}</textarea>
              <button class="pf-save" data-savebtn="pricing" onclick="saveField('pricing')">Zapisz</button>
            </div>
            <button class="pf-edit" onclick="editField('pricing')"><i data-lucide="pencil"></i></button>
          </div>

          <div class="profile-field">
            <div style="flex:1;">
              <div class="pf-label">Godziny pracy</div>
              <div class="pf-value" data-field="hours">{{ profile.hours or "Nie ustawiono" }}</div>
              <textarea data-input="hours">{{ profile.hours or "" }}</textarea>
              <button class="pf-save" data-savebtn="hours" onclick="saveField('hours')">Zapisz</button>
            </div>
            <button class="pf-edit" onclick="editField('hours')"><i data-lucide="pencil"></i></button>
          </div>

          <div class="profile-field">
            <div style="flex:1;">
              <div class="pf-label">Zasady i ograniczenia</div>
              <div class="pf-value" data-field="rules">{{ profile.rules or "Nie ustawiono" }}</div>
              <textarea data-input="rules">{{ profile.rules or "" }}</textarea>
              <button class="pf-save" data-savebtn="rules" onclick="saveField('rules')">Zapisz</button>
            </div>
            <button class="pf-edit" onclick="editField('rules')"><i data-lucide="pencil"></i></button>
          </div>
        </div>
      </div>

      <div class="card" id="calls-card">
        <div class="card-head">
          <h3><svg viewBox="0 0 24 24"><path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z"/></svg>Ostatnie rozmowy</h3>
          <a href="#">Zobacz wszystkie →</a>
        </div>
        <div style="overflow-x:auto;">
        <table>
          <tr><th>Data</th><th>Z kim</th><th>Podsumowanie</th><th>Status</th></tr>
          {% for call in calls %}
          <tr class="datarow"><td>{{ call.data }}</td><td>{{ call.z_kim }}</td><td>{{ call.podsumowanie }}</td><td><span class="tag ok">Zakończona</span></td></tr>
          {% endfor %}
        </table>
        </div>
      </div>
    </div>

    <div id="section-quickcall" style="display:none;">
      <div class="card call-wrap rise3">
        <div class="card-head"><h3>Co mam załatwić?</h3></div>
        <textarea id="taskInput" placeholder="np. Zadzwoń do dentysty i przełóż wizytę na przyszły tydzień"></textarea>
        <label style="font-size:12.5px;font-weight:600;color:#555;display:block;margin-bottom:6px;">Numer telefonu docelowego</label>
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
          <input id="phoneInput" type="text" placeholder="np. 601 234 567" style="flex:1;margin-bottom:0;">
        </div>
        <button class="call-btn" onclick="quickCall()">Zadzwoń teraz</button>
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
    if(!task || !phoneRaw){ status.textContent = 'Wpisz zadanie i numer telefonu.'; status.style.color = '#c0392b'; return; }

    // Jesli uzytkownik sam wpisal numer z + na poczatku, uzyj go bez zmian; inaczej dolacz wybrany kod kraju
    const phone = phoneRaw.startsWith('+') ? phoneRaw : countryCode + phoneRaw.replace(/^0+/, '');

    status.textContent = 'Dzwonie...';
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

  onAuthStateChanged(auth, async (user) => {
    if (!user) return;
    currentUid = user.uid;
    const snap = await getDoc(doc(db, "users", user.uid));
    const data = snap.exists() ? snap.data() : {};
    setVoiceStatus(!!data.voiceId);

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

  function setVoiceStatus(ready){
    const statusEl = document.getElementById("voiceStatus");
    if (ready) {
      statusEl.innerHTML = '<span class="voice-ready-dot"></span>Głos sklonowany i gotowy do użycia';
      statusEl.className = "voice-ready";
    } else {
      statusEl.textContent = "Nie masz jeszcze sklonowanego głosu.";
      statusEl.className = "";
    }
  }
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
  .center{flex:1;padding:32px 36px;min-width:0;}
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
  .rightcol{width:290px;flex-shrink:0;padding:32px 24px 32px 0;display:flex;flex-direction:column;gap:16px;}
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
    <span class="label">Dashboard</span>
  </a>
  <a class="nav-item{{ ' active' if active_page == 'number' else '' }}" href="/numer-telefonu">
    <i data-lucide="phone" class="nav-icon"></i>
    <span class="label">Numer telefonu</span>
  </a>
  <a class="nav-item{{ ' active' if active_page == 'voice' else '' }}" href="/moj-glos">
    <i data-lucide="mic" class="nav-icon"></i>
    <span class="label">Mój głos</span>
  </a>
  <a class="nav-item{{ ' active' if active_page == 'calls' else '' }}" href="/rozmowy">
    <i data-lucide="message-circle" class="nav-icon"></i>
    <span class="label">Rozmowy</span>
  </a>
  <a class="nav-item{{ ' active' if active_page == 'pricing' else '' }}" href="/cennik">
    <i data-lucide="credit-card" class="nav-icon"></i>
    <span class="label">Cennik</span>
  </a>
  <div class="nav-section-label">Konto</div>
  <a class="nav-item{{ ' active' if active_page == 'settings' else '' }}" href="/ustawienia">
    <i data-lucide="settings" class="nav-icon"></i>
    <span class="label">Ustawienia</span>
  </a>

  <div class="sidebar-widget">
    <div class="sw-title">Twój asystent AI<br>24/7 gotowy do rozmów</div>
    <div class="sw-orbit"><div class="sw-ring"></div><div class="sw-sphere"></div></div>
    <a class="sw-link" href="/dashboard">Zobacz statystyki →</a>
  </div>
</div>

<div class="main">
  <div class="center rise">
    <div class="center-head">
      <div>
        <h1>Sklonuj swój głos</h1>
        <p>Nagraj próbkę swojego głosu, a AI stworzy jego cyfrową kopię.</p>
      </div>
      <button class="howto-btn"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><path d="M9.1 9a3 3 0 0 1 5.8 1c0 2-3 2-3 4"/><line x1="12" y1="17" x2="12" y2="17"/></svg>Jak to działa?</button>
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
    <p class="record-hint">Zalecamy nagrać 1-2 minuty czystego mówionego tekstu.</p>

    <div class="privacy-bar">
      <svg viewBox="0 0 24 24"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
      Twoje nagrania są prywatne i szyfrowane end-to-end.
    </div>
  </div>

  <div class="rightcol rise">
    <div class="panel-card">
      <h4><i data-lucide="lightbulb"></i>Wskazówki</h4>
      <div class="tip done"><svg viewBox="0 0 24 24" fill="none" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M9 12l2 2 4-4"/></svg>Mów w cichym otoczeniu</div>
      <div class="tip done"><svg viewBox="0 0 24 24" fill="none" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M9 12l2 2 4-4"/></svg>Używaj naturalnego tempa</div>
      <div class="tip done"><svg viewBox="0 0 24 24" fill="none" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M9 12l2 2 4-4"/></svg>Rób krótkie przerwy</div>
      <div class="tip pending"><svg viewBox="0 0 24 24" fill="none" stroke-width="1.8"><circle cx="12" cy="12" r="9"/></svg>Unikaj szumów i echa</div>
    </div>

    <div class="panel-card">
      <h4><i data-lucide="list-checks"></i>Postęp klonowania</h4>
      <div class="step-row active" id="step1">
        <div class="step-num">1</div>
        <div><div class="step-title">Nagrywanie próbki</div><div class="step-sub">Zarejestruj swój głos</div></div>
      </div>
      <div class="step-row" id="step2">
        <div class="step-num">2</div>
        <div><div class="step-title">Przetwarzanie przez AI</div><div class="step-sub">Analiza cech głosu</div></div>
      </div>
      <div class="step-row" id="step3">
        <div class="step-num">3</div>
        <div><div class="step-title">Głos gotowy</div><div class="step-sub">Gotowy do użycia</div></div>
      </div>
    </div>

    <div class="panel-card">
      <h4><i data-lucide="audio-lines"></i>Twoje głosy</h4>
      <div id="voicesList">
        <div class="empty-voices">Nie masz jeszcze żadnego głosu.</div>
      </div>
      <button class="add-voice-btn" onclick="document.getElementById('recordBtn').scrollIntoView({behavior:'smooth',block:'center'});"><svg viewBox="0 0 24 24"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>Sklonuj nowy głos</button>
    </div>

    <div class="panel-card">
      <h4><i data-lucide="library"></i>Biblioteka głosów</h4>
      <p style="font-size:11.5px;color:#999;margin-bottom:10px;">Nie chcesz nagrywać własnego głosu? Wybierz gotowy.</p>
      <select id="libLangSelect" onchange="loadVoiceLibrary()" style="width:100%;padding:8px 10px;border-radius:8px;border:1px solid #ddd;font-size:12.5px;margin-bottom:10px;font-family:inherit;">
        <option value="pl">Polski</option>
        <option value="en">Angielski</option>
        <option value="de">Niemiecki</option>
        <option value="es">Hiszpański</option>
        <option value="fr">Francuski</option>
        <option value="it">Włoski</option>
      </select>
      <div id="libraryList">
        <div class="empty-voices">Ładowanie głosów...</div>
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

  function setVoiceStatus(ready){
    const statusRow = document.getElementById("statusRow");
    const title = document.getElementById("statusTitle");
    const sub = document.getElementById("statusSub");
    const btnText = document.getElementById("recordBtnText");
    const voicesList = document.getElementById("voicesList");

    if (ready) {
      statusRow.classList.add("voice-ready");
      title.textContent = "Głos gotowy";
      sub.textContent = "Twój cyfrowy głos jest aktywny i gotowy do użycia.";
      btnText.textContent = "Nagraj ponownie";
      setSteps(3);
      voicesList.innerHTML = `
        <div class="voice-item">
          <div class="play-btn" id="playBtn" onclick="testVoice()"><svg viewBox="0 0 24 24"><polygon points="6 3 20 12 6 21 6 3"/></svg></div>
          <div style="flex:1;">
            <div class="voice-item-name">Twój głos <span class="voice-tag">Aktywny</span></div>
            <div class="voice-item-date" id="playHint">Kliknij, aby odsłuchać próbkę</div>
          </div>
        </div>`;
    } else {
      statusRow.classList.remove("voice-ready");
      title.textContent = "Gotowy do nagrywania";
      sub.textContent = "Wypowiedz tekst wyraźnie i naturalnie.";
      btnText.textContent = "Nagraj";
      setSteps(1);
      voicesList.innerHTML = `<div class="empty-voices">Nie masz jeszcze żadnego głosu.</div>`;
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

        btnText.textContent = "Zatrzymaj nagrywanie";
        title.textContent = "Nagrywanie...";
        sub.textContent = "Mów teraz, kliknij ponownie aby zakończyć.";
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
      title.textContent = "Przetwarzanie";
      sub.textContent = "Analizujemy Twój głos...";
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
      document.getElementById("statusTitle").textContent = "Błąd klonowania";
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
  .center{flex:1;padding:32px 36px;min-width:0;}
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
  .rightcol{width:290px;flex-shrink:0;padding:32px 24px 32px 0;display:flex;flex-direction:column;gap:16px;}
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
    <span class="label">Dashboard</span>
  </a>
  <a class="nav-item{{ ' active' if active_page == 'number' else '' }}" href="/numer-telefonu">
    <i data-lucide="phone" class="nav-icon"></i>
    <span class="label">Numer telefonu</span>
  </a>
  <a class="nav-item{{ ' active' if active_page == 'voice' else '' }}" href="/moj-glos">
    <i data-lucide="mic" class="nav-icon"></i>
    <span class="label">Mój głos</span>
  </a>
  <a class="nav-item{{ ' active' if active_page == 'calls' else '' }}" href="/rozmowy">
    <i data-lucide="message-circle" class="nav-icon"></i>
    <span class="label">Rozmowy</span>
  </a>
  <a class="nav-item{{ ' active' if active_page == 'pricing' else '' }}" href="/cennik">
    <i data-lucide="credit-card" class="nav-icon"></i>
    <span class="label">Cennik</span>
  </a>
  <div class="nav-section-label">Konto</div>
  <a class="nav-item{{ ' active' if active_page == 'settings' else '' }}" href="/ustawienia">
    <i data-lucide="settings" class="nav-icon"></i>
    <span class="label">Ustawienia</span>
  </a>

  <div class="sidebar-widget">
    <div class="sw-title">Twój asystent AI<br>24/7 gotowy do rozmów</div>
    <div class="sw-orbit"><div class="sw-ring"></div><div class="sw-sphere"></div></div>
    <a class="sw-link" href="/dashboard">Zobacz statystyki →</a>
  </div>
</div>

<div class="main">
  <div class="center rise">
    <div class="center-head">
      <h1>Skonfiguruj numer telefonu</h1>
      <p>Wybierz kraj i uzyskaj własny numer dla swojego asystenta.</p>
    </div>

    <div class="step-label"><i data-lucide="globe"></i>1. Wybierz kraj</div>
    <div class="country-row" id="countryRow">
      <div class="country-card selected" data-country="PL" data-name="Polska" onclick="selectCountry(this)">
        <div class="country-flag">🇵🇱</div>
        <div><div class="country-name">Polska</div><div class="country-code">+48</div></div>
        <div class="selected-check"><svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg></div>
      </div>
      <div class="country-card" data-country="US" data-name="USA" onclick="selectCountry(this)">
        <div class="country-flag">🇺🇸</div>
        <div><div class="country-name">USA</div><div class="country-code">+1</div></div>
        <div class="selected-check"><svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg></div>
      </div>
      <div class="country-card" data-country="DE" data-name="Niemcy" onclick="selectCountry(this)">
        <div class="country-flag">🇩🇪</div>
        <div><div class="country-name">Niemcy</div><div class="country-code">+49</div></div>
        <div class="selected-check"><svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg></div>
      </div>
      <div class="country-card" data-country="GB" data-name="Wielka Brytania" onclick="selectCountry(this)">
        <div class="country-flag">🇬🇧</div>
        <div><div class="country-name">Wielka Brytania</div><div class="country-code">+44</div></div>
        <div class="selected-check"><svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg></div>
      </div>
    </div>

    <div class="step-label"><i data-lucide="search"></i>2. Znajdź dostępne numery</div>
    <div id="searchError"></div>
    <button class="search-btn" id="searchBtn" onclick="searchNumbers()">
      <i data-lucide="sparkles"></i>Wyszukaj dostępne numery
    </button>

    <div id="searchLoading"><div class="spinner"></div>Szukamy dostępnych numerów...</div>

    <div id="resultsSection">
      <div class="step-label"><i data-lucide="phone-call"></i>3. Wybierz swój numer</div>
      <div id="numbersList"></div>

      <div id="buyError"></div>
      <button class="activate-btn" id="activateBtn" disabled onclick="activateNumber()">
        Aktywuj ten numer <i data-lucide="arrow-right"></i>
      </button>
    </div>

    <div class="privacy-bar">
      <i data-lucide="lock"></i>
      <div>
        <b>Twój numer jest w pełni zarządzany i zabezpieczony</b>
        <span>Szyfrowanie end-to-end · Ochrona prywatności · Zgodność z RODO</span>
      </div>
    </div>
  </div>

  <div class="rightcol rise">
    <div class="panel-card">
      <h4><i data-lucide="lightbulb"></i>Wskazówki</h4>
      <div class="tip"><svg viewBox="0 0 24 24" fill="none" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M9 12l2 2 4-4"/></svg>Wybierz kraj Twoich klientów</div>
      <div class="tip"><svg viewBox="0 0 24 24" fill="none" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M9 12l2 2 4-4"/></svg>Numer możesz zmienić później</div>
      <div class="tip"><svg viewBox="0 0 24 24" fill="none" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M9 12l2 2 4-4"/></svg>Aktywacja zajmuje kilka sekund</div>
    </div>

    <div class="panel-card">
      <h4><i data-lucide="list-checks"></i>Postęp konfiguracji</h4>
      <div class="step-row active" id="step1">
        <div class="step-num">1</div>
        <div><div class="step-title">Wybierz kraj</div><div class="step-sub">Wybierz kraj dla swojego numeru</div></div>
      </div>
      <div class="step-row" id="step2">
        <div class="step-num">2</div>
        <div><div class="step-title">Wyszukaj numery</div><div class="step-sub">Znajdź i wybierz dostępny numer</div></div>
      </div>
      <div class="step-row" id="step3">
        <div class="step-num">3</div>
        <div><div class="step-title">Aktywuj numer</div><div class="step-sub">Aktywuj numer dla swojego bota</div></div>
      </div>
    </div>

    <div class="panel-card">
      <h4><i data-lucide="phone"></i>Twój numer</h4>
      <div id="myNumberBox">
        <div class="empty-number">
          <div class="empty-icon"><svg viewBox="0 0 24 24"><path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6 19.8 19.8 0 0 1-3.1-8.6A2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .3 2 .6 3a2 2 0 0 1-.5 2.1L8 10a16 16 0 0 0 6 6l1.2-1.2a2 2 0 0 1 2.1-.5c1 .3 2 .5 3 .6a2 2 0 0 1 1.7 2z"/></svg></div>
          <b>Nie masz jeszcze numeru</b>
          <p>Skonfiguruj swój pierwszy numer, aby Twój asystent mógł odbierać połączenia.</p>
        </div>
      </div>
    </div>
  </div>
</div>

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

  onAuthStateChanged(auth, async (user) => {
    if (!user) return;
    currentUid = user.uid;
    const snap = await getDoc(doc(db, "users", user.uid));
    const data = snap.exists() ? snap.data() : {};
    if (data.phoneNumber) renderMyNumber(data.phoneNumber, data.phoneNumberDate || "");
  });

  function renderMyNumber(phoneNumber, date){
    document.getElementById("myNumberBox").innerHTML = `
      <span class="active-number-tag">Aktywny</span>
      <div class="active-number-phone">${phoneNumber}</div>
      <div class="active-number-date">Aktywowano: ${date || "przed chwila"}</div>
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
        errorBox.textContent = result.error || "Nie udalo sie wyszukac numerow.";
        errorBox.style.display = "block";
        return;
      }

      const numbers = result.numbers || [];
      if (numbers.length === 0) {
        errorBox.textContent = "Brak dostepnych numerow dla tego kraju. Sprobuj inny kraj.";
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
      errorBox.textContent = "Blad polaczenia: " + e.message;
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
    btn.textContent = "Aktywowanie...";

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
        btn.innerHTML = 'Aktywuj ten numer <i data-lucide="arrow-right"></i>';
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
      btn.innerHTML = 'Aktywuj ten numer <i data-lucide="arrow-right"></i>';
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
    <span class="label">Dashboard</span>
  </a>
  <a class="nav-item{{ ' active' if active_page == 'number' else '' }}" href="/numer-telefonu">
    <i data-lucide="phone" class="nav-icon"></i>
    <span class="label">Numer telefonu</span>
  </a>
  <a class="nav-item{{ ' active' if active_page == 'voice' else '' }}" href="/moj-glos">
    <i data-lucide="mic" class="nav-icon"></i>
    <span class="label">Mój głos</span>
  </a>
  <a class="nav-item{{ ' active' if active_page == 'calls' else '' }}" href="/rozmowy">
    <i data-lucide="message-circle" class="nav-icon"></i>
    <span class="label">Rozmowy</span>
  </a>
  <a class="nav-item{{ ' active' if active_page == 'pricing' else '' }}" href="/cennik">
    <i data-lucide="credit-card" class="nav-icon"></i>
    <span class="label">Cennik</span>
  </a>
  <div class="nav-section-label">Konto</div>
  <a class="nav-item{{ ' active' if active_page == 'settings' else '' }}" href="/ustawienia">
    <i data-lucide="settings" class="nav-icon"></i>
    <span class="label">Ustawienia</span>
  </a>

  <div class="sidebar-widget">
    <div class="sw-title">Twój asystent AI<br>24/7 gotowy do rozmów</div>
    <div class="sw-orbit"><div class="sw-ring"></div><div class="sw-sphere"></div></div>
    <a class="sw-link" href="/dashboard">Zobacz statystyki →</a>
  </div>
</div>

<div class="main rise">
  <div class="hero-glow"></div>
  <div class="center-head">
    <h1>Wybierz plan dla siebie</h1>
    <p>Zacznij mały, płać za rozmowy. Bez ukrytych opłat.</p>
  </div>

  <div class="toggle-wrap rise2">
    <div class="toggle">
      <button class="active" id="toggle-monthly" onclick="setBilling('monthly')">Miesięcznie</button>
      <button id="toggle-yearly" onclick="setBilling('yearly')">Rocznie <span class="save-badge">-20%</span></button>
    </div>
  </div>

  <div id="actionMsg"></div>

  <div class="plans rise3">
    <div class="plan-card">
      <div class="plan-name">Start</div>
      <div class="plan-price"><span class="price-val" data-monthly="149" data-yearly="119">149 zł</span><span>/mies.</span></div>
      <div class="plan-desc">Dla jednoosobowych działalności testujących pierwszy raz</div>
      <ul class="plan-features">
        <li><svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg>1 numer telefonu</li>
        <li><svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg>100 minut rozmów miesięcznie</li>
        <li><svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg>1 sklonowany głos</li>
        <li><svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg>Podstawowy profil asystenta</li>
        <li><svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg>5 zleceń "Zadzwoń za mnie"/mies.</li>
      </ul>
      <button class="plan-btn outline" onclick="choosePlan('start')">Wybierz Start</button>
    </div>

    <div class="plan-card featured">
      <div class="plan-badge">NAJPOPULARNIEJSZY</div>
      <div class="plan-name">Pro</div>
      <div class="plan-price"><span class="price-val" data-monthly="399" data-yearly="319">399 zł</span><span>/mies.</span></div>
      <div class="plan-desc">Dla firm gotowych przekazać telefon botowi na stałe</div>
      <ul class="plan-features">
        <li><svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg>1 numer telefonu</li>
        <li><svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg>400 minut rozmów miesięcznie</li>
        <li><svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg>Nielimitowane zmiany głosu</li>
        <li><svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg>Sufler w czasie rzeczywistym</li>
        <li><svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg>30 zleceń "Zadzwoń za mnie"/mies.</li>
        <li><svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg>Priorytetowe wsparcie</li>
      </ul>
      <button class="plan-btn filled" onclick="choosePlan('pro')">Wybierz Pro</button>
    </div>

    <div class="plan-card">
      <div class="plan-name">Firma</div>
      <div class="plan-price"><span class="price-val" data-monthly="899" data-yearly="719">899 zł</span><span>/mies.</span></div>
      <div class="plan-desc">Dla zespołów z wieloma liniami i większym wolumenem</div>
      <ul class="plan-features">
        <li><svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg>Do 5 numerów telefonu</li>
        <li><svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg>1000+ minut rozmów</li>
        <li><svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg>Wszystko z planu Pro</li>
        <li><svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg>Eksport historii rozmów</li>
        <li><svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg>Opiekun wdrożenia</li>
      </ul>
      <button class="plan-btn outline" onclick="choosePlan('firma')">Wybierz Firmę</button>
    </div>
  </div>

  <div class="trust-bar">
    <span><svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg>Bez zobowiązań</span>
    <span><svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg>Anuluj w każdej chwili</span>
    <span><svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg>Płatność przez Stripe</span>
  </div>

  <div class="faq">
    <h3>Najczęstsze pytania</h3>
    <details class="faq-item">
      <summary>Co się stanie, jak przekroczę limit minut?</summary>
      <p>Dostaniesz powiadomienie zanim to nastąpi. Możesz dokupić dodatkowe minuty albo przejść na wyższy plan w dowolnym momencie.</p>
    </details>
    <details class="faq-item">
      <summary>Czy mogę zmienić plan później?</summary>
      <p>Tak, w dowolnym momencie możesz przejść na wyższy lub niższy plan z panelu ustawień.</p>
    </details>
    <details class="faq-item">
      <summary>Czy muszę mieć numer telefonu przed zakupem planu?</summary>
      <p>Nie - najpierw wybierasz plan, a numer konfigurujesz od razu potem w zakładce "Numer telefonu".</p>
    </details>
  </div>
</div>

<script>
  let billing = 'monthly';

  const PAYMENT_LINKS = {
    start: 'https://buy.stripe.com/test_dRm5kCbHobRp46D3xncV200',
    pro: 'https://buy.stripe.com/test_fZu14mdPw7B9gTpgk9cV201',
    firma: 'https://buy.stripe.com/test_4gMeVc6n4aNlcD9c3TcV202'
  };

  function setBilling(mode){
    billing = mode;
    document.getElementById('toggle-monthly').classList.toggle('active', mode === 'monthly');
    document.getElementById('toggle-yearly').classList.toggle('active', mode === 'yearly');
    document.querySelectorAll('.price-val').forEach(el => {
      const val = mode === 'monthly' ? el.dataset.monthly : el.dataset.yearly;
      el.textContent = val + ' zł';
    });
  }

  function choosePlan(plan){
    const link = PAYMENT_LINKS[plan];
    const msg = document.getElementById('actionMsg');
    if (!link) {
      msg.style.display = 'block';
      msg.textContent = 'Ten plan wymaga kontaktu - napisz do nas.';
      return;
    }
    msg.style.display = 'block';
    msg.textContent = 'Przekierowuję do bezpiecznej płatności Stripe...';
    window.location.href = link;
  }
</script>

<script type="module">
  import { initializeApp } from "https://www.gstatic.com/firebasejs/10.13.0/firebase-app.js";
  import { getAuth, onAuthStateChanged } from "https://www.gstatic.com/firebasejs/10.13.0/firebase-auth.js";
  import { getFirestore, doc, updateDoc } from "https://www.gstatic.com/firebasejs/10.13.0/firebase-firestore.js";

  const firebaseConfig = {{ firebase_config | tojson }};
  const app = initializeApp(firebaseConfig);
  const auth = getAuth(app);
  const db = getFirestore(app);

  // Obsluga powrotu po udanej platnosci Stripe (?payment=success&plan=pro)
  const params = new URLSearchParams(window.location.search);
  if (params.get('payment') === 'success') {
    const plan = params.get('plan') || 'start';
    onAuthStateChanged(auth, async (user) => {
      if (!user) return;
      await updateDoc(doc(db, "users", user.uid), { plan: plan });
      const msg = document.getElementById('actionMsg');
      msg.style.display = 'block';
      msg.style.background = '#e8f8f0';
      msg.style.color = '#1e9e63';
      msg.textContent = 'Platnosc zakonczona sukcesem! Twoj plan (' + plan + ') zostal aktywowany.';
      // Usun parametry z adresu, zeby nie aktywowac ponownie przy odswiezeniu
      window.history.replaceState({}, document.title, '/cennik');
    });
  } else if (params.get('payment') === 'cancel') {
    const msg = document.getElementById('actionMsg');
    msg.style.display = 'block';
    msg.textContent = 'Platnosc anulowana. Mozesz sprobowac ponownie w dowolnym momencie.';
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
    <span class="label">Dashboard</span>
  </a>
  <a class="nav-item{{ ' active' if active_page == 'number' else '' }}" href="/numer-telefonu">
    <i data-lucide="phone" class="nav-icon"></i>
    <span class="label">Numer telefonu</span>
  </a>
  <a class="nav-item{{ ' active' if active_page == 'voice' else '' }}" href="/moj-glos">
    <i data-lucide="mic" class="nav-icon"></i>
    <span class="label">Mój głos</span>
  </a>
  <a class="nav-item{{ ' active' if active_page == 'calls' else '' }}" href="/rozmowy">
    <i data-lucide="message-circle" class="nav-icon"></i>
    <span class="label">Rozmowy</span>
  </a>
  <a class="nav-item{{ ' active' if active_page == 'pricing' else '' }}" href="/cennik">
    <i data-lucide="credit-card" class="nav-icon"></i>
    <span class="label">Cennik</span>
  </a>
  <div class="nav-section-label">Konto</div>
  <a class="nav-item{{ ' active' if active_page == 'settings' else '' }}" href="/ustawienia">
    <i data-lucide="settings" class="nav-icon"></i>
    <span class="label">Ustawienia</span>
  </a>

  <div class="sidebar-widget">
    <div class="sw-title">Twój asystent AI<br>24/7 gotowy do rozmów</div>
    <div class="sw-orbit"><div class="sw-ring"></div><div class="sw-sphere"></div></div>
    <a class="sw-link" href="/dashboard">Zobacz statystyki →</a>
  </div>
</div>

<div class="main rise">
  <div class="hero-glow"></div>
  <div class="head">
    <div>
      <h1>Rozmowy</h1>
      <p>Historia i transkrypcje wszystkich połączeń Twojego asystenta.</p>
    </div>
  </div>

  <div class="stat-row rise2">
    <div class="stat-card">
      <div class="stat-icon purple"><svg viewBox="0 0 24 24"><path d="M21 11.5a8.4 8.4 0 0 1-9 8.5 8.7 8.7 0 0 1-4-1L3 20l1-4a8.4 8.4 0 0 1-1-4 8.4 8.4 0 0 1 9-8.5 8.5 8.5 0 0 1 9 8.5z"/></svg></div>
      <div><div class="lbl">Rozmowy w tym miesiącu</div><div class="val">{{ calls|length }}</div></div>
    </div>
    <div class="stat-card">
      <div class="stat-icon teal"><svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg></div>
      <div><div class="lbl">Zakończone pomyślnie</div><div class="val">{{ calls|length }}</div></div>
    </div>
    <div class="stat-card">
      <div class="stat-icon amber"><svg viewBox="0 0 24 24"><path d="M10.68 13.31a16 16 0 0 0 3.41 2.6l1.27-1.27a2 2 0 0 1 2.11-.45c.86.31 1.77.53 2.71.65A2 2 0 0 1 22 16.92z"/><line x1="23" y1="1" x2="1" y2="23"/><path d="M16 8l4-4"/><path d="M20 8l-4-4"/></svg></div>
      <div><div class="lbl">Nieodebrane</div><div class="val">0</div></div>
    </div>
  </div>

  <div class="filters rise3">
    <button class="filter-btn active" data-filter="all" onclick="filterCalls('all', this)">Wszystkie</button>
    <button class="filter-btn" data-filter="incoming" onclick="filterCalls('incoming', this)">Przychodzące</button>
    <button class="filter-btn" data-filter="outbound" onclick="filterCalls('outbound', this)">Zadzwoń za mnie</button>
    <button class="filter-btn" data-filter="missed" onclick="filterCalls('missed', this)">Nieodebrane</button>
  </div>

  {% if calls %}
  <div class="calls-table rise4">
    <table>
      <tr><th>Data</th><th>Typ</th><th>Z kim</th><th>Podsumowanie</th><th>Status</th></tr>
      {% for call in calls %}
      <tr class="datarow" data-type="incoming" data-status="ok">
        <td>{{ call.data }}</td>
        <td><div class="call-type"><svg viewBox="0 0 24 24"><path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6 19.8 19.8 0 0 1-3.1-8.6A2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .3 2 .6 3a2 2 0 0 1-.5 2.1L8 10a16 16 0 0 0 6 6l1.2-1.2a2 2 0 0 1 2.1-.5c1 .3 2 .5 3 .6a2 2 0 0 1 1.7 2z"/></svg>Przychodząca</div></td>
        <td>{{ call.z_kim }}</td>
        <td>{{ call.podsumowanie }}</td>
        <td><span class="tag ok">Zakończona</span></td>
      </tr>
      {% endfor %}
    </table>

  </div>
  {% else %}
  <div class="calls-table">
    <div class="empty-state">
      <div class="empty-icon"><svg viewBox="0 0 24 24"><path d="M21 11.5a8.4 8.4 0 0 1-9 8.5 8.7 8.7 0 0 1-4-1L3 20l1-4a8.4 8.4 0 0 1-1-4 8.4 8.4 0 0 1 9-8.5 8.5 8.5 0 0 1 9 8.5z"/></svg></div>
      <b>Nie masz jeszcze żadnych rozmów</b>
      <p>Gdy Twój asystent odbierze pierwsze połączenie, pojawi się tutaj.</p>
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
    <span class="label">Dashboard</span>
  </a>
  <a class="nav-item{{ ' active' if active_page == 'number' else '' }}" href="/numer-telefonu">
    <i data-lucide="phone" class="nav-icon"></i>
    <span class="label">Numer telefonu</span>
  </a>
  <a class="nav-item{{ ' active' if active_page == 'voice' else '' }}" href="/moj-glos">
    <i data-lucide="mic" class="nav-icon"></i>
    <span class="label">Mój głos</span>
  </a>
  <a class="nav-item{{ ' active' if active_page == 'calls' else '' }}" href="/rozmowy">
    <i data-lucide="message-circle" class="nav-icon"></i>
    <span class="label">Rozmowy</span>
  </a>
  <a class="nav-item{{ ' active' if active_page == 'pricing' else '' }}" href="/cennik">
    <i data-lucide="credit-card" class="nav-icon"></i>
    <span class="label">Cennik</span>
  </a>
  <div class="nav-section-label">Konto</div>
  <a class="nav-item{{ ' active' if active_page == 'settings' else '' }}" href="/ustawienia">
    <i data-lucide="settings" class="nav-icon"></i>
    <span class="label">Ustawienia</span>
  </a>

  <div class="sidebar-widget">
    <div class="sw-title">Twój asystent AI<br>24/7 gotowy do rozmów</div>
    <div class="sw-orbit"><div class="sw-ring"></div><div class="sw-sphere"></div></div>
    <a class="sw-link" href="/dashboard">Zobacz statystyki →</a>
  </div>
</div>

<div class="main rise">
  <div class="hero-glow"></div>
  <div class="head">
    <h1>Ustawienia</h1>
    <p>Zarządzaj swoim kontem, subskrypcją i preferencjami.</p>
  </div>

  <div class="card rise2">
    <div class="card-head"><div class="card-icon purple"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 8v4l3 2"/></svg></div><h3>Profil</h3></div>
    <div class="profile-row">
      <div class="avatar-lg" id="avatarLg">{{ user_email[0]|upper if user_email else "U" }}</div>
      <div class="profile-info">
        <b id="profileName">{{ user_email }}</b>
        <span id="profileEmail">{{ user_email }}</span>
      </div>
    </div>
    <div class="field-row">
      <span class="lbl">Imię wyświetlane</span>
      <input type="text" id="nameInput" placeholder="Twoje imię" style="border:1px solid #ddd;border-radius:8px;padding:7px 10px;font-size:13px;font-family:inherit;width:160px;text-align:right;">
    </div>
    <button class="btn-outline" onclick="saveProfile()" style="margin-top:12px;">Zapisz zmiany</button>
    <div id="saveMsg">Zapisano ✓</div>
  </div>

  <div class="card rise3">
    <div class="card-head"><div class="card-icon teal"><svg viewBox="0 0 24 24"><rect x="1" y="4" width="22" height="16" rx="2"/><line x1="1" y1="10" x2="23" y2="10"/></svg></div><h3>Subskrypcja</h3></div>
    <div class="plan-banner">
      <div>
        <b id="currentPlanName">Sprawdzam plan...</b>
        <span id="currentPlanDesc">Ładowanie danych konta</span>
      </div>
      <a href="/cennik">Zmień plan</a>
    </div>
  </div>

  <div class="card rise3">
    <div class="card-head"><div class="card-icon blue"><svg viewBox="0 0 24 24"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg></div><h3>Bezpieczeństwo</h3></div>
    <div class="field-row">
      <span class="lbl">Hasło</span>
      <button class="btn-outline" onclick="resetPassword()">Zresetuj hasło</button>
    </div>
    <div id="resetMsg" style="font-size:12.5px;color:#1e9e63;margin-top:8px;display:none;"></div>
  </div>

  <div class="card danger-zone rise4">
    <div class="card-head"><div class="card-icon red"><svg viewBox="0 0 24 24"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg></div><h3 style="color:#c0392b;">Strefa zagrożenia</h3></div>
    <div class="danger-row">
      <div>
        <b style="font-size:13.5px;">Wyloguj się ze wszystkich urządzeń</b>
        <p>Zakończy Twoją sesję na tym i innych urządzeniach.</p>
      </div>
      <a href="/logout" class="btn-outline">Wyloguj</a>
    </div>
  </div>
</div>

<script type="module">
  import { initializeApp } from "https://www.gstatic.com/firebasejs/10.13.0/firebase-app.js";
  import { getAuth, onAuthStateChanged, sendPasswordResetEmail, updateProfile } from "https://www.gstatic.com/firebasejs/10.13.0/firebase-auth.js";
  import { getFirestore, doc, getDoc, updateDoc } from "https://www.gstatic.com/firebasejs/10.13.0/firebase-firestore.js";

  const firebaseConfig = {{ firebase_config | tojson }};
  const app = initializeApp(firebaseConfig);
  const auth = getAuth(app);
  const db = getFirestore(app);

  let currentUser = null;

  const PLAN_NAMES = {
    "start": ["Plan Start", "149 zł/mies. · 100 minut rozmów"],
    "pro": ["Plan Pro", "399 zł/mies. · 400 minut rozmów"],
    "firma": ["Plan Firma", "899 zł/mies. · 1000+ minut rozmów"],
    "free": ["Brak aktywnego planu", "Wybierz plan, aby aktywować asystenta"]
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
    const plan = data.plan || "free";
    const [name, desc] = PLAN_NAMES[plan] || PLAN_NAMES["free"];
    document.getElementById("currentPlanName").textContent = name;
    document.getElementById("currentPlanDesc").textContent = desc;
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
      msg.textContent = "Link do resetu hasla wyslany na " + currentUser.email;
      msg.style.display = "block";
    } catch (e) {
      msg.textContent = "Blad: " + e.message;
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
        calls=FAKE_CALLS,
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

@app.route("/rozmowy")
def rozmowy():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    return render_template_string(
        CALLS_PAGE,
        calls=FAKE_CALLS,
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


def generate_speech_url(text, filename):
    """Generuje mowe przez ElevenLabs, zapisuje jako plik, zwraca publiczny URL."""
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
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


def gather_response_twiml(audio_url, action):
    """Buduje TwiML: odtwarza audio, potem sluchaj odpowiedzi (Gather ze speech recognition)."""
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather input="speech" action="{action}" method="POST" language="pl-PL" speechTimeout="auto">
        <Play>{audio_url}</Play>
    </Gather>
    <Say language="pl-PL">Nie uslyszalem odpowiedzi. Dziekuje za telefon, do uslyszenia.</Say>
    <Hangup/>
</Response>'''


@app.route("/incoming-call", methods=["POST"])
def incoming_call():
    call_sid = request.form.get("CallSid", "unknown")
    system_prompt = (
        "Jestes asystentem AI odbierajacym telefon w imieniu firmy. "
        "Rozmawiaj po polsku, krotko, uprzejmie i konkretnie. "
        "Oto instrukcje jak masz sie zachowywac: " + bot_instructions["text"]
    )
    CALL_CONTEXT[call_sid] = {"messages": [{"role": "system", "content": system_prompt}]}

    greeting = "Dzien dobry, tu automatyczny asystent. Slucham, w czym moge pomoc?"
    CALL_CONTEXT[call_sid]["messages"].append({"role": "assistant", "content": greeting})

    audio_url = generate_speech_url(greeting, f"greet_{call_sid}.mp3")
    if not audio_url:
        return Response(
            '<?xml version="1.0" encoding="UTF-8"?><Response><Say language="pl-PL">Wystapil blad.</Say></Response>',
            mimetype="text/xml"
        )
    return Response(gather_response_twiml(audio_url, "/handle-speech"), mimetype="text/xml")


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

    ctx["messages"].append({"role": "user", "content": speech_result})
    reply = ask_ai(ctx["messages"])
    ctx["messages"].append({"role": "assistant", "content": reply})

    audio_url = generate_speech_url(reply, f"reply_{call_sid}_{len(ctx['messages'])}.mp3")
    if not audio_url:
        return Response(
            '<?xml version="1.0" encoding="UTF-8"?><Response><Say language="pl-PL">Wystapil blad.</Say><Hangup/></Response>',
            mimetype="text/xml"
        )
    return Response(gather_response_twiml(audio_url, "/handle-speech"), mimetype="text/xml")


@app.route("/outbound-twiml", methods=["GET", "POST"])
def outbound_twiml():
    call_sid = request.values.get("CallSid", "unknown")
    task = request.values.get("task", "Przekaz uprzejmie ze to test systemu EchoLine.")

    system_prompt = (
        "Dzwonisz w imieniu uzytkownika EchoLine, zeby zalatwic konkretna sprawe. "
        "Rozmawiaj po polsku, krotko i uprzejmie. Twoje zadanie: " + task
    )
    CALL_CONTEXT[call_sid] = {"messages": [{"role": "system", "content": system_prompt}]}

    greeting = "Dzien dobry, dzwonie w imieniu mojego uzytkownika w nastepujacej sprawie: " + task
    CALL_CONTEXT[call_sid]["messages"].append({"role": "assistant", "content": greeting})

    audio_url = generate_speech_url(greeting, f"outbound_{call_sid}.mp3")
    if not audio_url:
        return Response(
            '<?xml version="1.0" encoding="UTF-8"?><Response><Say language="pl-PL">Wystapil blad.</Say></Response>',
            mimetype="text/xml"
        )
    return Response(gather_response_twiml(audio_url, "/handle-speech"), mimetype="text/xml")


@app.route("/start-outbound-call", methods=["POST"])
def start_outbound_call():
    if not session.get("logged_in"):
        return {"error": "not logged in"}, 401

    data = request.get_json()
    to_number = data.get("phone_number")
    task = data.get("task")
    if not to_number or not task:
        return {"error": "brak numeru lub zadania"}, 400

    sid = os.environ.get("TWILIO_ACCOUNT_SID")
    token = os.environ.get("TWILIO_AUTH_TOKEN")
    if not sid or not token:
        return {"error": "Brak skonfigurowanych danych Twilio na serwerze."}, 500

    twiml_url = request.url_root + "outbound-twiml?task=" + requests.utils.quote(task)
    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Calls.json"
    r = requests.post(url, auth=(sid, token), data={
        "To": to_number,
        "From": TWILIO_FROM_NUMBER,
        "Url": twiml_url,
    })

    if r.status_code not in (200, 201):
        try:
            err = r.json().get("message", r.text)
        except Exception:
            err = r.text
        return {"error": err}, 500

    return {"ok": True, "call_sid": r.json().get("sid")}


if __name__ == "__main__":
    os.makedirs("static", exist_ok=True)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
