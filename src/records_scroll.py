"""Load the next batch inside the Records table as its last row approaches."""

import json


def records_scroll_script(table_key, scope, limit, has_more):
    settings = json.dumps([table_key, scope, limit, has_more])
    return """<script>
(() => {
  const [key, scope, limit, hasMore] = %s;
  const frame = window.frameElement;
  const parent = window.parent;
  const doc = parent.document;
  let observer;
  window.addEventListener('pagehide', () => observer?.disconnect(), {once: true});

  function attach() {
    if (!frame?.isConnected) return;
    const table = doc.querySelector('.st-key-' + key);
    const marker = table?.querySelector('[data-records-end="' + scope + '-' + limit + '"]');
    const next = doc.querySelector('.st-key-records_scroll_next button');
    if (!marker || (hasMore && !next)) {
      window.requestAnimationFrame(attach);
      return;
    }
    let scroller = marker.parentElement;
    while (scroller && !['auto', 'scroll'].includes(parent.getComputedStyle(scroller).overflowY)) {
      if (scroller === table.parentElement) return;
      scroller = scroller.parentElement;
    }
    if (!scroller) return;

    const registry = parent.__oneshotRecordsScroll ||= {};
    const previous = registry[key];
    const state = previous?.scope === scope ? previous : {scope};
    registry[key] = state;
    if (previous && previous !== state) scroller.scrollTop = 0;
    if (state.pending && state.pending.limit < limit) {
      if (scroller.scrollTop === 0) scroller.scrollTop = state.pending.top;
      state.pending = null;
    }
    if (!hasMore) return;

    observer = new parent.IntersectionObserver(entries => {
      if (!frame.isConnected || registry[key] !== state || !marker.isConnected) {
        observer.disconnect();
        return;
      }
      if (state.pending || !next.isConnected || next.disabled) return;
      if (!table.getClientRects().length || !entries.some(entry => entry.isIntersecting)) return;
      state.pending = {limit, top: scroller.scrollTop};
      observer.disconnect();
      next.click();
    }, {root: scroller, rootMargin: '0px 0px 160px 0px'});
    observer.observe(marker);
  }
  attach();
})();
</script>""" % settings
