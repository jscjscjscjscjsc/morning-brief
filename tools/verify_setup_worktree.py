"""Recheck the team's stale-worktree patch against exact upstream bytes, offline."""
import argparse,json,pathlib,re,subprocess,sys,tempfile

BASE='ffd5e4889a9a1f84fdc5213edefe64c36b4377a2'
TARGETS=[
    'tools.test_setup.HubWorktrees.test_a_stale_registration_does_not_block_adding_again',
    'tools.test_setup.HubWorktrees.test_a_stale_registration_with_unicode_and_spaces_does_not_block_adding_again',
    'tools.test_setup.HubWorktrees.test_git_paths_are_utf8_when_python_utf8_mode_is_disabled',
    'tools.test_setup.HubWorktrees.test_recovery_does_not_force_prune_a_locked_worktree',
]
READONLY_TARGETS=[
    'tools.test_setup.HubWorktrees.test_reports_an_existing_clone_and_converts_it_on_request',
    'tools.test_setup.HubWorktrees.test_conversion_removes_readonly_git_objects',
    'tools.test_setup.HubWorktrees.test_failed_conversion_restores_the_original_clone_after_partial_checkout',
    'tools.test_setup.HubWorktrees.test_conversion_preserves_local_work',
]
def sanitize(text,root):
    for value,marker in ((str(root),'<FIXTURE>'),(str(pathlib.Path.home()),'<HOME>')):
        for variant in (value.replace('\\','/'), *(value.replace('\\','\\'*n) for n in (8,4,2,1))):
            text=text.replace(variant,marker)
    return re.sub(r'[A-Z]:\\[^\r\n\'\"]*?\\Temp\\tmp[^\\\'\"\r\n ]+','<TEMP>',text)
def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=pathlib.Path,required=True);p.add_argument('--out',type=pathlib.Path,required=True)
    p.add_argument('--integration-tree',help='verify both fixes from the tree returned by git merge-tree')
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    def git(*cmd):return subprocess.check_output(['git',*cmd],cwd=a.source)
    if a.integration_tree:
        with tempfile.TemporaryDirectory(prefix='setup-combined-proof-') as temp:
            root=pathlib.Path(temp);(root/'tools').mkdir()
            for name in ('tools/setup.py','tools/test_setup.py'):
                (root/name).write_bytes(git('show',a.integration_tree+':'+name))
            result=subprocess.run([sys.executable,'-X','utf8','-m','unittest',*TARGETS,*READONLY_TARGETS,'-v'],cwd=root,
                capture_output=True,encoding='utf-8',errors='replace',timeout=90)
            text=sanitize(result.stdout+result.stderr,root)
            (a.out/'integration.txt').write_text(text,encoding='utf-8',newline='\n')
            summary=[s for s in text.splitlines() if s.startswith(('Ran ','OK','FAILED'))]
            (a.out/'integration.json').write_text(json.dumps({'tree':a.integration_tree,
                'returncode':result.returncode,'summary':summary,'python':sys.version.split()[0]},indent=2),encoding='utf-8',newline='\n')
            print('integration',result.returncode,' / '.join(summary),flush=True)
            assert result.returncode==0
        return
    patched={name:git('show','HEAD:'+name) for name in ('tools/setup.py','tools/test_setup.py')}
    original=git('show',BASE+':tools/setup.py');records=[]
    with tempfile.TemporaryDirectory(prefix='setup-worktree-proof-') as temp:
        root=pathlib.Path(temp);(root/'tools').mkdir()
        for name,body in patched.items():(root/name).write_bytes(body)
        for label,body,tests in (
            ('target-red',original,TARGETS),('target-green',patched['tools/setup.py'],TARGETS),
            ('suite-baseline',original,['tools.test_setup']),('suite-fixed',patched['tools/setup.py'],['tools.test_setup'])):
            (root/'tools/setup.py').write_bytes(body)
            result=subprocess.run([sys.executable,'-X','utf8','-m','unittest',*tests,'-v'],cwd=root,
                capture_output=True,encoding='utf-8',errors='replace',timeout=90)
            text=result.stdout+result.stderr
            text=sanitize(text,root)
            (a.out/(label+'.txt')).write_text(text,encoding='utf-8',newline='\n')
            summary=[s for s in text.splitlines() if s.startswith(('Ran ','OK','FAILED'))]
            records.append({'case':label,'returncode':result.returncode,'summary':summary,
                'errors':re.findall(r'^(?:ERROR|FAIL): (.+)$',text,re.MULTILINE)})
            print(label,result.returncode,' / '.join(summary),flush=True)
    assert records[0]['returncode']!=0 and records[1]['returncode']==0
    before=set(records[2]['errors']);after=set(records[3]['errors'])
    assert after.issubset(before),'the fix introduced a new full-suite failure'
    receipt={'base':BASE,'head':git('rev-parse','HEAD').decode().strip(),'platform':sys.platform,
        'python':sys.version.split()[0],'runs':records,'resolved':sorted(before-after),'unchanged':sorted(after)}
    (a.out/'results.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8',newline='\n')

if __name__=='__main__':main()
