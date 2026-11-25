"""Keep the native browser close control while blocking accidental dismissal."""
import json


def explicit_close_script():
    return '''<script>
(() => {
  const host = window.parent, doc = host.document;
  host.__oneshotEditorDismissGuard?.abort();
  const guard = new host.AbortController();
  host.__oneshotEditorDismissGuard = guard;
  const dialog = doc.querySelector('[data-testid="stDialog"] [role="dialog"]');
  if (!dialog) return;
  function outside(event) {
    if (!dialog.isConnected) { guard.abort(); return; }
    const target = event.target;
    if (dialog.contains(target) || target.closest?.('[data-baseweb="popover"], [role="listbox"]')) return;
    event.preventDefault();
    event.stopImmediatePropagation();
  }
  for (const type of ['pointerdown', 'mousedown', 'mouseup', 'click', 'touchstart', 'touchend']) {
    doc.addEventListener(type, outside, {capture:true, passive:false, signal:guard.signal});
  }
  doc.addEventListener('keydown', event => {
    if (event.key === 'Escape' && dialog.isConnected) {
      event.preventDefault(); event.stopImmediatePropagation();
    }
  }, {capture:true, signal:guard.signal});
  const observer = new host.MutationObserver(() => {
    if (!dialog.isConnected) { guard.abort(); observer.disconnect(); }
  });
  observer.observe(doc.body, {childList:true, subtree:true});
  guard.signal.addEventListener('abort', () => observer.disconnect(), {once:true});
})();
</script>'''


def saved_record_script(save_id):
    """Close the saved editor and show a five-second confirmation outside it."""
    return '''<script>
(() => {
  const host = window.parent, doc = host.document;
  const saveId = __SAVE_ID__;
  if (host.__oneshotEditNoticeSaveId === saveId) {
    const dialog = window.frameElement?.closest('[role="dialog"]') || doc.querySelector('[data-testid="stDialog"] [role="dialog"]');
    dialog?.querySelector('button[aria-label="Close"]')?.click();
    return;
  }
  host.__oneshotEditNoticeSaveId = saveId;
  host.__oneshotEditNotice?.remove();
  const banner = doc.createElement('div');
  banner.textContent = 'Edits have been made';
  banner.setAttribute('role', 'status');
  banner.style.cssText = 'position:fixed;z-index:2147483647;top:22px;right:22px;max-width:min(380px,calc(100vw - 44px));padding:15px 20px;border:1px solid #73d69b;border-radius:12px;background:#dcfce7;color:#14532d;font:700 16px/1.4 system-ui,sans-serif;box-shadow:0 10px 30px #14532d26';
  doc.body.appendChild(banner);
  host.__oneshotEditNotice = banner;
  host.setTimeout(() => {
    banner.remove();
    if (host.__oneshotEditNotice === banner) host.__oneshotEditNotice = null;
  }, 5000);
  const dialog = window.frameElement?.closest('[role="dialog"]') || doc.querySelector('[data-testid="stDialog"] [role="dialog"]');
  const close = dialog?.querySelector('button[aria-label="Close"]');
  close?.click();
})();
</script>'''.replace('__SAVE_ID__', json.dumps(str(save_id)))
