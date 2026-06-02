"""
Página de autorização OAuth integrada ao fluxo MCP.
Aparece quando o Quick Suite redireciona o usuário para /authorize.
Fluxo: Login/Signup → Token PipeRun → Redirect com code para o Quick.
"""

AUTHORIZE_PAGE_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>PipeRun - Autorizar MCP</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
     background:linear-gradient(135deg,#1a1a2e,#16213e);
     min-height:100vh;display:flex;justify-content:center;align-items:center;padding:20px}
.card{background:#fff;border-radius:16px;padding:40px;
      box-shadow:0 20px 60px rgba(0,0,0,.3);max-width:460px;width:100%}
.logo{text-align:center;margin-bottom:24px}
.logo h1{color:#e53935;font-size:24px}
.logo p{color:#666;font-size:13px;margin-top:4px}
h2{font-size:18px;color:#333;margin-bottom:16px}
label{display:block;font-weight:600;margin-bottom:6px;color:#333;font-size:14px}
input{width:100%;padding:12px;border:1px solid #ddd;border-radius:8px;
      font-size:14px;margin-bottom:16px}
input:focus{outline:none;border-color:#e53935}
button{width:100%;padding:14px;background:#e53935;color:#fff;border:none;
       border-radius:8px;font-size:16px;font-weight:600;cursor:pointer;margin-bottom:8px}
button:hover{background:#c62828}
button:disabled{background:#ccc;cursor:not-allowed}
.btn-sec{background:#fff;color:#e53935;border:2px solid #e53935}
.btn-sec:hover{background:#ffebee}
.msg{padding:12px;border-radius:8px;margin-bottom:16px;font-size:13px;display:none}
.msg-err{background:#ffebee;color:#c62828}
.msg-ok{background:#e8f5e9;color:#2e7d32}
.hidden{display:none}
.link{color:#e53935;cursor:pointer;font-size:13px;text-align:center;display:block;margin-top:8px}
.link:hover{text-decoration:underline}
.spinner{display:inline-block;width:16px;height:16px;border:2px solid #fff;
         border-top-color:transparent;border-radius:50%;animation:spin .6s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
.info{background:#e3f2fd;color:#1565c0;padding:12px;border-radius:8px;
      margin-bottom:16px;font-size:12px}
</style>
</head>
<body>
<div class="card">
<div class="logo">
    <h1>&#128279; MCP PipeRun</h1>
    <p>Autorize o acesso ao seu CRM PipeRun</p>
</div>
<div class="msg msg-err" id="err"></div>
<div class="msg msg-ok" id="ok"></div>
"""
AUTHORIZE_PAGE_HTML += """
<!-- ESCOLHA -->
<div id="v-choice">
    <div class="info">O Amazon Quick Suite precisa da sua autorizacao para acessar o PipeRun.</div>
    <button onclick="show('v-login')">Entrar com minha conta</button>
    <button class="btn-sec" onclick="show('v-signup')">Criar nova conta</button>
</div>

<!-- LOGIN -->
<div id="v-login" class="hidden">
    <h2>Entrar</h2>
    <label>E-mail</label>
    <input type="email" id="l-email" placeholder="seu@dati.com.br">
    <label>Senha</label>
    <input type="password" id="l-pass">
    <button onclick="doLogin()" id="btn-login">Entrar</button>
    <span class="link" onclick="show('v-signup')">Criar nova conta</span>
</div>

<!-- SIGNUP -->
<div id="v-signup" class="hidden">
    <h2>Criar conta</h2>
    <label>E-mail</label>
    <input type="email" id="s-email" placeholder="seu@dati.com.br">
    <label>Nome completo</label>
    <input type="text" id="s-name" placeholder="Diego Alexandre">
    <label>Senha (min 8, maiuscula + numero)</label>
    <input type="password" id="s-pass">
    <button onclick="doSignup()" id="btn-signup">Criar conta</button>
    <span class="link" onclick="show('v-login')">Ja tenho conta</span>
</div>

<!-- CONFIRM EMAIL -->
<div id="v-confirm" class="hidden">
    <h2>Confirme seu e-mail</h2>
    <p style="color:#666;margin-bottom:16px;font-size:14px">Enviamos um codigo para seu e-mail.</p>
    <label>Codigo (6 digitos)</label>
    <input type="text" id="c-code" maxlength="6" placeholder="123456">
    <button onclick="doConfirm()" id="btn-confirm">Confirmar</button>
</div>

<!-- TOKEN PIPERUN -->
<div id="v-token" class="hidden">
    <h2>Cole seu token PipeRun</h2>
    <p style="color:#666;margin-bottom:16px;font-size:14px">
        Encontre em <a href="https://app.pipe.run/v2/me/user-data" target="_blank">Meus Dados</a>
        ou Configuracoes &gt; Integracoes &gt; API.</p>
    <label>Token da API PipeRun</label>
    <input type="password" id="t-token" placeholder="Cole aqui">
    <button onclick="doToken()" id="btn-token">Autorizar acesso</button>
</div>

<!-- REDIRECTING -->
<div id="v-done" class="hidden" style="text-align:center;padding:20px">
    <div style="font-size:48px;margin-bottom:16px">&#9989;</div>
    <h2 style="color:#2e7d32">Autorizado!</h2>
    <p style="color:#666;margin-top:12px;font-size:14px">Redirecionando de volta...</p>
</div>
</div>
"""
AUTHORIZE_PAGE_HTML += """
<script>
const API = "{API_BASE_URL}";
const REGION = "{REGION}";
const CLIENT_ID = "{CLIENT_ID}";
const REDIRECT_URI = "{REDIRECT_URI}";
const STATE = "{STATE}";
const COGNITO_URL = "https://cognito-idp." + REGION + ".amazonaws.com/";

let email = "", password = "", accessToken = "";

function show(id) {
    ["v-choice","v-login","v-signup","v-confirm","v-token","v-done"]
        .forEach(v => document.getElementById(v).classList.add("hidden"));
    document.getElementById(id).classList.remove("hidden");
    hideMsg();
}
function showErr(m){const e=document.getElementById("err");e.textContent=m;e.style.display="block";e.classList.add("msg-err");document.getElementById("ok").style.display="none";}
function showOk(m){const e=document.getElementById("ok");e.textContent=m;e.style.display="block";e.classList.add("msg-ok");document.getElementById("err").style.display="none";}
function hideMsg(){document.getElementById("err").style.display="none";document.getElementById("ok").style.display="none";}

async function cognito(target, body) {
    const r = await fetch(COGNITO_URL, {
        method:"POST",
        headers:{"Content-Type":"application/x-amz-json-1.1","X-Amz-Target":"AWSCognitoIdentityProviderService."+target},
        body:JSON.stringify(body)
    });
    const d = await r.json();
    if(!r.ok) throw new Error(d.message||d.Message||"Erro Cognito");
    return d;
}

async function login(user, pass) {
    const d = await cognito("InitiateAuth", {
        AuthFlow:"USER_PASSWORD_AUTH", ClientId:CLIENT_ID,
        AuthParameters:{USERNAME:user, PASSWORD:pass}
    });
    if(d.AuthenticationResult && d.AuthenticationResult.AccessToken){
        accessToken = d.AuthenticationResult.AccessToken;
        return true;
    }
    throw new Error("Login falhou.");
}

async function doLogin() {
    email = document.getElementById("l-email").value.trim();
    password = document.getElementById("l-pass").value;
    if(!email||!password){showErr("Preencha e-mail e senha.");return;}
    const btn=document.getElementById("btn-login");
    btn.disabled=true;btn.innerHTML='<span class="spinner"></span>';
    try {
        await login(email, password);
        // Verificar se ja tem token PipeRun cadastrado
        const check = await fetch(API+"/register-token", {
            method:"POST",
            headers:{"Authorization":"Bearer "+accessToken,"Content-Type":"application/json"},
            body:JSON.stringify({check_only:true})
        });
        // Se ja tem token, redirecionar direto
        if(check.status === 200) {
            const data = await check.json();
            if(data.already_registered) { doRedirect(); return; }
        }
        show("v-token");
    } catch(e){showErr(e.message);}
    btn.disabled=false;btn.textContent="Entrar";
}

async function doSignup() {
    email = document.getElementById("s-email").value.trim();
    const name = document.getElementById("s-name").value.trim();
    password = document.getElementById("s-pass").value;
    if(!email||!name||!password){showErr("Preencha todos os campos.");return;}
    if(password.length<8){showErr("Senha: minimo 8 caracteres.");return;}
    const btn=document.getElementById("btn-signup");
    btn.disabled=true;btn.innerHTML='<span class="spinner"></span>';
    try {
        await cognito("SignUp",{
            ClientId:CLIENT_ID, Username:email, Password:password,
            UserAttributes:[{Name:"email",Value:email},{Name:"name",Value:name}]
        });
        show("v-confirm");
    } catch(e){
        if(e.message.includes("UsernameExists")||e.message.includes("already exists")){
            showErr("E-mail ja cadastrado. Use 'Entrar'.");
        } else {showErr(e.message);}
    }
    btn.disabled=false;btn.textContent="Criar conta";
}

async function doConfirm() {
    const code=document.getElementById("c-code").value.trim();
    if(!code){showErr("Digite o codigo.");return;}
    const btn=document.getElementById("btn-confirm");
    btn.disabled=true;btn.innerHTML='<span class="spinner"></span>';
    try {
        await cognito("ConfirmSignUp",{ClientId:CLIENT_ID,Username:email,ConfirmationCode:code});
        await login(email, password);
        show("v-token");
    } catch(e){showErr(e.message);}
    btn.disabled=false;btn.textContent="Confirmar";
}

async function doToken() {
    const token=document.getElementById("t-token").value.trim();
    if(!token){showErr("Cole o token do PipeRun.");return;}
    const btn=document.getElementById("btn-token");
    btn.disabled=true;btn.innerHTML='<span class="spinner"></span>';
    try {
        const r = await fetch(API+"/register-token",{
            method:"POST",
            headers:{"Authorization":"Bearer "+accessToken,"Content-Type":"application/json"},
            body:JSON.stringify({piperun_token:token})
        });
        if(r.status===401){
            await login(email, password);
            const r2 = await fetch(API+"/register-token",{
                method:"POST",
                headers:{"Authorization":"Bearer "+accessToken,"Content-Type":"application/json"},
                body:JSON.stringify({piperun_token:token})
            });
            if(!r2.ok){const d=await r2.json();throw new Error(d.error||"Erro");}
        } else if(!r.ok){
            const d=await r.json();throw new Error(d.error||d.message||"Erro");
        }
        doRedirect();
    } catch(e){showErr(e.message);}
    btn.disabled=false;btn.textContent="Autorizar acesso";
}

function doRedirect() {
    show("v-done");
    // Redirecionar de volta pro Quick com o access_token como code
    if(REDIRECT_URI) {
        const sep = REDIRECT_URI.includes("?") ? "&" : "?";
        const url = REDIRECT_URI + sep + "code=" + encodeURIComponent(accessToken) + "&state=" + encodeURIComponent(STATE);
        setTimeout(()=>{ window.location.href = url; }, 1000);
    }
}
</script>
</body></html>"""
