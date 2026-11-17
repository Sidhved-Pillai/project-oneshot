"""Presentation-only scroll positioning for the live report grids."""

import json
from pathlib import Path


def latest_rows_scroll_script(container_key, signature):
    """Start at the last row on opening a report, without resetting manual scrolling."""
    assets = Path(__file__).with_name('rtgs_grid_component')
    css = (assets / 'scrollbars.css').read_text()
    javascript = (assets / 'scrollbars.js').read_text()
    return '<script>' + javascript + '</script>' + """<script>
(() => {
  const key = %s, signature = %s;
  const doc = window.parent.document;
  if (!doc.getElementById('oneshot-report-scrollbar-style')) {
    const style = doc.createElement('style');
    style.id = 'oneshot-report-scrollbar-style';
    style.textContent = %s;
    doc.head.append(style);
  }
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
    grid.style.position = 'relative';
    grid.style.paddingRight = '20px';
    grid.style.paddingBottom = '20px';
    window.installReportScrollbars(grid, scroller);
    if (!state.visible || state.signature !== signature) {
      scroller.scrollTo({top: scroller.scrollHeight, behavior: 'instant'});
      state.signature = signature;
    }
    state.visible = true;
  }, 200);
})();
</script>""" % (json.dumps(container_key), json.dumps(signature), json.dumps(css + '\n.st-key-' + container_key + ' .dvn-scroller{scrollbar-width:none!important}.st-key-' + container_key + ' .dvn-scroller::-webkit-scrollbar{display:none!important}'))
