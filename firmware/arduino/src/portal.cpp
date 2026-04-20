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
body{font-family:system-ui,sans-serif;background:#000000;color:#e0e0e0;
min-height:100vh;display:flex;flex-direction:column;align-items:center;padding:2em}
h1{font-size:clamp(2em,5vw,3.5em);color:#76FF03;margin-bottom:.2em}
.gs{display:flex;flex-wrap:wrap;gap:1.5em;justify-content:center;max-width:800px}
.g{display:flex;align-items:center;justify-content:center;width:220px;height:120px;
background:linear-gradient(135deg,#1a1a1a,#111111);border:2px solid rgba(118,255,3,.3);border-radius:16px;
color:#76FF03;font-size:1.3em;font-weight:600;text-decoration:none;transition:all .2s}
.g:hover{border-color:#76FF03;transform:scale(1.05);box-shadow:0 0 20px rgba(118,255,3,.3)}
.upd-btn{display:none;width:100%;max-width:500px;padding:16px;margin-bottom:1.5em;margin-top:0.5em;
background:#76FF03;color:#000;border:none;border-radius:12px;font-size:1.2em;
font-weight:700;cursor:pointer;text-align:center}
.upd-btn:hover{background:#a0ff50}
.upd-bar{background:#333;border-radius:4px;height:20px;margin:8px 0;max-width:500px;width:100%;display:none}
.upd-fill{background:#FFD700;height:100%;border-radius:4px;width:0%;transition:width .3s}
.upd-status{font-size:.85em;color:#aaa;margin-bottom:1em;display:none}
.settings-gear{position:fixed;bottom:1.5em;right:1.5em;color:#76FF03;
font-size:1.5em;text-decoration:none;transition:color .2s}
.settings-gear:hover{color:rgba(255,255,255,0.6)}
.health-alert{display:none;width:100%;max-width:500px;padding:12px 16px;margin-bottom:1em;
background:linear-gradient(135deg,#4a2a00,#2a1a00);border:2px solid #ff9800;border-radius:12px;
color:#ffcc80;font-size:.95em;line-height:1.4;text-align:center}
.health-alert.crit{background:linear-gradient(135deg,#4a0000,#2a0000);border-color:#f44336;color:#ffcdd2}
.wifi-status{display:none;position:fixed;bottom:1.5em;left:1.5em;font-size:.75em;color:#888;
font-family:ui-monospace,SFMono-Regular,monospace;letter-spacing:.02em;line-height:1.5;
max-width:calc(100vw - 12em);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.wifi-status .ok{color:#7ccf7c}
.wifi-status .warn{color:#ffcc80}
.wifi-status .crit{color:#ff8a80}
</style></head><body>
<h1>MundMaus</h1>)==";

// Settings gear + version — assembled dynamically in generatePortal()

static const char PORTAL_UPDATE_SECTION[] PROGMEM =
    R"==(<div class="health-alert" id="health-alert"></div>)=="
    R"==(<button class="upd-btn" id="upd-btn" onclick="startUpdate()">&#128260; Aktualisieren</button>)=="
    R"==(<div class="upd-bar" id="upd-bar-wrap"><div class="upd-fill" id="upd-fill"></div></div>)=="
    R"==(<div class="upd-status" id="upd-status"></div>)=="
    R"==(<div class="wifi-status" id="wifi-status"></div>)==";

static const char PORTAL_SCRIPT[] PROGMEM = R"==(<script>
function showUpd(d){
  var btn=document.getElementById('upd-btn');
  if(!d.offline && d.available && d.available.length>0){
    btn.style.display='block';
  } else {
    btn.style.display='none';
  }
}
var _updating=false;
function _fadeOut(){
  var o=document.getElementById('fade-overlay');
  if(!o){o=document.createElement('div');o.id='fade-overlay';
    o.style.cssText='position:fixed;top:0;left:0;width:100%;height:100%;background:#000;opacity:0;transition:opacity 0.8s;z-index:9999;display:flex;align-items:center;justify-content:center;color:#FFD700;font-size:3vh;font-family:system-ui';
    o.textContent='\u23f3 Neustart...';document.body.appendChild(o);}
  requestAnimationFrame(function(){o.style.opacity='1';});
  // Fallback: force reload after 15s in case WS reconnect fails
  setTimeout(function(){location.reload();},15000);
}
function connectWS(){
  var ws=new WebSocket('ws://'+location.hostname+':81');
  ws.onopen=function(){
    if(_updating){location.reload();return;}
    fetch('/api/updates/check',{method:'POST'}).catch(function(){});
  };
  ws.onclose=function(){
    if(_updating) _fadeOut();
    setTimeout(connectWS,3000);
  };
  ws.onmessage=function(e){
    var d=JSON.parse(e.data);
    if(d.type==='update_status') showUpd(d);
    else if(d.type==='update_progress'){
      _updating=true;
      document.getElementById('upd-btn').style.display='none';
      document.getElementById('upd-bar-wrap').style.display='block';
      document.getElementById('upd-fill').style.width=(d.current/d.total*100)+'%';
      document.getElementById('upd-status').style.display='block';
      document.getElementById('upd-status').textContent='Aktualisierung l\u00e4uft...';
    }
    else if(d.type==='update_complete'){
      document.getElementById('upd-fill').style.width='100%';
      _updating=true;
      _fadeOut();
      setTimeout(function(){fetch('/api/reboot').catch(function(){})},1500);
    }
    else if(d.type==='update_error'){
      document.getElementById('upd-status').textContent='\u2717 Fehler: '+d.file;
      _updating=false;
    }
    else if(d.type==='nav'&&_navItems.length){
      if(d.dir==='right'||d.dir==='down') _navIdx=Math.min(_navItems.length-1,_navIdx+1);
      else if(d.dir==='left'||d.dir==='up') _navIdx=Math.max(0,_navIdx-1);
      _navUpdate();
    }
    else if(d.type==='action'&&_navItems.length){_navItems[_navIdx].click()}
  };
}
connectWS();
// Initial check triggered via WS onopen → /api/updates/check
// Power-supply health + WiFi status: fetch once at load. Always show the
// compact status bar (bottom-left, monospace, dezent) so the operator can
// read RSSI / brownout-count / TX-level at a glance even when nothing is
// wrong. Show the loud alert banner on top only when the firmware has
// already stepped TX-power down or has logged brownouts.
fetch('/api/wifi-status').then(function(r){return r.json();}).then(function(d){
  if(!d) return;
  var txLabels=['15 dBm','13 dBm','11 dBm','8.5 dBm','7 dBm'];
  var tx=txLabels[d.tx_level]||('lvl '+d.tx_level);
  // Human-readable WiFi quality: 4-bar visual + plain-German label + dBm.
  // Thresholds tuned for our actual use-case: HTTP portal + WebSocket nav.
  // This is a control-plane workload (tiny messages, no video/streaming),
  // so it keeps working reliably much further into "bad" RSSI than common
  // router dashboards suggest — we only warn once the link is actually
  // starting to risk nav-event drops.
  var rssi=d.rssi;
  var bars, word, rssiClass;
  if(rssi>=-55)       { bars='\u25ae\u25ae\u25ae\u25ae'; word='Ausgezeichnet'; rssiClass='ok';   }
  else if(rssi>=-65)  { bars='\u25ae\u25ae\u25ae\u2b1a'; word='Sehr gut';      rssiClass='ok';   }
  else if(rssi>=-75)  { bars='\u25ae\u25ae\u2b1a\u2b1a'; word='Gut';           rssiClass='ok';   }
  else if(rssi>=-82)  { bars='\u25ae\u2b1a\u2b1a\u2b1a'; word='Ausreichend';   rssiClass='warn'; }
  else                { bars='\u2b1a\u2b1a\u2b1a\u2b1a'; word='Schwach';       rssiClass='crit'; }
  var boClass=(d.brownout_total===0)?'ok':(d.brownout_total<5)?'warn':'crit';
  var txClass=(d.tx_level===0)?'ok':(d.tx_level<3)?'warn':'crit';
  var s=document.getElementById('wifi-status');
  s.innerHTML='<span class="'+rssiClass+'">'+bars+' '+word+'</span> <span style="opacity:.6">('+rssi+' dBm)</span>'+
              ' \u2022 \u26a1 <span class="'+boClass+'">'+d.brownout_total+' Brownouts</span>'+
              ' \u2022 TX <span class="'+txClass+'">'+tx+'</span>';
  s.style.display='block';
  if(d.health_hint){
    var a=document.getElementById('health-alert');
    a.textContent='\u26a0 '+d.health_hint+' (Brownouts gesamt: '+d.brownout_total+')';
    if(d.tx_level>=3) a.classList.add('crit');
    a.style.display='block';
  }
}).catch(function(){});
async function startUpdate(){
  _updating=true;
  document.getElementById('upd-btn').textContent='\u231b...';
  document.getElementById('upd-btn').disabled=true;
  document.getElementById('upd-status').style.display='block';
  document.getElementById('upd-status').textContent='Starte...';
  try{await fetch('/api/update/start',{method:'POST'})}
  catch(e){document.getElementById('upd-status').textContent='Fehler';_updating=false;}
}
var _navIdx=0;
var _navItems=document.querySelectorAll('.g');
function _navUpdate(){
  _navItems.forEach(function(el,i){
    el.style.border=i===_navIdx?'4px solid #00e5ff':'2px solid rgba(118,255,3,.3)';
    el.style.boxShadow=i===_navIdx?'0 0 24px rgba(0,229,255,.6)':'none';
  });
}
if(_navItems.length) _navUpdate();
document.addEventListener('keydown',function(e){
  if(!_navItems.length)return;
  if(e.key==='ArrowRight'||e.key==='ArrowDown'){_navIdx=Math.min(_navItems.length-1,_navIdx+1);_navUpdate()}
  else if(e.key==='ArrowLeft'||e.key==='ArrowUp'){_navIdx=Math.max(0,_navIdx-1);_navUpdate()}
  else if(e.key===' '||e.key==='Enter'){_navItems[_navIdx].click()}
});
</script>)==";

// ============================================================
// GAME DISCOVERY
// ============================================================

struct GameEntry {
    String filename;  // e.g. "chess.html"
    String label;     // e.g. "Chess"
};

static void discoverGames(std::vector<GameEntry>& out) {
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
        else if (raw == "muehle")    label = "Muehle";
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
// GENERATE PORTAL
// ============================================================

String generatePortal(WiFiManager& wifi, const PortalHwStatus& hw) {
    (void)wifi;
    (void)hw;

    // Discover games from LittleFS
    std::vector<GameEntry> games;
    discoverGames(games);

    // Build game buttons
    String btns;
    for (const auto& g : games) {
        btns += "<a href=\"/www/" + g.filename + "\" class=\"g\">" + g.label + "</a>";
    }

    // ---- Assemble HTML ----
    String html;
    html.reserve(4096);

    // Head + title
    html += FPSTR(PORTAL_HEAD);

    // Update section (hidden by default, shown by JS if updates available)
    // Placed ABOVE the game grid so it's the first thing the user sees
    html += FPSTR(PORTAL_UPDATE_SECTION);

    // Game buttons
    html += F("<div class=\"gs\">");
    html += btns;
    html += F("</div>");

    // Settings gear + version (fixed bottom-right)
    html += F("<div class=\"settings-gear\"><span style=\"font-size:.6em;opacity:.6;margin-right:8px\">v");
    html += Config::VERSION;
    html += F("</span><a href=\"/www/settings.html\" style=\"color:inherit;text-decoration:none\">&#9881;</a>"
              " <span onclick=\"location.reload()\" style=\"cursor:pointer;margin-left:8px\">&#8635;</span></div>");

    // Script
    html += FPSTR(PORTAL_SCRIPT);

    html += F("</body></html>");

    return html;
}
