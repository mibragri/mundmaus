/* MundMaus device link: the page's one WebSocket to the device (ws://<host>:81), shared by every page.

   The firmware answers every {"type":"hb"}, sent here every 2 s, so a socket that has brought nothing for
   10 s is dead whatever its readyState says. It is dropped on the spot: "connected" goes false, its
   handlers are detached, and it is closed without waiting for the closing handshake, which a dead network
   never answers. The next socket follows after a backoff of 3 s, doubling up to 30 s, back to 3 s once
   data flows again.

   DeviceLink.start({ onMessage(msg), onChange(connected) })   once per page
   DeviceLink.send(obj)     true if handed to an open socket
   DeviceLink.connected     data flows: the current socket has brought a message
   DeviceLink.silentOpens   sockets in a row that opened and were dropped without a single message
   DeviceLink.retryNow()    skip the rest of the backoff (conn-guard.js, once HTTP answers again) */
(function () {
  'use strict';
  if (window.DeviceLink) return;

  var HB_MS = 2000, DEAD_MS = 10000, BACKOFF_MIN_MS = 3000, BACKOFF_MAX_MS = 30000;

  var handlers = null;
  var sock = null;        // the current socket; a dropped one is detached and forgotten
  var opened = false;     // the current socket fired open
  var heard = false;      // ... and brought at least one message
  var lastSign = 0;       // ms of its creation, its open or its last message
  var backoff = BACKOFF_MIN_MS;
  var retryTimer = null;

  var link = {
    connected: false,
    silentOpens: 0,
    start: function (h) {
      if (handlers) return;
      handlers = h || {};
      connect();
      setInterval(heartbeat, HB_MS);
      setInterval(watch, 1000);
    },
    send: function (obj) {
      if (!sock || sock.readyState !== 1) return false;
      try { sock.send(JSON.stringify(obj)); return true; } catch (e) { return false; }
    },
    retryNow: function () {
      if (sock || !retryTimer) return;   // a socket is on its way, or start() has not run
      clearTimeout(retryTimer);
      connect();
    }
  };
  window.DeviceLink = link;

  function setConnected(on) {
    if (link.connected === on) return;
    link.connected = on;
    if (handlers.onChange) handlers.onChange(on);
  }

  function connect() {
    retryTimer = null;
    opened = false;
    heard = false;
    lastSign = Date.now();
    var s;
    try {
      s = new WebSocket('ws://' + (location.hostname || '192.168.4.1') + ':81');
    } catch (e) {
      console.warn('[DeviceLink] WebSocket constructor failed:', e);
      retry();
      return;
    }
    sock = s;
    s.onopen = function () { opened = true; lastSign = Date.now(); };
    s.onmessage = function (ev) {
      lastSign = Date.now();
      if (!heard) {
        heard = true;
        link.silentOpens = 0;
        backoff = BACKOFF_MIN_MS;
        setConnected(true);
      }
      var msg;
      try { msg = JSON.parse(ev.data); } catch (e) { console.warn('[DeviceLink] not JSON:', ev.data); return; }
      if (handlers.onMessage) handlers.onMessage(msg);
    };
    s.onclose = s.onerror = function () { if (s === sock) drop(); };
  }

  function drop() {
    var s = sock;
    sock = null;
    if (s) {
      s.onopen = s.onmessage = s.onclose = s.onerror = null;
      try { s.close(); } catch (e) { console.warn('[DeviceLink] close failed:', e); }
      if (opened && !heard) link.silentOpens++;
    }
    setConnected(false);
    retry();
  }

  function retry() {
    clearTimeout(retryTimer);
    retryTimer = setTimeout(connect, backoff);
    backoff = Math.min(backoff * 2, BACKOFF_MAX_MS);
  }

  function heartbeat() {
    if (!sock || sock.readyState !== 1) return;
    try { sock.send('{"type":"hb"}'); } catch (e) { console.warn('[DeviceLink] heartbeat failed:', e); }
  }

  function watch() {
    if (sock && Date.now() - lastSign > DEAD_MS) drop();
  }
})();
