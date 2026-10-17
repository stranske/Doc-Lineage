import os,sys,pathlib,subprocess,time,hashlib,json,importlib.metadata
ROOT=pathlib.Path('/Users/teacher/.codex/orchestrator/worktrees/stranske__Doc-Lineage__129__opener')
OUT=pathlib.Path(__file__).parent
PY='/private/tmp/dl129-main2-venv/bin/python'
env={**os.environ,'PATH':'/private/tmp/dl129-main2-venv/bin:'+os.environ['PATH'],'PYTHONPATH':str(ROOT/'src'),'PYTHONDONTWRITEBYTECODE':'1','PIP_NO_BUILD_ISOLATION':'0','PIP_NO_DEPS':'1','PIP_NO_INDEX':'1','COVERAGE_FILE':str(OUT/'.coverage'),'DOC129_NATIVE_EVIDENCE':str(OUT/'native'),'XDG_CACHE_HOME':str(OUT/'cache')}
def bindings(root=ROOT):
 return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for base in ['src','tests','schemas','vocab','docs/contracts/schemas'] for p in (root/base).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
def run(label,argv,cwd=ROOT,extra=None):
 before=bindings(cwd);start=time.time()
 with (OUT/f'{label}.log').open('w') as log:
  r=subprocess.run(argv,cwd=cwd,env={**env,**(extra or {})},stdout=log,stderr=subprocess.STDOUT)
 files=[OUT/f'{label}.log',OUT/f'{label}.xml']
 receipt={'argv':argv,'cwd':str(cwd),'exit_code':r.returncode,'elapsed_seconds':time.time()-start,'git_revision':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'bindings':before,'bindings_unchanged':before==bindings(cwd),'outputs':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files if p.exists()},'env':{k:env[k] for k in ['PYTHONPATH','PIP_NO_DEPS','PIP_NO_BUILD_ISOLATION','PIP_NO_INDEX','DOC129_NATIVE_EVIDENCE']}}
 (OUT/f'{label}.json').write_text(json.dumps(receipt,indent=2)+'\n');print(label,r.returncode,flush=True);return r.returncode
if __name__=='__main__':
 (OUT/'environment.json').write_text(json.dumps({'executable':PY,'base':'/opt/anaconda3/bin/python3','packages':{d.metadata['Name']:d.version for d in importlib.metadata.distributions()}},indent=2))
 for label,args in [
 ('focused',['pytest','tests/test_cli.py','tests/ingest','tests/blackline','tests/export','tests/test_package_identity.py','-q',f'--junitxml={OUT}/focused.xml']),
 ('full',['pytest','--cov=src','--cov-report=term-missing',f'--cov-report=xml:{OUT}/coverage.xml',f'--junitxml={OUT}/full.xml','-q']),
 ('ruff',['ruff','check','src','tests']),('black',['black','--check','src','tests']),
 ('mypy-focused',['mypy','--follow-imports=silent','src/doc_lineage/cli.py','src/doc_lineage/ingest.py','src/doc_lineage/blackline.py','src/doc_lineage/persistence.py']),
 ('mypy-full',['mypy','src'])]:
  run(label,[PY,'-m',*args])
