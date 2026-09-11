"""Behavior parity through the actual shipped entrypoints, outside checkout."""
import contextlib
import io
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

from dcore.release.bundle_cli import build as build_cli
from dcore.release.bundle_gpt import build as build_gpt
from dcore.release.bundle_skill import build as build_skill

ROOT = Path(__file__).resolve().parents[1]


def test_independent_delivery_findings_and_retrieval(tmp_path):
    work = ROOT / '.dcore-work'
    work.mkdir(exist_ok=True)
    cli, gpt, skill = work/'parity-cli', work/'parity-gpt', work/'parity-skill.zip'
    build_cli(ROOT, cli)
    build_gpt(ROOT, gpt)
    with contextlib.redirect_stdout(io.StringIO()):
        build_skill(ROOT, skill)
    # Only shipped files enter this directory; -I -S removes PYTHONPATH and
    # site packages. The worker rejects any dCore import from the checkout.
    shutil.copytree(cli, tmp_path/'cli')
    shutil.copytree(gpt/'Knowledge', tmp_path/'gpt')
    with zipfile.ZipFile(skill) as archive:
        archive.extractall(tmp_path/'skill')
    project = tmp_path/'project'
    project.mkdir()
    (project/'events.dsc').write_text('scope:\n  type: world\n  events:\n    on player right clicks entity:\n    # has_flag[owned]\n    - narrate <player.flag[other]>\n    - determine cancelled\n')
    (project/'worker.dsc').write_text('worker:\n  type: task\n  script:\n  - run finish\n  - run <[dynamic]>\n  - while true:\n    - wait 1t\n    - narrate session\n')
    (project/'finish.dsc').write_text('finish:\n  type: task\n  script:\n  - stop\n')
    worker = tmp_path/'worker.py'
    worker.write_text('''import contextlib,io,json,pathlib,runpy,sys
base=pathlib.Path(__file__).parent
kind=sys.argv[1]
if kind=='gpt':
    api=runpy.run_path(str(base/'gpt/dcore_bootstrap.py'))
    main=api['initialize'](base/'gpt')
elif kind=='skill':
    main=runpy.run_path(str(base/'skill/dcore/scripts/dcore.py'))['main']
else:
    main=runpy.run_path(str(base/'cli/dcore.py'))['main']
import dcore
assert pathlib.Path(dcore.__file__).resolve().is_relative_to(base)
pack=base/'modern-pack'
(pack/'assets/test/post_effect').mkdir(parents=True,exist_ok=True)
(pack/'pack.mcmeta').write_text(json.dumps({'pack':{'min_format':75,'max_format':75}}))
(pack/'assets/test/post_effect/test.json').write_text(json.dumps({'targets':{'swap':{}},'passes':[{'vertex_shader':'minecraft:core/screenquad','fragment_shader':'minecraft:post/blit','inputs':[{'sampler_name':'In','target':'minecraft:main'}],'output':'swap','uniforms':{}}]}))
output=[]
for args in [
    ['lint',str(base/'project'),'--minecraft','1.16.5','--profile','denizen','--denizen-version','1.2.6-b1782','--json'],
    ['retrieve','--meta-query','flag','--profile','denizen','--denizen-version','1.2.6-b1782'],
    ['lint-pack',str(pathlib.Path(dcore.__file__).parent/'examples/visual/outline-scene-blur'),
     '--minecraft','1.21.8','--pack-format','64','--graphics-mode','fancy','--json'],
    ['lint-pack',str(pack),'--minecraft','1.21.11','--json'],
    ['versions','--minecraft-profiles']]:
    text=io.StringIO()
    with contextlib.redirect_stdout(text):
        status=main(args)
    output.append([status,json.loads(text.getvalue())])
print(json.dumps(output,sort_keys=True))
''')
    results=[]
    for delivery in ('cli','skill','gpt'):
        process=subprocess.run([sys.executable,'-I','-S',str(worker),delivery],cwd=tmp_path,
                               capture_output=True,text=True,encoding='utf-8',timeout=90)
        assert process.returncode == 0, process.stderr
        payload=json.loads(process.stdout)
        # The report labels the pack's physical location, which differs by delivery.
        serialized=json.dumps(payload)
        for location in (tmp_path/'cli/runtime',tmp_path/'skill/dcore/runtime',tmp_path/'gpt/dcore_runtime'):
            serialized=serialized.replace(str(location).replace('\\','\\\\'),'<runtime>')
        results.append(json.loads(serialized))
    assert results[0] == results[1] == results[2]
    assert 'broad_cancel_without_identity_guard' in json.dumps(results[0][0])
    assert 'unproven_loop_bound' in json.dumps(results[0][0])
    assert results[0][3][0] == 0
    assert not results[0][3][1]['issues']
    assert len(results[0][4][1]['profiles']) == 34
    assert '1.16.5' in results[0][4][1]['profiles'] and '26.2' in results[0][4][1]['profiles']
    assert results[0][1][1]['matches'], 'Actual portable database query must return API evidence'
    for path in (cli,gpt):
        assert path.resolve().parent == work.resolve()
        shutil.rmtree(path)
    skill.unlink()
