"""Remember the active top-level tab in the current browser URL."""


def tab_persistence_script():
    return '''<script>
(() => {
  const host = window.parent, doc = host.document;
  host.__oneshotTabPersistence?.abort();
  const guard = new host.AbortController();
  host.__oneshotTabPersistence = guard;
  function remember(tab) {
    const list = doc.querySelector('[data-testid="stTabs"] [data-baseweb="tab-list"]');
    if (!tab || !list?.contains(tab)) return;
    const name = tab.textContent.trim();
    if (!name) return;
    const url = new host.URL(host.location.href);
    url.searchParams.set('oneshot_tab', name);
    host.history.replaceState(host.history.state, '', url);
  }
  doc.addEventListener('click', event => {
    remember(event.target.closest?.('[data-testid="stTab"]'));
  }, {capture:true, signal:guard.signal});
  doc.addEventListener('keydown', event => {
    const tab = event.target.closest?.('[data-testid="stTab"]');
    if (tab && ['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) {
      host.setTimeout(() => remember(doc.querySelector('[data-testid="stTabs"] [data-testid="stTab"][aria-selected="true"]')), 0);
    }
  }, {signal:guard.signal});
})();
</script>'''
