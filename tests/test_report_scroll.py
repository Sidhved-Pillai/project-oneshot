import shutil
import subprocess

import pytest

from src.report_scroll import latest_rows_scroll_script


def test_report_scroll_opens_at_bottom_but_preserves_manual_scroll():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is needed for the scroll controller browser mock")
    script = latest_rows_scroll_script("report_dtr_grid", "rows-1")
    script = script.split("</script><script>", 1)[1].removesuffix("</script>")
    harness = """
const assert = require('node:assert/strict');
let tick, visible = true, calls = 0, disconnected = false;
const scroller = {clientHeight: 400, scrollHeight: 1600, scrollTop: 0,
  scrollTo({top}) { this.scrollTop = top; calls++; }};
const grid = {style: {}, getBoundingClientRect: () => ({height: visible ? 400 : 0}),
  querySelector: selector => selector === 'canvas' ? {} : scroller};
global.window = {installReportScrollbars: () => {}, frameElement: {isConnected: true}, parent: {
  document: {querySelector: () => grid, getElementById: () => ({})}, getComputedStyle: () => ({visibility:'visible'})}};
global.setInterval = callback => { tick = callback; return 1; };
global.clearInterval = () => { disconnected = true; };
""" + script + """
tick(); assert.equal(scroller.scrollTop, 1600); assert.equal(calls, 1);
scroller.scrollTop = 200; tick(); assert.equal(scroller.scrollTop, 200);
visible = false; tick(); visible = true; tick(); assert.equal(calls, 2);
""" + script + """
scroller.scrollTop = 100; tick(); assert.equal(scroller.scrollTop, 100);
window.parent.__oneshotReportScroll.report_dtr_grid.signature = 'old-rows';
tick(); assert.equal(calls, 3);
window.frameElement.isConnected = false; tick(); assert.equal(disconnected, true);
"""
    subprocess.run([node, "-e", harness], check=True, capture_output=True, text=True)
