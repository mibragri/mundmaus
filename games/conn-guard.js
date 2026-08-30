/* MundMaus connection guard.
   Shows a caretaker-facing overlay when the device becomes unreachable for a
   sustained period, so a WiFi/router outage turns into a clear, actionable
   instruction instead of a frozen screen. Self-contained: injects its own
   styles + DOM and polls /api/info. Included on every served page via a single
   <script src="conn-guard.js"> tag (relative: resolves to /www/ on the device,
   and to games/ under the local test server).

   Inert on localhost -- there is no device to lose there, and it keeps the local
   game tests clean. Tunable for tests via window.__mmConnGuardConfig set before
   this script runs (pollMs, timeoutMs, thresholdMs, pingUrl, force). */
(function () {
  'use strict';
  if (window.__mmConnGuard) return;            // double-init guard
  window.__mmConnGuard = true;

  var cfg = window.__mmConnGuardConfig || {};
  var host = location.hostname;
  var isLocal = host === 'localhost' || host === '127.0.0.1' || host === '::1' || host === '';
  if (isLocal && cfg.force !== true) return;   // no-op in local/dev

  var POLL_MS      = cfg.pollMs      || 5000;
  var TIMEOUT_MS   = cfg.timeoutMs   || 3000;
  var THRESHOLD_MS = cfg.thresholdMs || 25000; // above a self-heal reboot (~10-15s) so a normal reboot never alarms
  var PING_URL     = cfg.pingUrl     || '/api/info';

  var downSince = null;   // ms of the first failed poll in the current outage; null while reachable
  var shown = false;
  var overlay = null;

  function inject() {
    var style = document.createElement('style');
    style.textContent = [
      '#mm-conn-lost{position:fixed;inset:0;z-index:2147483000;display:none;',
      'align-items:center;justify-content:center;background:rgba(8,10,20,.85);',
      'pointer-events:none;font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}',
      '#mm-conn-lost.mm-on{display:flex}',
      '.mm-cl-card{max-width:600px;width:calc(100% - 80px);background:#1a1a2e;color:#fff;',
      'border:3px solid #ffb300;border-radius:18px;padding:44px 48px;text-align:center;',
      'box-shadow:0 14px 56px rgba(0,0,0,.6)}',
      '.mm-cl-ic{font-size:68px;line-height:1}',
      '.mm-cl-tt{font-size:32px;font-weight:800;margin:18px 0 10px;letter-spacing:.5px}',
      '.mm-cl-ms{font-size:23px;line-height:1.45;color:#fff}',
      '.mm-cl-hi{color:#ffd54a;font-weight:700}',
      '.mm-cl-sb{font-size:19px;margin-top:26px;color:#a9c2e0}',
      '.mm-cl-dots{display:inline-block;margin-left:6px}',
      '.mm-cl-dots i{display:inline-block;width:10px;height:10px;margin:0 3px;border-radius:50%;',
      'background:#ffb300;opacity:.3;animation:mm-blink 1.2s infinite}',
      '.mm-cl-dots i:nth-child(2){animation-delay:.2s}',
      '.mm-cl-dots i:nth-child(3){animation-delay:.4s}',
      '@keyframes mm-blink{0%,100%{opacity:.3}50%{opacity:1}}'
    ].join('');
    overlay = document.createElement('div');
    overlay.id = 'mm-conn-lost';
    overlay.setAttribute('role', 'alert');
    // Static text only -- no interpolation, nothing from the network.
    overlay.innerHTML =
      '<div class="mm-cl-card">' +
        '<div class="mm-cl-ic">&#9888;</div>' +
        '<div class="mm-cl-tt">KEINE VERBINDUNG ZUR MUNDMAUS</div>' +
        '<div class="mm-cl-ms">Bitte den WLAN-Router (<span class="mm-cl-hi">FRITZ!Box</span>) ' +
        'aus- und wieder einschalten<br>und etwa 1 Minute warten.</div>' +
        '<div class="mm-cl-sb">Verbindung wird automatisch wiederhergestellt' +
        '<span class="mm-cl-dots"><i></i><i></i><i></i></span></div>' +
      '</div>';
    document.head.appendChild(style);
    document.body.appendChild(overlay);
  }

  function show() { if (!shown) { shown = true; overlay.classList.add('mm-on'); } }
  function hide() { if (shown) { shown = false; overlay.classList.remove('mm-on'); } }

  function onOk()   { downSince = null; hide(); }
  function onFail() {
    if (downSince === null) downSince = Date.now();
    if (Date.now() - downSince >= THRESHOLD_MS) show();
  }

  function poll() {
    var ctrl = new AbortController();
    var t = setTimeout(function () { ctrl.abort(); }, TIMEOUT_MS);
    fetch(PING_URL, { method: 'GET', cache: 'no-store', signal: ctrl.signal })
      .then(function (r) { clearTimeout(t); if (r && r.ok) onOk(); else onFail(); })
      .catch(function ()  { clearTimeout(t); onFail(); });
  }

  function start() {
    inject();
    poll();                    // check immediately, then on an interval
    setInterval(poll, POLL_MS);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
})();
