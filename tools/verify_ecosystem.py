"""Verify saved ecosystem patches against pinned local Git objects, offline."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PINS = {
    'flow': ('d0344682df7c52ae5a79055f20f148f542d115e0', 'octo-publisher-root-utf8.patch'),
    'sense': ('ffd5e4889a9a1f84fdc5213edefe64c36b4377a2', 'octosense-setup-worktree-windows.patch'),
}
SETUP_TESTS = [
    'tools.test_setup.HubWorktrees.test_a_stale_registration_does_not_block_adding_again',
    'tools.test_setup.HubWorktrees.test_a_stale_registration_with_unicode_and_spaces_does_not_block_adding_again',
    'tools.test_setup.HubWorktrees.test_git_paths_are_utf8_when_python_utf8_mode_is_disabled',
]


def run(command, cwd, output_dir, name):
    result = subprocess.run(command, cwd=cwd, capture_output=True, encoding='utf-8',
                            env={**os.environ, 'PYTHONIOENCODING': 'utf-8',
                                 'CARGO_NET_OFFLINE': 'true', 'RUSTUP_AUTO_INSTALL': '0'})
    log = 'Command: ' + subprocess.list2cmdline([str(value) for value in command])
    log += '\nExit code: ' + str(result.returncode) + '\n' + result.stdout + result.stderr
    (output_dir / (name + '.txt')).write_bytes(log.encode('utf-8'))
    print(name + ': exit ' + str(result.returncode), flush=True)
    if result.returncode:
        print((result.stdout + result.stderr)[-3000:], flush=True)
        raise RuntimeError(name + ' failed; see ' + str(output_dir / (name + '.txt')))


def export_and_patch(source, name, scratch, output_dir):
    revision, patch = PINS[name]
    archive = scratch / (name + '.zip')
    run(['git', '-C', str(source), 'archive', '--format=zip', '--output=' + str(archive), revision],
        ROOT, output_dir, name + '-archive')
    checkout = scratch / name
    checkout.mkdir()
    with zipfile.ZipFile(archive) as contents:
        for item in contents.infolist():
            target = (checkout / item.filename).resolve()
            if checkout.resolve() not in target.parents and target != checkout.resolve():
                raise RuntimeError('Archive entry escapes checkout: ' + item.filename)
        contents.extractall(checkout)
    run(['git', 'init', '--quiet'], checkout, output_dir, name + '-init')
    patch_path = ROOT / 'my-entry/patches' / patch
    run(['git', 'apply', '--check', str(patch_path)], checkout, output_dir, name + '-apply-check')
    run(['git', 'apply', str(patch_path)], checkout, output_dir, name + '-apply')
    return checkout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--flow-source', type=Path, default=ROOT / 'OctoScript-App-Design-Flow')
    parser.add_argument('--sense-source', type=Path, default=ROOT / 'OctoSense')
    parser.add_argument('--output', type=Path, default=ROOT / 'build/ecosystem-verification')
    args = parser.parse_args()
    output_dir = args.output.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    # Export committed bytes, never the edited/ignored source checkouts.
    with tempfile.TemporaryDirectory(prefix='ecosystem-', dir=output_dir) as temp:
        scratch = Path(temp)
        flow = export_and_patch(args.flow_source.resolve(), 'flow', scratch, output_dir)
        sense = export_and_patch(args.sense_source.resolve(), 'sense', scratch, output_dir)
        for pattern in ('test_github_publish.py', 'test_octo_encoding.py', 'test_octo.py'):
            run([sys.executable, '-X', 'utf8', '-m', 'unittest', 'discover', '-s', 'tools', '-p', pattern, '-v'],
                flow, output_dir, pattern[:-3])
        run([sys.executable, '-X', 'utf8', '-m', 'unittest', '-v', *SETUP_TESTS],
            sense, output_dir, 'setup-targeted')
    print('Both patches applied to pinned clean sources; selected suites passed. Logs: ' + str(output_dir))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, zipfile.BadZipFile) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
