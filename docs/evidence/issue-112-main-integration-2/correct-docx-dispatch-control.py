import pathlib,shutil,json,hashlib
from validate import ROOT,OUT,PY,run
COPY=pathlib.Path('/private/tmp/dl129-main2-causal')
shutil.rmtree(COPY)
COPY.mkdir()
for d in ['src','tests','schemas','vocab']:
 shutil.copytree(ROOT/d,COPY/d,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
shutil.copytree(ROOT/'docs/contracts',COPY/'docs/contracts')
for f in ['pyproject.toml','README.md']:shutil.copyfile(ROOT/f,COPY/f)
original={str(p.relative_to(COPY)):p.read_bytes() for base in ['src','tests'] for p in (COPY/base).rglob('*') if p.is_file()}
tests_hash={n:hashlib.sha256(b).hexdigest() for n,b in original.items() if n.startswith('tests/')}
variants=[
 ('privacy-directory','src/doc_lineage/ingest.py',lambda s:s.replace('destination.mkdir(mode=0o700','destination.mkdir(mode=0o777').replace('    destination.chmod(0o700)','    # disconnected run privacy').replace('evidence_dir.mkdir(mode=0o700','evidence_dir.mkdir(mode=0o777').replace('    evidence_dir.chmod(0o700)','    # disconnected evidence privacy'),'test_ingest_artifacts_owner_only_under_permissive_umask[False]','INGEST_RUN_IS_PRIVATE'),
 ('privacy-artifact','src/doc_lineage/ingest.py',lambda s:s.replace('write_private(segments_path, segments_bytes)','segments_path.write_bytes(segments_bytes)').replace('write_private(evidence_path, payload_bytes)','evidence_path.write_bytes(payload_bytes)').replace('write_private(manifest_path, _dump(manifest))','manifest_path.write_bytes(_dump(manifest))'),'test_ingest_artifacts_owner_only_under_permissive_umask[False]','INGEST_ARTIFACT_IS_PRIVATE'),
 ('snapshot-publication','src/doc_lineage/persistence.py',lambda s:s.replace('    try:\n        with os.fdopen(descriptor, "wb") as output:','    try:\n        os.link(temporary, path)\n        with os.fdopen(descriptor, "wb") as output:',1).replace('        os.link(temporary, path)\n    finally:', '    finally:',1),'test_snapshot_failure_cleanup_and_retry[write]','INTERRUPTED_SNAPSHOT_NEVER_PUBLISHES_FINAL'),
 ('directory-durability','src/doc_lineage/persistence.py',lambda s:s.replace('    sync_directory(path.parent)','    # disconnected durable directory publication'),'test_comparison_durable_publication_order','DURABLE_COMPARISON_ORDER'),
]
variants += [
 ('docx-cli-dispatch','src/doc_lineage/cli.py',lambda s:s.replace('if args.command == "create-comparison":','if args.command == "disconnected-create-comparison":'),'tests/blackline/test_combined_comparison_modes.py::test_combined_cli_keeps_both_comparison_schemas', 'unhandled command: create-comparison'),
 ('pdf-cli-dispatch','src/doc_lineage/cli.py',lambda s:s.replace('if args.command in {"pair-sections", "lookup-section-pairing"}:','if args.command in {"disconnected-pair-sections", "disconnected-lookup-section-pairing"}:'),'tests/blackline/test_comparison_run_cli.py::test_independent_ingest_compare_lookup_replay','assert result.returncode == 0'),
 ('pdf-engine-wiring','src/doc_lineage/blackline.py',lambda s:s.replace('lineage_edge_for(pair) for pair in align_sections(left, right, threshold=threshold)','lineage_edge_for(pair) for pair in []'),'tests/blackline/test_section_id_pairing.py::test_persisted_section_pairing_binds_ordered_inputs_and_replays','assert'),
 ('docx-source-hash-wiring','src/doc_lineage/cli.py',lambda s:s.replace('if hashlib.sha256(content).hexdigest() != expected:', 'if False:'),'tests/test_cli.py::test_comparison_sha256_check_disconnection[file-original]','SHA256_CHECK_DISCONNECTION'),
]
variants=[v for v in variants if v[0]=="docx-cli-dispatch"]
receipts=[]
for name,path,mutate,node,assertion in variants:
 target=COPY/path; before=target.read_bytes(); broken=mutate(before.decode()).encode();assert broken!=before
 (OUT/f'{name}.green.py.txt').write_bytes(before);(OUT/f'{name}.red.py.txt').write_bytes(broken)
 target.write_bytes(broken)
 red=run(name+'-red',[PY,'-m','pytest',(node if '::' in node else 'tests/ingest/test_private_publication.py::'+node),'-q',f'--junitxml={OUT}/{name}-red.xml'],cwd=COPY,extra={'PYTHONPATH':str(COPY/'src')})
 assert red==1 and assertion in (OUT/f'{name}-red.log').read_text(),(name,red)
 target.write_bytes(before);assert target.read_bytes()==before
 assert all((COPY/n).read_bytes()==b for n,b in original.items()),'restoration is not byte identical'
 green=run(name+'-restored-green',[PY,'-m','pytest',(node if '::' in node else 'tests/ingest/test_private_publication.py::'+node),'-q',f'--junitxml={OUT}/{name}-restored-green.xml'],cwd=COPY,extra={'PYTHONPATH':str(COPY/'src')})
 assert green==0
 receipts.append({'variant':name,'path':path,'node':node,'assertion':assertion,'red_exit':red,'green_exit':green,'source_green_sha256':hashlib.sha256(before).hexdigest(),'source_red_sha256':hashlib.sha256(broken).hexdigest(),'byte_identical_restoration':True,'unchanged_test_hashes':tests_hash})
original=json.loads((OUT/'causal-proof.json').read_text())
original=[p for p in original if p['variant']!='docx-cli-dispatch']+receipts
(OUT/'causal-proof.json').write_text(json.dumps(original,indent=2)+'\n')
