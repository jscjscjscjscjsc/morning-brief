"""Offline red/green proof of UTF-8 and LF authoring on Windows."""
import argparse,io,json,os,pathlib,re,subprocess,sys,tempfile,zipfile

BASE='d0344682df7c52ae5a79055f20f148f542d115e0'
def sanitize(text,*roots):
    for root,marker in (*((r,'<FIXTURE>') for r in roots),(pathlib.Path.home(),'<HOME>')):
        value=str(root)
        for variant in (value.replace('\\','/'),*(value.replace('\\','\\'*n) for n in (8,4,2,1))):
            text=text.replace(variant,marker)
    return text
def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=pathlib.Path,required=True)
    p.add_argument('--out',type=pathlib.Path,required=True)
    p.add_argument('--scratch-root',type=pathlib.Path,required=True,help='existing temporary directory outside any Git repository')
    a=p.parse_args();a.scratch_root=a.scratch_root.resolve()
    if not a.scratch_root.is_dir():p.error('scratch root must already exist')
    if any((r/'.git').exists() for r in (a.scratch_root,*a.scratch_root.parents)):
        p.error('scratch root must be outside any Git repository')
    a.out.mkdir(parents=True,exist_ok=True)
    def git(*cmd):return subprocess.check_output(['git',*cmd],cwd=a.source)
    original=git('show',BASE+':tools/octo');fixed=git('show','HEAD:tools/octo')
    records=[]
    with tempfile.TemporaryDirectory(prefix='octo-encoding-proof-',dir=a.scratch_root) as temp:
        root=pathlib.Path(temp)/'flow 中文';root.mkdir()
        data=git('archive','--format=zip','HEAD','tools','templates','sdk','docs')
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            for member in archive.infolist():
                target=(root/member.filename).resolve()
                assert root.resolve() in target.parents or target==root.resolve()
            archive.extractall(root)
        env={**os.environ,'TEMP':str(a.scratch_root),'TMP':str(a.scratch_root),
            'PYTHONUTF8':'1','PYTHONIOENCODING':'utf-8'}
        for label,body,pattern in (
            ('encoding-red',original,'test_octo_encoding.py'),('encoding-green',fixed,'test_octo_encoding.py'),
            ('cli-baseline',original,'test_octo.py'),('cli-fixed',fixed,'test_octo.py')):
            (root/'tools/octo').write_bytes(body)
            result=subprocess.run([sys.executable,'-B','-X','utf8','-m','unittest','discover','-s','tools','-p',pattern,'-v'],
                cwd=root,env=env,capture_output=True,encoding='utf-8',errors='replace',timeout=90)
            text=sanitize(result.stdout+result.stderr,root,a.scratch_root)
            (a.out/(label+'.txt')).write_text(text,encoding='utf-8',newline='\n')
            summary=[s for s in text.splitlines() if s.startswith(('Ran ','OK','FAILED'))]
            records.append({'case':label,'returncode':result.returncode,'summary':summary,
                'errors':re.findall(r'^(?:FAIL|ERROR): (.+)$',text,re.MULTILINE)})
            print(label,result.returncode,' / '.join(summary),flush=True)
    assert records[0]['returncode']!=0 and records[1]['returncode']==0
    assert set(records[3]['errors'])==set(records[2]['errors']),'CLI regression set changed'
    receipt={'base':BASE,'head':git('rev-parse','HEAD').decode().strip(),'platform':sys.platform,
        'python':sys.version.split()[0],'runs':records,'cli_unchanged':records[3]['errors']}
    (a.out/'results.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8',newline='\n')

if __name__=='__main__':main()
