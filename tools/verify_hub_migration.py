"""Reproduce migration data loss, then verify the saved patch on clean Git bytes.

Requires Git, an existing Rust toolchain/linker, and Cargo dependencies (cached
when --offline is used). This builds exact production migration functions with
the real app-contract crate and bounded admission helpers. It does NOT build
the whole App Hub, Store, catalog/signature checks, or the appstore UI.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REVISION = '386359153ed6377b5f047bd9ed2767a6a2ac2bc7'
CASES = Path(__file__).with_name('hub_migration_cases.rs')
BOUNDARY = ('Exact production migration functions, unchanged app-contract, and '
            'bounded admission helpers; excludes whole App Hub, Store, catalog/'
            'signature validation, and appstore UI integration.')


def save_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n',
                    encoding='utf-8', newline='\n')


def run(command, cwd, output, name, env, allow_failure=False):
    command = [str(value) for value in command]
    result = subprocess.run(command, cwd=cwd, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    header = ('Command: ' + subprocess.list2cmdline(command)
              + '\nExit code: ' + str(result.returncode) + '\n\n')
    (output / (name + '.txt')).write_bytes(header.encode('utf-8') + result.stdout)
    print(name + ': exit ' + str(result.returncode), flush=True)
    if result.returncode and not allow_failure:
        raise RuntimeError(name + ' failed; see ' + str(output / (name + '.txt')))
    return result


def section(text, start, end):
    if text.count(start) != 1 or text.count(end) != 1:
        raise RuntimeError('Production extraction anchors changed: ' + start)
    first, last = text.index(start), text.index(end)
    if first >= last:
        raise RuntimeError('Production extraction anchors are out of order')
    return text[first:last]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def tree_digest(root):
    result = hashlib.sha256()
    for path in sorted(root.rglob('*')):
        if path.is_file():
            result.update(path.relative_to(root).as_posix().encode('utf-8'))
            result.update(b'\0')
            result.update(path.read_bytes())
    return result.hexdigest()


def prepare_harness(source, harness, revision, patch_sha):
    """Wrapper imports adapt crate names; production function bodies stay exact."""
    client_bytes = (source / 'crates/app-hub/src/client.rs').read_bytes()
    functions = section(client_bytes.decode('utf-8'),
                        'pub const INSTALLS_DIR: &str = ".bundles";',
                        "/// Days from a catalog's")
    for function in ('adopt_legacy_install', 'adopt_legacy_installs'):
        if functions.count('pub fn ' + function + '(') != 1:
            raise RuntimeError('Missing production function: ' + function)
    # Using app-contract for these names is exact: app-policy reexports them.
    policy_hashes = {}
    for module in ('bundle', 'manifest'):
        data = (source / ('crates/app-policy/src/' + module + '.rs')).read_bytes()
        if ('pub use octosense_app_contract::' + module + '::*;') not in data.decode('utf-8'):
            raise RuntimeError('App Policy no longer directly reexports ' + module)
        policy_hashes[module] = digest(data)

    (harness / 'src').mkdir(parents=True)
    shutil.copytree(source / 'crates/app-contract', harness / 'contract')
    manifest = '''[workspace]
members = ["contract"]

[package]
name = "hub-migration-function-validation"
version = "0.0.0"
edition = "2021"
publish = false

[dependencies]
octosense-app-contract = { path = "contract" }
serde_json = "1"
base64 = "0.22"
'''
    (harness / 'Cargo.toml').write_text(manifest, encoding='utf-8', newline='\n')
    header = ('use std::path::{Path, PathBuf};\n'
              'use octosense_app_contract as octosense_app_policy;\n'
              'use octosense_app_contract::digest_dir;\n')
    evidence = {
        'revision': revision, 'patch_sha256': patch_sha, 'boundary': BOUNDARY,
        'client_rs_sha256': digest(client_bytes),
        'migration_functions_sha256': digest(functions.encode('utf-8')),
        'contract_tree_sha256': tree_digest(harness / 'contract'),
        'policy_reexport_files_sha256': policy_hashes,
        'cases_sha256': digest(CASES.read_bytes()),
    }
    if 'crate::admission::' in functions:
        admission_bytes = (source / 'crates/app-hub/src/admission.rs').read_bytes()
        bounded = section(admission_bytes.decode('utf-8'), 'pub const MAX_ENTRIES:',
                          '#[derive(Clone, Debug, Serialize)]\n'
                          '#[serde(rename_all = "kebab-case")]\n'
                          'pub enum ResourceKind {')
        gate_bytes = (source / 'crates/app-hub/src/gate.rs').read_bytes()
        limits = re.findall(r'pub const MAX_BUNDLE_BYTES: u64 = [^;]+;',
                            gate_bytes.decode('utf-8'))
        if len(limits) != 1:
            raise RuntimeError('MAX_BUNDLE_BYTES extraction changed')
        support = ('use std::fs;\nuse std::io::Read;\n'
                   'use std::path::{Component, Path, PathBuf};\n'
                   'use crate::octosense_app_policy;\n')
        (harness / 'src/admission.rs').write_text(support + limits[0] + '\n' + bounded,
                                                 encoding='utf-8', newline='\n')
        functions += '\nmod admission;\n'
        evidence.update({
            'admission_rs_sha256': digest(admission_bytes),
            'gate_rs_sha256': digest(gate_bytes),
            'bounded_admission_sha256': digest(bounded.encode('utf-8')),
            'max_bundle_bytes_declaration': limits[0],
        })
    (harness / 'src/lib.rs').write_text(header + functions + '\n#[cfg(test)]\nmod cases;\n',
                                       encoding='utf-8', newline='\n')
    shutil.copyfile(CASES, harness / 'src/cases.rs')
    return evidence


def test_harness(cargo, harness, output, name, env, offline):
    command = [cargo, 'test', '--color', 'never', '--manifest-path', harness / 'Cargo.toml',
               '-p', 'hub-migration-function-validation', '--lib']
    if offline:
        command.append('--offline')
    command += ['--', '--show-output', '--test-threads=1']
    result = run(command, ROOT, output, name, env, allow_failure=True)
    text = result.stdout.decode('utf-8', errors='replace')
    names = re.findall(r'#\[test\]\s*fn (\w+)\(', CASES.read_text(encoding='utf-8'))
    summary = re.search(r'^test result: (ok|FAILED)\. (\d+) passed; (\d+) failed; '
                        r'(\d+) ignored; \d+ measured; (\d+) filtered out;', text, re.M)
    observed = dict(re.findall(r'^test cases::(\w+) \.\.\. (ok|FAILED)$', text, re.M))
    if len(names) != 17 or set(observed) != set(names) or not summary:
        raise RuntimeError(name + ' did not execute all 17 cases; compiler/dependency '
                           'errors are not regression evidence. See ' + str(output / (name + '.txt')))
    status, passed, failed, ignored, filtered = summary.groups()
    counts = {'passed': int(passed), 'failed': int(failed), 'ignored': int(ignored),
              'filtered': int(filtered), 'exit_code': result.returncode}
    if counts['passed'] + counts['failed'] != 17 or counts['ignored'] or counts['filtered']:
        raise RuntimeError(name + ' did not complete all 17 cases')
    if name == 'red':
        if (result.returncode == 0 or status != 'FAILED'
                or observed.get('current_install_preserves_data_named_bundle') != 'FAILED'):
            raise RuntimeError('Baseline did not reproduce the named data-loss regression')
    elif result.returncode != 0 or status != 'ok' or counts['failed']:
        raise RuntimeError('Patched functions failed; see ' + str(output / 'green.txt'))
    print(name + ': ' + passed + ' passed / ' + failed + ' failed', flush=True)
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / 'OctoSense-App-Hub',
                        help='local official Git checkout containing the revision')
    parser.add_argument('--revision', default=REVISION, help='commit to export; source edits are ignored')
    parser.add_argument('--patch', type=Path,
                        default=ROOT / 'my-entry/patches/app-hub-legacy-migration-data-loss.patch')
    parser.add_argument('--cargo-path', default='cargo', help='Cargo executable or command on PATH')
    parser.add_argument('--offline', action='store_true', help='use only existing Cargo dependency cache')
    parser.add_argument('--output', type=Path, default=ROOT / 'build/hub-migration-verification')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    # Remove stale evidence before a failed rerun can be mistaken for this run.
    for name in ('summary.json', 'red.txt', 'green.txt', 'red-extraction.json', 'green-extraction.json'):
        (output / name).unlink(missing_ok=True)
    cargo = shutil.which(args.cargo_path)
    if cargo is None:
        raise RuntimeError('Cargo not found: ' + args.cargo_path)
    cargo = str(Path(cargo).resolve())
    env = {**os.environ, 'PYTHONIOENCODING': 'utf-8', 'RUSTUP_AUTO_INSTALL': '0',
           'CARGO_TARGET_DIR': str(output / 'cargo-target')}
    # A selected standalone Cargo can find its companion rustc without a machine path.
    env['PATH'] = str(Path(cargo).parent) + os.pathsep + env.get('PATH', '')
    if args.offline:
        env['CARGO_NET_OFFLINE'] = 'true'
    source, patch = args.source.resolve(), args.patch.resolve()
    patch_sha = digest(patch.read_bytes())
    resolved = run(['git', '-C', source, 'rev-parse', '--verify', args.revision + '^{commit}'],
                   ROOT, output, 'revision', env).stdout.decode('ascii').strip()
    run([cargo, '--version'], ROOT, output, 'cargo-version', env)
    print(BOUNDARY, flush=True)
    with tempfile.TemporaryDirectory(prefix='hub-migration-', dir=output) as temp:
        scratch = Path(temp)
        archive = scratch / 'source.zip'
        run(['git', '-c', 'core.autocrlf=false', '-c', 'core.eol=lf', '-C', source,
             'archive', '--format=zip', '--output=' + str(archive), resolved],
            ROOT, output, 'archive', env)
        checkout = scratch / 'source'
        checkout.mkdir()
        with zipfile.ZipFile(archive) as contents:
            for item in contents.infolist():
                target = (checkout / item.filename).resolve()
                if checkout.resolve() not in target.parents and target != checkout.resolve():
                    raise RuntimeError('Archive entry escapes checkout: ' + item.filename)
            contents.extractall(checkout)
        red_harness = scratch / 'red'
        red_info = prepare_harness(checkout, red_harness, resolved, None)
        save_json(output / 'red-extraction.json', red_info)
        red = test_harness(cargo, red_harness, output, 'red', env, args.offline)
        red_info['harness_cargo_lock_sha256'] = digest((red_harness / 'Cargo.lock').read_bytes())
        save_json(output / 'red-extraction.json', red_info)
        run(['git', 'init', '--quiet'], checkout, output, 'init', env)
        run(['git', 'config', 'core.autocrlf', 'false'], checkout, output, 'git-config', env)
        run(['git', 'apply', '--check', patch], checkout, output, 'apply-check', env)
        run(['git', 'apply', patch], checkout, output, 'apply', env)
        green_harness = scratch / 'green'
        green_info = prepare_harness(checkout, green_harness, resolved, patch_sha)
        save_json(output / 'green-extraction.json', green_info)
        green = test_harness(cargo, green_harness, output, 'green', env, args.offline)
        green_info['harness_cargo_lock_sha256'] = digest((green_harness / 'Cargo.lock').read_bytes())
        save_json(output / 'green-extraction.json', green_info)
    save_json(output / 'summary.json', {'revision': resolved, 'patch_sha256': patch_sha,
                                      'boundary': BOUNDARY, 'red': red, 'green': green,
                                      'clean_patch_applied': True})
    print('Baseline data loss reproduced; clean patch applied; 17 function cases passed. Logs: '
          + str(output), flush=True)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, zipfile.BadZipFile) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
