// portal.cpp -- Generate portal HTML (mirrors MicroPython _generate_portal)

#include "portal.h"
#include "config.h"
#include <LittleFS.h>
#include <WiFi.h>
#include <algorithm>
#include <vector>

// ============================================================
// STATIC HTML FRAGMENTS (PROGMEM)
// Custom delimiter "=(" / ")=" to avoid conflicts with HTML parens
// ============================================================

static const char PORTAL_HEAD[] PROGMEM = R"==(<!DOCTYPE html><html lang="de"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>MundMaus</title><link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='6' fill='%231a1a2e'/><text x='16' y='24' text-anchor='middle' font-size='22' font-weight='bold' fill='%23FFD700'>M</text></svg>"><style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:system-ui,sans-serif;background:#0a1628;color:#e0e0e0;
min-height:100vh;display:flex;flex-direction:column;align-items:center;padding:2em}
h1{font-size:clamp(2em,5vw,3.5em);color:#FFD700;margin-bottom:.2em}
.sub{color:#78909c;margin-bottom:1.5em}
.gs{display:flex;flex-wrap:wrap;gap:1.5em;justify-content:center;max-width:800px}
.g{display:flex;align-items:center;justify-content:center;width:220px;height:120px;
background:linear-gradient(135deg,#1a3a5c,#0d2240);border:2px solid rgba(255,215,0,.3);border-radius:16px;
color:#FFD700;font-size:1.3em;font-weight:600;text-decoration:none;transition:all .2s}
.g:hover{border-color:#FFD700;transform:scale(1.05);box-shadow:0 0 20px rgba(255,215,0,.3)}
.wf{background:rgba(255,255,255,.04);border:1px solid #333;border-radius:12px;padding:1.2em;
margin-top:2em;max-width:500px;width:100%}
.wf h2{font-size:1.1em;color:#FFD700;margin-bottom:.8em;display:flex;align-items:center;gap:.5em}
.wf label{font-size:.85em;color:#aaa;display:block;margin-bottom:.3em}
.wf select,.wf input{width:100%;padding:8px;margin-bottom:.8em;background:#1a2a3a;
border:1px solid #444;border-radius:6px;color:#fff;font-size:15px}
.wf select:focus,.wf input:focus{border-color:#FFD700;outline:none}
.wf button{padding:10px 16px;border:none;border-radius:6px;font-size:15px;font-weight:600;cursor:pointer}
.wb{background:#FFD700;color:#000;width:100%}
.wb:hover{background:#ffe44d}
.wsc{background:#333;color:#ccc;margin-bottom:.8em;width:100%}
.wsc:hover{background:#444}
.wm{font-size:.85em;color:#FFD700;margin-top:.5em;min-height:1.2em}
.rb{background:#8b0000;color:#fff;padding:8px 20px;border:none;border-radius:6px;
font-size:.9em;cursor:pointer;margin-top:1.5em}
.rb:hover{background:#a00}
.i{margin-top:1.5em;color:#546e7a;font-size:.85em;text-align:center}
code{background:#1a2a3a;padding:2px 6px;border-radius:4px;color:#80cbc4}
</style></head><body>
<h1>MundMaus</h1>)==";

static const char PORTAL_SETTINGS_LINK[] PROGMEM =
    R"==(<a href="/www/settings.html" style="display:inline-flex;align-items:center;gap:6px;)=="
    R"==(color:#78909c;text-decoration:none;font-size:.9em;margin-top:1.5em;padding:8px 16px;)=="
    R"==(border:1px solid #333;border-radius:8px;transition:all .2s">&#9881; Einstellungen / Settings</a>)==";

static const char PORTAL_UPDATE_SECTION[] PROGMEM = R"==(<div class="wf" id="upd" style="display:none">
<h2>Software</h2>
<div id="upd-info"></div>
<button class="wb" id="upd-btn" onclick="startUpdate()" style="display:none">&#11015; Install</button>
<div id="upd-progress" style="display:none">
<div style="background:#333;border-radius:4px;height:24px;margin:8px 0">
<div id="upd-bar" style="background:#FFD700;height:100%;border-radius:4px;width:0%;transition:width .3s"></div>
</div>
<div id="upd-file" style="font-size:.85em;color:#aaa"></div>
</div>
</div>)==";

static const char PORTAL_WIFI_FORM_BOTTOM[] PROGMEM =
    R"==(<button class="wsc" onclick="sc()">&#128269; Scan</button>)=="
    R"==(<div class="wm" id="wm"></div>)=="
    R"==(<select id="sl" onchange="document.getElementById('si').value=this.value" style="display:none"></select>)=="
    R"==(<label>SSID</label>)=="
    R"==(<input id="si" placeholder="SSID">)=="
    R"==(<label>Passwort / Password</label>)=="
    R"==(<input id="pw" type="password" placeholder="Passwort / Password">)=="
    R"==(<button class="wb" onclick="sv()">Connect</button>)=="
    R"==(</div>)==";

static const char PORTAL_REBOOT_BTN[] PROGMEM =
    R"==(<button class="rb" onclick="rb()">&#8635; Restart</button>)==";

static const char PORTAL_KEYBOARD_HINT[] PROGMEM =
    R"==(<div style="margin-top:1em;color:#546e7a;font-size:.8em">)=="
    R"==(<kbd style="background:#1a2a3a;padding:1px 5px;border-radius:3px;color:#80cbc4">&#8592;&#8593;&#8594;&#8595;</kbd> )=="
    R"==(<kbd style="background:#1a2a3a;padding:1px 5px;border-radius:3px;color:#80cbc4">&#9166;</kbd>)=="
    R"==(</div>)==";

static const char PORTAL_SCRIPT[] PROGMEM = R"==(<script>
async function sc(){document.getElementById('wm').textContent='\ud83d\udd0d...';try{const r=await fetch('/api/scan'),d=await r.json(),s=document.getElementById('sl');
s.innerHTML='<option>-- select --</option>';
d.networks.forEach(n=>{const o=document.createElement('option');o.value=n;o.textContent=n;s.appendChild(o)});
s.style.display='block';document.getElementById('wm').textContent='\u2713 '+d.networks.length}
catch(e){document.getElementById('wm').textContent='\u2717 Scan'}}
async function sv(){const s=document.getElementById('si').value,p=document.getElementById('pw').value;
if(!s)return(document.getElementById('wm').textContent='SSID!');
document.getElementById('wm').textContent='...';
try{const r=await fetch('/api/wifi',{method:'POST',headers:{'Content-Type':'application/json'},
body:JSON.stringify({ssid:s,password:p})}),d=await r.json();
document.getElementById('wm').textContent=d.message||'OK'}
catch(e){document.getElementById('wm').textContent='Fehler: '+e}}
async function rb(){if(confirm('ESP32 neu starten?')){try{await fetch('/api/reboot')}catch(e){}
document.getElementById('wm').textContent='Neustart...'}}
function showUpd(d){const el=document.getElementById('upd'),info=document.getElementById('upd-info'),btn=document.getElementById('upd-btn');if(d.offline){el.style.display='none';return}el.style.display='block';if(d.available&&d.available.length>0){info.innerHTML='\u2b07 '+d.available.length+' update'+(d.available.length>1?'s':'');btn.textContent='\u2b07 Install';btn.onclick=startUpdate;btn.style.display='block'}else{info.innerHTML='\u2713 Up to date';btn.style.display='none'}}
let _wsLost=0;
function connectWS(){const ws=new WebSocket('ws://'+location.hostname+':81');ws.onopen=function(){if(_wsLost&&(Date.now()-_wsLost)>10000)location.reload();_wsLost=0;const d=document.getElementById('ws-dot'),c=document.getElementById('ws-chip');if(d)d.style.background='#4caf50';if(c){c.style.background='rgba(76,175,80,.15)';c.style.borderColor='#4caf50'};const t=document.getElementById('ws-text');if(t)t.textContent='\u2713';fetch('/api/updates').then(r=>r.json()).then(d=>showUpd(d)).catch(()=>{})};ws.onclose=function(){if(!_wsLost)_wsLost=Date.now();const d=document.getElementById('ws-dot'),c=document.getElementById('ws-chip'),t=document.getElementById('ws-text');if(d)d.style.background='#d42a2a';if(c){c.style.background='rgba(212,42,42,.15)';c.style.borderColor='#d42a2a'};if(t)t.textContent='\u2717';setTimeout(connectWS,3000)};ws.onmessage=function(e){const d=JSON.parse(e.data);
if(d.type==='update_status'){showUpd(d)}
else if(d.type==='update_progress'){document.getElementById('upd-btn').style.display='none';document.getElementById('upd-progress').style.display='block';document.getElementById('upd-bar').style.width=(d.current/d.total*100)+'%';document.getElementById('upd-file').textContent='Datei '+d.current+'/'+d.total+': '+d.file}
else if(d.type==='update_complete'){document.getElementById('upd-progress').style.display='none';document.getElementById('upd-info').textContent=d.message;document.getElementById('upd-btn').textContent='\u21bb Restart';document.getElementById('upd-btn').style.display='block';document.getElementById('upd-btn').onclick=function(){fetch('/api/updates/check',{method:'POST'});document.getElementById('upd-info').textContent='\ud83d\udd0d...';document.getElementById('upd-btn').style.display='none'}}
else if(d.type==='update_error'){document.getElementById('upd-file').textContent='Fehler: '+d.file+' - '+d.error}
else if(d.type==='nav'&&_navItems.length){if(d.dir==='right'||d.dir==='down'){_navIdx=Math.min(_navItems.length-1,_navIdx+1)}else if(d.dir==='left'||d.dir==='up'){_navIdx=Math.max(0,_navIdx-1)}  _navUpdate()}
else if(d.type==='action'&&_navItems.length){_navItems[_navIdx].click()}};}connectWS();
fetch('/api/updates').then(r=>r.json()).then(d=>showUpd(d)).catch(()=>{});
async function startUpdate(){document.getElementById('upd-info').textContent='\u2b07...';document.getElementById('upd-btn').style.display='none';try{await fetch('/api/update/start',{method:'POST'})}catch(e){document.getElementById('upd-info').textContent='Fehler: '+e}}
let _navIdx=0;const _navItems=document.querySelectorAll('.g');
function _navUpdate(){_navItems.forEach((el,i)=>{el.style.border=i===_navIdx?'2px solid #FFD700':'2px solid rgba(255,215,0,.3)';el.style.boxShadow=i===_navIdx?'0 0 20px rgba(255,215,0,.5)':'none'})}
if(_navItems.length)_navUpdate();
document.addEventListener('keydown',function(e){if(!_navItems.length)return;if(e.key==='ArrowRight'||e.key==='ArrowDown'){_navIdx=Math.min(_navItems.length-1,_navIdx+1);_navUpdate()}else if(e.key==='ArrowLeft'||e.key==='ArrowUp'){_navIdx=Math.max(0,_navIdx-1);_navUpdate()}else if(e.key===' '||e.key==='Enter'){_navItems[_navIdx].click()}});
</script>)==";

// ============================================================
// GAME DISCOVERY
// ============================================================

struct GameEntry {
    String filename;  // e.g. "chess.html"
    String label;     // e.g. "Chess"
};

static void _discoverGames(std::vector<GameEntry>& out) {
    File root = LittleFS.open(Config::WWW_DIR);
    if (!root || !root.isDirectory()) return;

    File entry = root.openNextFile();
    while (entry) {
        String name = entry.name();
        entry.close();

        // Accept .html and .html.gz
        String raw;
        if (name.endsWith(".html.gz")) {
            raw = name.substring(0, name.length() - 8);
        } else if (name.endsWith(".html")) {
            raw = name.substring(0, name.length() - 5);
        } else {
            entry = root.openNextFile();
            continue;
        }

        // Skip index + settings
        if (raw == "index" || raw == "settings") {
            entry = root.openNextFile();
            continue;
        }

        // Friendly name
        String label;
        if (raw == "memo")           label = "Memo";
        else if (raw == "solitaire") label = "Solitaer";
        else {
            label = raw;
            label.replace("-", " ");
            label.replace("_", " ");
            if (label.length() > 0) {
                label[0] = toupper(label[0]);
            }
        }

        String htmlName = raw + ".html";

        // Deduplicate (gz + non-gz both present)
        bool exists = false;
        for (const auto& g : out) {
            if (g.filename == htmlName) { exists = true; break; }
        }
        if (!exists) {
            out.push_back({htmlName, label});
        }

        entry = root.openNextFile();
    }
    root.close();

    // Sort by label
    std::sort(out.begin(), out.end(),
              [](const GameEntry& a, const GameEntry& b) { return a.label < b.label; });
}

// ============================================================
// HW STATUS CHIP HELPER
// ============================================================

static void _appendHwChip(String& html, const char* label, bool ok) {
    const char* bgColor   = ok ? "rgba(76,175,80,.15)"  : "rgba(212,42,42,.15)";
    const char* borderClr = ok ? "#4caf50" : "#d42a2a";
    const char* dotClr    = ok ? "#4caf50" : "#d42a2a";

    html += F("<span title=\"");
    html += label;
    html += (ok ? " \xe2\x9c\x93" : " \xe2\x9c\x97");
    html += F("\" style=\"display:inline-flex;align-items:center;gap:4px;background:");
    html += bgColor;
    html += F(";border:1px solid ");
    html += borderClr;
    html += F(";border-radius:12px;padding:2px 10px;font-size:.8em\"><span style=\"width:6px;height:6px;border-radius:50%;background:");
    html += dotClr;
    html += F("\"></span>");
    html += label;
    html += F("</span>");
}

// ============================================================
// GENERATE PORTAL
// ============================================================

String generatePortal(WiFiManager& wifi, const PortalHwStatus& hw) {
    // Pre-compute WiFi values
    String modeStr  = wifi.mode;
    String ssidStr  = wifi.ssid.length() > 0 ? wifi.ssid : String(Config::AP_SSID);
    bool   connected = (modeStr == "station" && WiFi.isConnected());
    String modeLabel = (modeStr == "station") ? "WLAN" : "Hotspot";

    const char* dotColor;
    if (connected) dotColor = "#4caf50";
    else if (modeStr == "ap") dotColor = "#f0a030";
    else dotColor = "#d42a2a";

    auto [rssi, rssiLabel] = wifi.getRSSI();
    String rssiText;
    if (rssiLabel.length() > 0) {
        rssiText = " (" + rssiLabel + ", " + String(rssi) + "dBm)";
    }

    // Discover games from LittleFS
    std::vector<GameEntry> games;
    _discoverGames(games);

    // Build game buttons
    String btns;
    if (games.empty()) {
        btns = F("<p style=\"color:#78909c\">Noch keine Spiele. Lade HTML in <code>www/</code></p>");
    } else {
        for (const auto& g : games) {
            btns += "<a href=\"/www/" + g.filename + "\" class=\"g\">" + g.label + "</a>";
        }
    }

    // Free heap in KB
    uint32_t heapKB = ESP.getFreeHeap() / 1024;

    // ---- Assemble HTML ----
    String html;
    html.reserve(6144);

    // Head + title
    html += FPSTR(PORTAL_HEAD);

    // Subtitle
    html += F("<p class=\"sub\">Assistive Gaming Controller v");
    html += Config::VERSION;
    html += F("</p>");

    // Game buttons
    html += F("<div class=\"gs\">");
    html += btns;
    html += F("</div>");

    // Settings link
    html += FPSTR(PORTAL_SETTINGS_LINK);

    // Update section
    html += FPSTR(PORTAL_UPDATE_SECTION);

    // WiFi form
    html += F("<div class=\"wf\">");
    html += F("<h2><span class=\"wd\" style=\"width:10px;height:10px;border-radius:50%;background:");
    html += dotColor;
    html += F(";flex-shrink:0\"></span> ");
    html += modeLabel;
    html += F(": ");
    html += ssidStr;
    html += F(" - ");
    html += wifi.ip;
    html += rssiText;
    html += F("</h2>");
    html += FPSTR(PORTAL_WIFI_FORM_BOTTOM);

    // Reboot button
    html += FPSTR(PORTAL_REBOOT_BTN);

    // Info bar with HW chips
    html += F("<div class=\"i\" style=\"display:flex;flex-wrap:wrap;gap:8px;align-items:center;justify-content:center\">");
    html += wifi.ip;
    html += F(" | ");
    html += BOARD_NAME;
    html += F(" | v");
    html += Config::VERSION;
    html += F(" | RAM: ");
    html += String(heapKB);
    html += F("KB ");

    _appendHwChip(html, "Joystick", hw.joystick);
    _appendHwChip(html, "Puff", hw.puff);

    // WS connectivity chip (starts disconnected, JS updates it)
    html += F("<span id=\"ws-chip\" title=\"Geraet erreichbar\" style=\"display:inline-flex;align-items:center;gap:4px;"
              "background:rgba(212,42,42,.15);border:1px solid #d42a2a;border-radius:12px;padding:2px 10px;"
              "font-size:.8em\"><span id=\"ws-dot\" style=\"width:6px;height:6px;border-radius:50%;"
              "background:#d42a2a\"></span><span id=\"ws-text\">&#10007;</span></span>");

    html += F("</div>");

    // Keyboard hint
    html += FPSTR(PORTAL_KEYBOARD_HINT);

    // Script
    html += FPSTR(PORTAL_SCRIPT);

    html += F("</body></html>");

    return html;
}
