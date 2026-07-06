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
  .bell{width:34px;height:34px;border-radius:50%;display:flex;align-items:center;justify-content:center;position:relative;cursor:pointer;}
  .bell:hover{background:#f5f5f7;}
  .bell svg{width:18px;height:18px;stroke:#555;fill:none;stroke-width:1.8;}
  .bell-dot{position:absolute;top:8px;right:9px;width:6px;height:6px;border-radius:50%;background:#ef4444;}
  a.logout{color:#888;font-size:13px;text-decoration:none;}
  a.logout:hover{text-decoration:underline;}
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
  .card-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;}
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
  }
</style>
</head>
<body>

<div class="sidebar">
  <div class="logo"><span class="logo-dot"></span>EchoLine</div>
  <a class="nav-item{{ ' active' if active_page == 'dashboard' else '' }}" href="/dashboard">
    <i data-lucide="layout-dashboard" class="nav-icon"></i>
    <span class="label">Dashboard</span>
  </a>
  <div class="nav-item">
    <i data-lucide="phone" class="nav-icon"></i>
    <span class="label">Numer telefonu</span>
  </div>
  <a class="nav-item{{ ' active' if active_page == 'voice' else '' }}" href="/moj-glos">
    <i data-lucide="mic" class="nav-icon"></i>
    <span class="label">Mój głos</span>
  </a>
  <div class="nav-item">
    <i data-lucide="message-circle" class="nav-icon"></i>
    <span class="label">Rozmowy</span>
  </div>
  <div class="nav-section-label">Konto</div>
  <div class="nav-item">
    <i data-lucide="settings" class="nav-icon"></i>
    <span class="label">Ustawienia</span>
  </div>

  <div class="sidebar-widget">
    <div class="sw-title">Twój asystent AI<br>24/7 gotowy do rozmów</div>
    <div class="sw-orbit"><div class="sw-ring"></div><div class="sw-sphere"></div></div>
    <a class="sw-link" href="#">Zobacz statystyki →</a>
  </div>
</div>

<div class="main">
  <div class="topbar">
    <div class="bell"><i data-lucide="bell"></i><div class="bell-dot"></div></div>
    <a class="logout" href="/logout">Wyloguj</a>
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
        <div class="action-card" onclick="location.href='#'">
          <div class="glow-icon glow-purple"><i data-lucide="phone"></i></div>
          <h3>Skonfiguruj numer <i data-lucide="chevron-right"></i></h3>
          <p>Wybierz kraj i uzyskaj swój numer telefonu</p>
        </div>
        <div class="action-card" onclick="location.href='/moj-glos';">
          <div class="glow-icon glow-blue"><i data-lucide="mic"></i></div>
          <h3>Sklonuj swój głos <i data-lucide="chevron-right"></i></h3>
          <p>Nagraj próbkę, aby bot mówił Twoim głosem</p>
        </div>
        <div class="action-card" onclick="document.getElementById('calls-card').scrollIntoView({behavior:'smooth',block:'center'});">
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
        <input id="phoneInput" type="text" placeholder="Numer telefonu docelowego, np. +48 601 234 567">
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
  window.showTab = function(tab){
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
    const phone = document.getElementById('phoneInput').value.trim();
    const status = document.getElementById('quickCallStatus');
    if(!task || !phone){ status.textContent = 'Wpisz zadanie i numer telefonu.'; status.style.color = '#c0392b'; return; }
    status.textContent = 'Ta funkcja uruchomi się po aktywacji numeru Twilio.';
    status.style.color = '#888';
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

  .main{flex:1;display:flex;flex-direction:column;min-width:0;}
  .topbar{display:flex;align-items:center;justify-content:space-between;padding:16px 32px;border-bottom:1px solid #eee;}
  .topbar h2{font-size:15px;font-weight:600;display:flex;align-items:center;gap:10px;}
  .back-link{color:#888;text-decoration:none;display:flex;align-items:center;}
  .back-link svg{width:18px;height:18px;stroke:#888;fill:none;stroke-width:1.8;}
  .avatar{width:32px;height:32px;border-radius:50%;background:linear-gradient(135deg,#7c6aff,#4f3fcf);color:#fff;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:700;flex-shrink:0;}

  .content{padding:40px 32px;max-width:560px;margin:0 auto;text-align:center;}
  .content h1{font-size:24px;font-weight:800;letter-spacing:-0.01em;margin-bottom:8px;}
  .content > p.sub{font-size:14px;color:#888;margin-bottom:32px;}

  #voiceStatus{font-size:13.5px;color:#888;margin-bottom:24px;}
  .voice-ready{color:#1e8449 !important;}
  .voice-ready-dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:#22d3a0;margin-right:6px;box-shadow:0 0 0 3px rgba(34,211,160,0.15);}

  #waveWrap{display:flex;flex-direction:column;align-items:center;gap:14px;margin-bottom:28px;padding:40px 16px;background:linear-gradient(180deg,#f2f8ff,#fafafa);border-radius:20px;}
  #waveWrap.hidden{display:none;}
  @keyframes recPulse{0%,100%{opacity:1;}50%{opacity:0.25;}}

  .spinner{width:18px;height:18px;border:2px solid #eee;border-top-color:#7c6aff;border-radius:50%;animation:spin 0.7s linear infinite;margin:0 auto;}
  @keyframes spin{to{transform:rotate(360deg);}}
  #processingWrap{display:none;flex-direction:column;align-items:center;gap:10px;margin-bottom:28px;padding:40px 16px;}

  .record-btn{padding:15px 28px;border-radius:13px;border:none;background:linear-gradient(135deg,#7c6aff,#5dadff);color:#fff;font-weight:700;font-size:15px;cursor:pointer;box-shadow:0 10px 24px rgba(124,106,255,0.3);}
  .record-btn:hover{opacity:0.92;}
  .hint{font-size:12.5px;color:#aaa;margin-top:14px;}

  @media (max-width: 760px) {
    body{flex-direction:column;}
    .sidebar{width:100%;border-right:none;border-bottom:1px solid #eee;flex-direction:row;align-items:center;padding:12px 16px;overflow-x:auto;white-space:nowrap;}
    .nav-section-label{display:none;}
    .logo{padding:0 14px 0 0;}
    .nav-item span.label{display:none;}
    .content{padding:24px 16px;}
    .topbar{padding:12px 16px;}
  }
</style>
</head>
<body>

<div class="sidebar">
  <div class="logo"><span class="logo-dot"></span>EchoLine</div>
  <a class="nav-item{{ ' active' if active_page == 'dashboard' else '' }}" href="/dashboard">
    <i data-lucide="layout-dashboard" class="nav-icon"></i>
    <span class="label">Dashboard</span>
  </a>
  <div class="nav-item">
    <i data-lucide="phone" class="nav-icon"></i>
    <span class="label">Numer telefonu</span>
  </div>
  <a class="nav-item{{ ' active' if active_page == 'voice' else '' }}" href="/moj-glos">
    <i data-lucide="mic" class="nav-icon"></i>
    <span class="label">Mój głos</span>
  </a>
  <div class="nav-item">
    <i data-lucide="message-circle" class="nav-icon"></i>
    <span class="label">Rozmowy</span>
  </div>
  <div class="nav-section-label">Konto</div>
  <div class="nav-item">
    <i data-lucide="settings" class="nav-icon"></i>
    <span class="label">Ustawienia</span>
  </div>
</div>

<div class="main">
  <div class="topbar">
    <h2><a class="back-link" href="/dashboard"><svg viewBox="0 0 24 24"><path d="M15 18l-6-6 6-6"/></svg></a>Mój głos</h2>
    <div class="avatar">{{ user_email[0]|upper if user_email else "U" }}</div>
  </div>

  <div class="content rise">
    <h1>Sklonuj swój głos</h1>
    <p class="sub">Nagraj krótką próbkę, żeby Twój asystent mówił Twoim własnym głosem</p>

    <p id="voiceStatus">Sprawdzam status...</p>

    <div id="waveWrap" class="hidden">
      <canvas id="waveCanvas" width="180" height="180"></canvas>
      <div style="display:flex;align-items:center;gap:8px;">
        <div id="recDot" style="width:8px;height:8px;border-radius:50%;background:#e74c3c;flex-shrink:0;animation:recPulse 1.2s infinite;"></div>
        <span style="font-size:12.5px;color:#888;">Nagrywanie</span>
        <span id="recTimer" style="font-size:12.5px;color:#888;font-variant-numeric:tabular-nums;">0:00</span>
      </div>
    </div>

    <div id="processingWrap">
      <div class="spinner"></div>
      <span style="font-size:13px;color:#888;">Klonowanie głosu przez AI...</span>
    </div>

    <button class="record-btn" id="recordBtn" onclick="toggleRecording()">Nagraj próbkę głosu</button>
    <p class="hint">Nagraj ok. 30-60 sekund swobodnej wypowiedzi, w cichym miejscu.</p>
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
  let audioCtx, analyser, timeData, animId, startTime, timerInterval;
  let level = 0, rippleT = 0;
  let waveW = 180, waveH = 180;

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
    const baseR = 30;
    const R = baseR + level * 34;

    rippleT += 0.015 + level * 0.05;
    for (let i = 0; i < 3; i++) {
      const phase = (rippleT + i / 3) % 1;
      const ringR = baseR + phase * 52;
      const alpha = (1 - phase) * 0.28;
      ctx.beginPath();
      ctx.strokeStyle = `rgba(93,173,255,${alpha})`;
      ctx.lineWidth = 2;
      ctx.arc(cx, cy, ringR, 0, Math.PI * 2);
      ctx.stroke();
    }

    const grad = ctx.createRadialGradient(cx, cy - R * 0.3, R * 0.1, cx, cy, R);
    grad.addColorStop(0, "#a9d8ff");
    grad.addColorStop(0.5, "#5dadff");
    grad.addColorStop(1, "#7c6aff");
    ctx.beginPath();
    ctx.fillStyle = grad;
    ctx.arc(cx, cy, R, 0, Math.PI * 2);
    ctx.fill();

    animId = requestAnimationFrame(drawOrb);
  }

  function sizeCanvas(){
    const canvas = document.getElementById("waveCanvas");
    const rect = canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    waveW = rect.width;
    waveH = rect.height;
    canvas.width = waveW * dpr;
    canvas.height = waveH * dpr;
    canvas.getContext("2d").scale(dpr, dpr);
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
        analyser.fftSize = 512;
        timeData = new Uint8Array(analyser.fftSize);
        source.connect(analyser);
        waveWrap.classList.remove("hidden");
        sizeCanvas();
        drawOrb();

        mediaRecorder = new MediaRecorder(stream);
        chunks = [];
        mediaRecorder.ondataavailable = (e) => chunks.push(e.data);
        mediaRecorder.onstop = uploadRecording;
        mediaRecorder.start();
        recording = true;

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
      waveWrap.classList.add("hidden");
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
