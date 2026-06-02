"""
Página HTML de auto-cadastro + login.
Se já tem conta, faz login e vai direto pro cadastro do token PipeRun.
"""

SIGNUP_PAGE_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MCP PipeRun - Cadastro</title>
    <style>
        *{box-sizing:border-box;margin:0;padding:0}
        body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
             background:linear-gradient(135deg,#1a1a2e,#16213e);
             min-height:100vh;display:flex;justify-content:center;
             align-items:center;padding:20px}
        .card{background:#fff;border-radius:16px;padding:40px;
              box-shadow:0 20px 60px rgba(0,0,0,.3);max-width:460px;width:100%}
        .logo{text-align:center;margin-bottom:24px}
        .logo h1{color:#e53935;font-size:28px}
        .logo p{color:#666;font-size:14px;margin-top:4px}
        h2{font-size:18px;color:#333;margin-bottom:16px}
        label{display:block;font-weight:600;margin-bottom:6px;color:#333;font-size:14px}
        input{width:100%;padding:12px;border:1px solid #ddd;border-radius:8px;
              font-size:14px;margin-bottom:16px}
        input:focus{outline:none;border-color:#e53935}
        button{width:100%;padding:14px;background:#e53935;color:#fff;border:none;
               border-radius:8px;font-size:16px;font-weight:600;cursor:pointer;
               margin-bottom:8px}
        button:hover{background:#c62828}
        button:disabled{background:#ccc;cursor:not-allowed}
        .btn-sec{background:#fff;color:#e53935;border:2px solid #e53935}
        .btn-sec:hover{background:#ffebee}
        .error{background:#ffebee;color:#c62828;padding:12px;border-radius:8px;
               margin-bottom:16px;font-size:13px;display:none}
        .success{background:#e8f5e9;color:#2e7d32;padding:12px;border-radius:8px;
                 margin-bottom:16px;font-size:13px;display:none}
        .hidden{display:none}
        .link{color:#e53935;cursor:pointer;font-size:13px;text-align:center;
              margin-top:8px;display:block}
        .link:hover{text-decoration:underline}
        .spinner{display:inline-block;width:16px;height:16px;border:2px solid #fff;
                 border-top-color:transparent;border-radius:50%;
                 animation:spin .6s linear infinite}
        @keyframes spin{to{transform:rotate(360deg)}}
    </style>
</head>
<body>
<div class="card">
    <div class="logo"><h1>&#128279; MCP PipeRun</h1>
    <p>Cadastro para uso no Amazon Quick Suite</p></div>
    <div class="error" id="err"></div>
    <div class="success" id="ok"></div>
"""
SIGNUP_PAGE_HTML += """
    <!-- ESCOLHA: signup ou login -->
    <div id="step-choice">
        <h2>Como deseja continuar?</h2>
        <button onclick="showStep('step-signup')">Criar nova conta</button>
        <button class="btn-sec" onclick="showStep('step-login')">Ja tenho conta</button>
    </div>

    <!-- SIGNUP -->
    <div id="step-signup" class="hidden">
        <h2>Criar conta</h2>
        <label>E-mail</label>
        <input type="email" id="s-email" placeholder="seu@dati.com.br">
        <label>Nome completo</label>
        <input type="text" id="s-name" placeholder="Diego Alexandre">
        <label>Senha (min 8, maiuscula+numero)</label>
        <input type="password" id="s-pass" placeholder="Crie uma senha">
        <button onclick="doSignup()" id="btn-signup">Criar conta</button>
        <span class="link" onclick="showStep('step-login')">Ja tenho conta</span>
    </div>

    <!-- CONFIRM -->
    <div id="step-confirm" class="hidden">
        <h2>Confirme seu e-mail</h2>
        <p style="color:#666;margin-bottom:16px;font-size:14px">
            Enviamos um codigo de 6 digitos para seu e-mail.</p>
        <label>Codigo de verificacao</label>
        <input type="text" id="c-code" placeholder="123456" maxlength="6">
        <button onclick="doConfirm()" id="btn-confirm">Confirmar</button>
    </div>

    <!-- LOGIN -->
    <div id="step-login" class="hidden">
        <h2>Entrar na conta</h2>
        <label>E-mail</label>
        <input type="email" id="l-email" placeholder="seu@dati.com.br">
        <label>Senha</label>
        <input type="password" id="l-pass" placeholder="Sua senha">
        <button onclick="doLogin()" id="btn-login">Entrar</button>
        <span class="link" onclick="showStep('step-signup')">Criar nova conta</span>
    </div>

    <!-- TOKEN PIPERUN -->
    <div id="step-token" class="hidden">
        <h2>Cole seu token PipeRun</h2>
        <p style="color:#666;margin-bottom:16px;font-size:14px">
            Encontre em <a href="https://app.pipe.run/v2/me/user-data" target="_blank">
            Meus Dados</a> ou Configuracoes &gt; Integracoes &gt; API.</p>
        <label>Token da API PipeRun</label>
        <input type="password" id="t-token" placeholder="Cole seu token aqui">
        <button onclick="doToken()" id="btn-token">Finalizar cadastro</button>
    </div>

    <!-- SUCESSO -->
    <div id="step-done" class="hidden" style="text-align:center;padding:20px">
        <div style="font-size:48px;margin-bottom:16px">&#9989;</div>
        <h2 style="color:#2e7d32">Cadastro completo!</h2>
        <p style="color:#666;margin-top:12px;font-size:14px">
            Seu MCP PipeRun esta pronto.<br><br>
            <strong>Endpoint MCP:</strong><br>
            <code style="background:#f5f5f5;padding:4px 8px;border-radius:4px;
            font-size:12px">{API_BASE_URL}/mcp</code>
        </p>
    </div>
</div>
"""
SIGNUP_PAGE_HTML += """
<script>
const API = "{API_BASE_URL}";
const REGION = "{REGION}";
const CLIENT_ID = "{CLIENT_ID}";
const COGNITO_URL = "https://cognito-idp." + REGION + ".amazonaws.com/";

let email = "", password = "", accessToken = "";

function showStep(id) {
    ["step-choice","step-signup","step-confirm","step-login","step-token","step-done"]
        .forEach(s => document.getElementById(s).classList.add("hidden"));
    document.getElementById(id).classList.remove("hidden");
    hide();
}
function showErr(m) { const e=document.getElementById("err"); e.textContent=m; e.style.display="block"; document.getElementById("ok").style.display="none"; }
function showOk(m) { const e=document.getElementById("ok"); e.textContent=m; e.style.display="block"; document.getElementById("err").style.display="none"; }
function hide() { document.getElementById("err").style.display="none"; document.getElementById("ok").style.display="none"; }

async function cognitoCall(target, body) {
    const r = await fetch(COGNITO_URL, {
        method: "POST",
        headers: {"Content-Type":"application/x-amz-json-1.1","X-Amz-Target":"AWSCognitoIdentityProviderService."+target},
        body: JSON.stringify(body)
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.message || d.Message || JSON.stringify(d));
    return d;
}

async function doSignup() {
    email = document.getElementById("s-email").value.trim();
    const name = document.getElementById("s-name").value.trim();
    password = document.getElementById("s-pass").value;
    if (!email||!name||!password) { showErr("Preencha todos os campos."); return; }
    if (password.length<8) { showErr("Senha deve ter no minimo 8 caracteres."); return; }

    const btn = document.getElementById("btn-signup");
    btn.disabled=true; btn.innerHTML='<span class="spinner"></span>';
    try {
        await cognitoCall("SignUp", {
            ClientId: CLIENT_ID, Username: email, Password: password,
            UserAttributes: [{Name:"email",Value:email},{Name:"name",Value:name}]
        });
        showStep("step-confirm");
    } catch(e) {
        if (e.message.includes("UsernameExists") || e.message.includes("already exists")) {
            showErr("E-mail ja cadastrado. Use 'Ja tenho conta'.");
        } else { showErr(e.message); }
    }
    btn.disabled=false; btn.textContent="Criar conta";
}

async function doConfirm() {
    const code = document.getElementById("c-code").value.trim();
    if (!code) { showErr("Digite o codigo."); return; }
    const btn = document.getElementById("btn-confirm");
    btn.disabled=true; btn.innerHTML='<span class="spinner"></span>';
    try {
        await cognitoCall("ConfirmSignUp", {ClientId:CLIENT_ID, Username:email, ConfirmationCode:code});
        // Login automatico apos confirmar
        await loginWithCredentials(email, password);
        showStep("step-token");
    } catch(e) { showErr(e.message); }
    btn.disabled=false; btn.textContent="Confirmar";
}

async function doLogin() {
    email = document.getElementById("l-email").value.trim();
    password = document.getElementById("l-pass").value;
    if (!email||!password) { showErr("Preencha e-mail e senha."); return; }
    const btn = document.getElementById("btn-login");
    btn.disabled=true; btn.innerHTML='<span class="spinner"></span>';
    try {
        await loginWithCredentials(email, password);
        showStep("step-token");
    } catch(e) { showErr(e.message); }
    btn.disabled=false; btn.textContent="Entrar";
}

async function loginWithCredentials(user, pass) {
    const data = await cognitoCall("InitiateAuth", {
        AuthFlow: "USER_PASSWORD_AUTH",
        ClientId: CLIENT_ID,
        AuthParameters: { USERNAME: user, PASSWORD: pass }
    });
    if (data.AuthenticationResult && data.AuthenticationResult.AccessToken) {
        accessToken = data.AuthenticationResult.AccessToken;
    } else {
        throw new Error("Login falhou. Verifique suas credenciais.");
    }
}

async function doToken() {
    const token = document.getElementById("t-token").value.trim();
    if (!token) { showErr("Cole o token do PipeRun."); return; }
    const btn = document.getElementById("btn-token");
    btn.disabled=true; btn.innerHTML='<span class="spinner"></span>';
    try {
        const r = await fetch(API + "/register-token", {
            method: "POST",
            headers: {"Authorization":"Bearer "+accessToken,"Content-Type":"application/json"},
            body: JSON.stringify({piperun_token: token})
        });
        const d = await r.json();
        if (!r.ok) {
            if (r.status === 401) {
                // Token cognito expirou, refazer login
                showErr("Sessao expirada. Refazendo login...");
                await loginWithCredentials(email, password);
                // Tentar novamente
                const r2 = await fetch(API + "/register-token", {
                    method: "POST",
                    headers: {"Authorization":"Bearer "+accessToken,"Content-Type":"application/json"},
                    body: JSON.stringify({piperun_token: token})
                });
                const d2 = await r2.json();
                if (!r2.ok) throw new Error(d2.error || d2.message || "Erro ao registrar token.");
            } else {
                throw new Error(d.error || d.message || "Erro ao registrar token.");
            }
        }
        showStep("step-done");
    } catch(e) { showErr(e.message); }
    btn.disabled=false; btn.textContent="Finalizar cadastro";
}
</script>
</body></html>"""
