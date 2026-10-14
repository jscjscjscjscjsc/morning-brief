"""Reproduce one upstream Windows clone-conversion fix without network or real sources."""
import argparse,json,pathlib,re,subprocess,sys,tempfile

BASE='ffd5e4889a9a1f84fdc5213edefe64c36b4377a2'
TARGETS=[
    'tools.test_setup.HubWorktrees.test_reports_an_existing_clone_and_converts_it_on_request',
    'tools.test_setup.HubWorktrees.test_conversion_removes_readonly_git_objects',
    'tools.test_setup.HubWorktrees.test_failed_conversion_restores_the_original_clone_after_partial_checkout',
    'tools.test_setup.HubWorktrees.test_conversion_preserves_local_work',
]
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',type=pathlib.Path,required=True,help='checkout containing the reviewed upstream fix')
    parser.add_argument('--out',type=pathlib.Path,required=True)
    args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    def git(*cmd):return subprocess.check_output(['git',*cmd],cwd=args.source)
    source={p:git('show','HEAD:'+p) for p in ('tools/setup.py','tools/test_setup.py')}
    baseline=git('show',BASE+':tools/setup.py')
    records=[]
    with tempfile.TemporaryDirectory(prefix='setup-readonly-proof-') as temp:
        root=pathlib.Path(temp);(root/'tools').mkdir()
        for name,body in source.items():(root/name).write_bytes(body)
        for label,body,tests in (
            ('target-red',baseline,TARGETS),('target-green',source['tools/setup.py'],TARGETS),
            ('suite-baseline',baseline,['tools.test_setup']),('suite-fixed',source['tools/setup.py'],['tools.test_setup'])):
            (root/'tools/setup.py').write_bytes(body)
            result=subprocess.run([sys.executable,'-X','utf8','-m','unittest',*tests,'-v'],cwd=root,
                capture_output=True,encoding='utf-8',errors='replace',timeout=90)
            text=result.stdout+result.stderr
            for value,marker in ((str(root),'<FIXTURE>'),(str(pathlib.Path.home()),'<HOME>')):
                text=text.replace(value.replace('\\','\\\\'),marker).replace(value,marker)
            text=re.sub(r'[A-Z]:\\[^\r\n\'\"]*?\\Temp\\tmp[^\\\'\"\r\n ]+', '<TEMP>',text)
            (args.out/(label+'.txt')).write_text(text,encoding='utf-8',newline='\n')
            summary=[s for s in text.splitlines() if s.startswith(('Ran ','OK','FAILED'))]
            records.append({'case':label,'returncode':result.returncode,'summary':summary,
                'errors':re.findall(r'^ERROR: (.+)$',text,re.MULTILINE)})
            print(label,result.returncode,' / '.join(summary),flush=True)
    assert records[0]['returncode']!=0 and records[1]['returncode']==0,'red/green proof failed'
    receipt={'base':BASE,'head':git('rev-parse','HEAD').decode().strip(),'platform':sys.platform,
        'python':sys.version.split()[0],'runs':records}
    (args.out/'results.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8',newline='\n')

if __name__=='__main__':main()
