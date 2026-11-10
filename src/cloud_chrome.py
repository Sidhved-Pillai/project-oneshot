"""Hide only Community Cloud's floating owner-management button."""
import streamlit as st
import streamlit.components.v1 as components

MANAGE_APP_CSS = '[data-testid="manage-app-button"]{display:none!important;}'


def manage_app_script():
    # Community Cloud hosts the app inside a same-origin iframe. A component
    # starts one level deeper; install the narrow rule in accessible ancestors.
    # A stylesheet also handles buttons that Cloud mounts after this script runs.
    return '''<script>
(() => {
  let frame = window.parent;
  for (let level = 0; level < 4; level++) {
    try {
      const doc = frame.document;
      const id = 'oneshot-hide-manage-app';
      let style = doc.getElementById(id);
      if (!style) {
        style = doc.createElement('style');
        style.id = id;
        (doc.head || doc.documentElement).appendChild(style);
      }
      style.textContent = '[data-testid="manage-app-button"]{display:none!important;}';
      if (frame.parent === frame) break;
      frame = frame.parent;
    } catch (_) {
      // A different-origin host cannot be styled; leave it untouched.
      break;
    }
  }
})();
</script>'''


def hide_manage_app():
    st.markdown(f'<style>{MANAGE_APP_CSS}</style>', unsafe_allow_html=True)
    components.html(manage_app_script(), height=0, scrolling=False)
