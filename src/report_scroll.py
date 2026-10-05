"""Presentation-only scroll positioning for the live report grids."""

import json


def latest_rows_scroll_script(container_key, signature):
    """Start at the last row on opening a report, without resetting manual scrolling."""
    return """<script>
(() => {
  const key = %s, signature = %s;
  const doc = window.parent.document;
  const registry = window.parent.__oneshotReportScroll ||= {};
  Object.keys(registry).filter(other => other !== key).forEach(other => {
    registry[other].visible = false;
  });
  const state = registry[key] ||= {visible: false, signature: null};
  const timer = setInterval(() => {
    if (!window.frameElement?.isConnected) { clearInterval(timer); return; }
    const grid = doc.querySelector('.st-key-' + key);
    const visible = !!grid && grid.getBoundingClientRect().height > 0 &&
      window.parent.getComputedStyle(grid).visibility !== 'hidden';
    if (!visible) { state.visible = false; return; }
    const canvas = grid.querySelector('canvas');
    if (!canvas) return;
    let scroller = grid.querySelector('.dvn-scroller');
    if (!scroller) {
      scroller = Array.from(grid.querySelectorAll('div')).find(el =>
        el.scrollHeight > el.clientHeight && el.clientHeight > 0 &&
        ['auto', 'scroll'].includes(window.parent.getComputedStyle(el).overflowY));
    }
    if (!scroller || scroller.clientHeight === 0) return;
    if (!state.visible || state.signature !== signature) {
      scroller.scrollTo({top: scroller.scrollHeight, behavior: 'instant'});
      state.signature = signature;
    }
    state.visible = true;
  }, 200);
})();
</script>""" % (json.dumps(container_key), json.dumps(signature))
