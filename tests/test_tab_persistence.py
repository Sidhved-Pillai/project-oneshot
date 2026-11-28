import shutil
import subprocess

import pytest

from src.tab_persistence import tab_persistence_script


def test_top_level_tab_click_updates_url_without_navigation():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is needed for browser event simulation')
    script = tab_persistence_script().removeprefix('<script>').removesuffix('</script>')
    harness = '''
const assert = require('node:assert/strict');
let click, replaced='';
const tab={textContent:'Records'};
const list={contains:item=>item===tab};
const doc={querySelector:()=>list,addEventListener:(name,handler)=>{if(name==='click')click=handler}};
const host={document:doc,AbortController,URL,location:{href:'https://example.com/?member_session=token'},
 history:{state:null,replaceState(_state,_title,url){replaced=String(url)}}};
global.window={parent:host};
'''
    checks = '''
click({target:{closest:()=>tab}});
assert.equal(new URL(replaced).searchParams.get('oneshot_tab'),'Records');
assert.equal(new URL(replaced).searchParams.get('member_session'),'token');
'''
    subprocess.run([node, '-e', harness + script + checks], check=True)
