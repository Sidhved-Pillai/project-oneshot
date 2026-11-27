import shutil
import subprocess

import pytest
from src.dialog_browser import explicit_close_script, saved_record_script


def test_native_cross_passes_through_but_backdrop_and_escape_are_blocked():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is needed for browser event simulation')
    script = explicit_close_script().removeprefix('<script>').removesuffix('</script>')
    harness = '''
const assert = require('node:assert/strict');
const listeners = {};
const dialog = {isConnected:true, contains:target=>target.inside === true};
const doc = {body:{}, querySelector:()=>dialog,
  addEventListener:(type,fn)=>{listeners[type]=fn}};
global.window = {parent:{document:doc, AbortController,
  MutationObserver:class {observe(){} disconnect(){}}}};
'''
    checks = '''
function event(target,key) {return {target,key,blocked:false,
  preventDefault(){this.blocked=true},stopImmediatePropagation(){this.stopped=true}}}
let cross=event({inside:true}); listeners.click(cross); assert.equal(cross.blocked,false);
let backdrop=event({}); listeners.click(backdrop); assert.equal(backdrop.blocked,true);
let dropdown=event({closest:()=>true}); listeners.click(dropdown); assert.equal(dropdown.blocked,false);
let escape=event({},'Escape'); listeners.keydown(escape); assert.equal(escape.blocked,true);
dialog.isConnected=false;
let next=event({}); listeners.click(next); assert.equal(next.blocked,false);
assert.equal(window.parent.__oneshotEditorDismissGuard.signal.aborted,true);
'''
    subprocess.run([node, '-e', harness + script + checks], check=True, capture_output=True, text=True)


def test_saved_record_closes_dialog_even_if_close_control_renders_late():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is needed for browser event simulation')
    script = saved_record_script('save-1').removeprefix('<script>').removesuffix('</script>')
    harness = '''
const assert = require('node:assert/strict');
let closed=0, delay, retry, scheduled=0, ready=false;
const close={click(){closed++}};
const dialog={querySelector:()=>ready ? close : null};
const doc={querySelector:()=>dialog};
global.window={parent:{document:doc,setTimeout(fn,ms){retry=fn;delay=ms;scheduled++}},
  frameElement:{closest:()=>dialog}};
'''
    checks = '''
assert.equal(closed,0);
assert.equal(scheduled,1);
assert.equal(delay,50);
ready=true;
retry();
assert.equal(closed,1);
assert.equal(scheduled,1);
'''
    subprocess.run([node, '-e', harness + script + checks],
                   check=True, capture_output=True, text=True)
