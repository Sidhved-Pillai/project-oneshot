"""Keep the native browser close control while blocking accidental dismissal."""


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
