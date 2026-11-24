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


def test_saved_record_closes_dialog_and_removes_green_notice_after_five_seconds():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is needed for browser event simulation')
    script = saved_record_script().removeprefix('<script>').removesuffix('</script>')
    harness = '''
const assert = require('node:assert/strict');
let closed=0, delay, expiry;
const close={click(){closed++}};
const dialog={querySelector:()=>close};
const body={appendChild(element){this.banner=element}};
const doc={body, createElement:()=>({style:{},setAttribute(){},remove(){this.removed=true}})};
global.window={parent:{document:doc,setTimeout(fn,ms){expiry=fn;delay=ms}},
  frameElement:{closest:()=>dialog}};
'''
    checks = '''
assert.equal(closed,1);
assert.equal(body.banner.textContent,'Edits have been made');
assert.match(body.banner.style.cssText,/background:#dcfce7/);
assert.equal(delay,5000);
expiry();
assert.equal(body.banner.removed,true);
'''
    subprocess.run([node, '-e', harness + script + checks], check=True, capture_output=True, text=True)
