/* AI Customer Support — widget chat nhúng. JS thuần, không dependency.
   Cách dùng: <script src="/widget/widget.js" data-api="http://localhost:8005"></script> */
(function () {
  if (window.__acsWidget) return;
  window.__acsWidget = true;

  var SCRIPT = document.currentScript;
  var API = (SCRIPT && SCRIPT.dataset.api) || "";
  var SESSION_KEY = "acs_session";

  function sessionId() {
    var s = localStorage.getItem(SESSION_KEY);
    if (!s) { s = "w-" + Math.random().toString(36).slice(2, 10); localStorage.setItem(SESSION_KEY, s); }
    return s;
  }

  var cfg = { title: "Hỗ trợ khách hàng", welcome: "Chào bạn! Tôi có thể giúp gì?", primary_color: "#2563eb", bot_name: "Trợ lý ảo" };

  function inject() {
    var css = document.createElement("style");
    css.textContent =
      "#acs-widget{position:fixed;bottom:20px;right:20px;z-index:9999;font-family:-apple-system,'Segoe UI',Roboto,sans-serif;font-size:14px}" +
      "#acs-btn{width:56px;height:56px;border-radius:50%;border:none;cursor:pointer;color:#fff;box-shadow:0 4px 14px rgba(0,0,0,.35);display:flex;align-items:center;justify-content:center;transition:transform .15s}" +
      "#acs-btn:hover{transform:scale(1.06)}" +
      "#acs-panel{position:fixed;bottom:88px;right:20px;width:340px;max-width:calc(100vw - 40px);height:460px;max-height:calc(100vh - 120px);background:#161a22;border-radius:14px;display:none;flex-direction:column;overflow:hidden;box-shadow:0 8px 30px rgba(0,0,0,.45)}" +
      "#acs-panel.open{display:flex}" +
      "#acs-head{background:#0b0e13;padding:12px 14px;display:flex;align-items:center;gap:8px;border-bottom:1px solid #262c38}" +
      "#acs-head b{color:#e2e8f0;font-size:14px}" +
      "#acs-close{margin-left:auto;background:none;border:none;color:#94a3b8;cursor:pointer;font-size:16px}" +
      "#acs-msgs{flex:1;overflow-y:auto;padding:12px;display:flex;flex-direction:column;gap:8px}" +
      ".acs-m{max-width:82%;padding:8px 11px;border-radius:10px;line-height:1.45;white-space:pre-wrap;word-break:break-word}" +
      ".acs-user{align-self:flex-end;background:#2563eb;color:#fff;border-bottom-right-radius:3px}" +
      ".acs-bot{align-self:flex-start;background:#1d222d;color:#e2e8f0;border-bottom-left-radius:3px}" +
      "#acs-input-row{display:flex;gap:8px;padding:10px;border-top:1px solid #262c38;background:#0b0e13}" +
      "#acs-input{flex:1;background:#1d222d;border:1px solid #262c38;border-radius:8px;color:#e2e8f0;padding:8px 10px;font-size:14px;outline:none}" +
      "#acs-input:focus{border-color:" + cfg.primary_color + "}" +
      "#acs-send{background:" + cfg.primary_color + ";color:#fff;border:none;border-radius:8px;padding:8px 14px;cursor:pointer;font-size:14px}" +
      ".acs-typing{color:#94a3b8;font-size:12px;padding:4px 2px}";
    document.head.appendChild(css);

    var root = document.createElement("div");
    root.id = "acs-widget";
    root.innerHTML =
      '<button id="acs-btn" aria-label="Mở chat hỗ trợ">' +
      '<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg></button>' +
      '<div id="acs-panel">' +
      '<div id="acs-head"><b></b><button id="acs-close" aria-label="Đóng chat">✕</button></div>' +
      '<div id="acs-msgs"></div>' +
      '<div id="acs-input-row"><input id="acs-input" placeholder="Nhập câu hỏi..." /><button id="acs-send">Gửi</button></div>' +
      "</div>";
    document.body.appendChild(root);
  }

  function boot() {
    inject();
    var btn = document.getElementById("acs-btn");
    var panel = document.getElementById("acs-panel");
    var msgs = document.getElementById("acs-msgs");
    var input = document.getElementById("acs-input");

    document.getElementById("acs-head").querySelector("b").textContent = cfg.title;
    btn.style.background = cfg.primary_color;
    addMsg("bot", cfg.welcome);
    btn.onclick = function () { panel.classList.toggle("open"); input.focus(); };
    document.getElementById("acs-close").onclick = function () { panel.classList.remove("open"); };

    function addMsg(role, text) {
      var m = document.createElement("div");
      m.className = "acs-m acs-" + role;
      m.textContent = text;
      msgs.appendChild(m);
      msgs.scrollTop = msgs.scrollHeight;
    }

    function send() {
      var text = input.value.trim();
      if (!text) return;
      input.value = "";
      addMsg("user", text);
      var typing = document.createElement("div");
      typing.className = "acs-typing";
      typing.textContent = cfg.bot_name + " đang trả lời...";
      msgs.appendChild(typing);
      fetch(API + "/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId(), message: text, channel: "widget" }),
      })
        .then(function (r) { return r.json(); })
        .then(function (d) { typing.remove(); addMsg("bot", d.reply || "Lỗi máy chủ."); })
        .catch(function () { typing.remove(); addMsg("bot", "Không kết nối được máy chủ."); });
    }

    input.addEventListener("keydown", function (e) { if (e.key === "Enter") send(); });
    document.getElementById("acs-send").onclick = send;
  }

  fetch(API + "/widget/config")
    .then(function (r) { return r.json(); })
    .then(function (c) { cfg = Object.assign(cfg, c); boot(); })
    .catch(function () { boot(); });
})();
