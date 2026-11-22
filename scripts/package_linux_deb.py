#!/usr/bin/env python3
"""Build and inspect the Ubuntu 24.04 amd64 system-library GUI package."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import subprocess
import tarfile

from package_notices import verify_notices

TARGET = 'linux-ubuntu24.04-x86_64-deb'
GUI = 'usr/bin/chronoscope-desktop'
RESOURCES = 'usr/lib/TimeScope'
DOC = 'usr/share/doc/timescope'
ICON = 'usr/share/icons/hicolor/128x128/apps/timescope.png'
DESKTOP = 'usr/share/applications/timescope.desktop'
DESKTOP_TEXT = """[Desktop Entry]
Type=Application
Name=TimeScope
Exec=chronoscope-desktop
Icon=timescope
Terminal=false
Categories=Science;Education;
"""
SYSTEM_DEPENDS = (
    'libwebkit2gtk-4.1-0', 'libgtk-3-0t64', 'libgl1', 'libegl1', 'libgles2',
)


def check(condition, message):
    if not condition:
        raise ValueError(message)


def ubuntu_guard():
    release = platform.freedesktop_os_release() if platform.system() == 'Linux' else {}
    check(release.get('ID') == 'ubuntu' and release.get('VERSION_ID') == '24.04'
          and platform.machine() == 'x86_64', 'Ubuntu 24.04 amd64 required')


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def package_name(source):
    config = json.loads((source / 'src-tauri/tauri.conf.json').read_text())
    version = config['version']
    check(re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', version), 'Unsupported Debian package version')
    return f'timescope_{version}_amd64.deb'


def dependency_field(binary, staging):
    debian = staging / 'debian'
    debian.mkdir()
    (debian / 'control').write_text('Source: timescope\n\nPackage: timescope\nArchitecture: amd64\nDescription: TimeScope desktop\n')
    output = subprocess.check_output(['dpkg-shlibdeps', '-O', '-e' + str(binary)], cwd=staging, text=True)
    generated = output.strip().removeprefix('shlibs:Depends=')
    check(generated and 'libc6' in generated and output.startswith('shlibs:Depends='), 'Missing ELF dependency metadata')
    terms = generated.split(', ')
    names = {term.split()[0] for term in terms}
    return ', '.join(terms + [name for name in SYSTEM_DEPENDS if name not in names])


def build(package, work, source, binary, source_access):
    ubuntu_guard()
    tree = work / 'data'
    resources = tree / RESOURCES
    shutil.copytree(source / 'frontend/dist/third-party', resources / 'third-party')
    (resources / 'terrain').mkdir()
    shutil.copyfile(source / 'assets/terrain/balanced.cterrain', resources / 'terrain/balanced.cterrain')
    for name, original in ((GUI, binary), (ICON, source / 'src-tauri/icons/128x128.png'),
                           (DOC + '/copyright', source / 'LICENSE'), (DOC + '/SOURCE-ACCESS.txt', source_access)):
        destination = tree / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, destination)
    (tree / GUI).chmod(0o755)
    (tree / DESKTOP).parent.mkdir(parents=True, exist_ok=True)
    (tree / DESKTOP).write_text(DESKTOP_TEXT)
    control = tree / 'DEBIAN'
    control.mkdir()
    version = package.name.split('_')[1]
    depends = dependency_field(tree / GUI, work)
    (control / 'control').write_text(
        f'Package: timescope\nVersion: {version}\nArchitecture: amd64\n'
        f'Depends: {depends}\nSection: science\nPriority: optional\n'
        'Maintainer: TimeScope\n'
        'Homepage: https://github.com/TimeScope/timescope\n'
        'Description: TimeScope desktop spatiotemporal analysis\n')
    subprocess.run(['dpkg-deb', '--root-owner-group', '--build', tree, package], check=True, timeout=120)


def extract_member_archive(package, mode, destination):
    # Stream both tar members; never run maintainer scripts or let an archiver
    # create a symlink, device, or unbounded filesystem entry.
    destination.mkdir()
    seen = set()
    byte_limit = 512 * 1024 * 1024 if mode == '--fsys-tarfile' else 64 * 1024
    total = 0
    with subprocess.Popen(['dpkg-deb', mode, package], stdout=subprocess.PIPE) as process:
        try:
            with tarfile.open(fileobj=process.stdout, mode='r|') as archive:
                for entry in archive:
                    name = entry.name.removeprefix('./').rstrip('/')
                    if name in ('', '.') and entry.isdir():
                        continue
                    path = PurePosixPath(name)
                    check(name == path.as_posix() and not path.is_absolute() and
                          '..' not in path.parts and not any(c in name for c in '\\\x00') and
                          name not in seen and len(seen) < 20000,
                          'Unsafe or duplicate Debian package entry')
                    seen.add(name)
                    total += entry.size
                    check((entry.isdir() or entry.isfile()) and not entry.mode & 0o7000
                          and 0 <= total <= byte_limit, 'Unsupported or oversized Debian package entry')
                    output = destination / path
                    if entry.isdir():
                        output.mkdir(parents=True, exist_ok=True)
                        continue
                    allowed = (name == 'control' if mode == '--ctrl-tarfile' else
                               name in {GUI, DESKTOP, ICON, DOC + '/copyright', DOC + '/SOURCE-ACCESS.txt',
                                        RESOURCES + '/terrain/balanced.cterrain'} or
                               name.startswith(RESOURCES + '/third-party/'))
                    check(allowed and bool(entry.mode & 0o111) == (name == GUI),
                          'Unexpected Debian package file or executable mode')
                    output.parent.mkdir(parents=True, exist_ok=True)
                    with archive.extractfile(entry) as stream, output.open('xb') as target:
                        shutil.copyfileobj(stream, target, length=1024 * 1024)
                    output.chmod(0o755 if name == GUI else 0o644)
            # Consume bounded trailing tar padding before checking dpkg's exit.
            check(len(process.stdout.read(10241)) <= 10240, 'Unexpected Debian archive trailer')
            check(process.wait(timeout=20) == 0, 'dpkg-deb inspection failed')
        finally:
            if process.poll() is None:
                process.kill()


def inspect(package, work, source, source_access):
    check(package.name == package_name(source), 'Unexpected Ubuntu package filename')
    extract_member_archive(package, '--ctrl-tarfile', work / 'control')
    tree = work / 'extracted'
    extract_member_archive(package, '--fsys-tarfile', tree)
    control = (work / 'control/control').read_text().splitlines()
    check(all(control.count(line) == 1 for line in (
        'Package: timescope', 'Architecture: amd64', f'Version: {package.name.split("_")[1]}')),
        'Debian package identity mismatch')
    depends, = [line.removeprefix('Depends: ') for line in control if line.startswith('Depends: ')]
    names = {term.split()[0] for term in depends.split(', ')}
    check(set(SYSTEM_DEPENDS) | {'libc6'} <= names, 'Missing system runtime dependencies')
    verify_notices(tree / RESOURCES / 'third-party', source)
    terrain = json.loads((source / 'assets/terrain/balanced.json').read_text())
    data = tree / RESOURCES / 'terrain/balanced.cterrain'
    check(data.stat().st_size == terrain['bytes'] and digest(data) == terrain['sha256'], 'Packaged terrain mismatch')
    check((tree / DESKTOP).read_text() == DESKTOP_TEXT
          and digest(tree / ICON) == digest(source / 'src-tauri/icons/128x128.png')
          and digest(tree / DOC / 'copyright') == digest(source / 'LICENSE')
          and digest(tree / DOC / 'SOURCE-ACCESS.txt') == digest(source_access),
          'Packaged desktop metadata or source-access instructions mismatch')
    binary = tree / GUI
    with binary.open('rb') as stream:
        header = stream.read(20)
    check(header.startswith(b'\x7fELF\x02\x01') and header[18:20] == b'\x3e\x00',
          'Debian GUI must be an x86-64 ELF')
    dynamic = subprocess.check_output(['readelf', '-dW', binary], text=True, timeout=20)
    needed = re.findall(r'\(NEEDED\).*?\[([^\]]+)\]', dynamic)
    check({'libwebkit2gtk-4.1.so.0', 'libgtk-3.so.0'} <= set(needed)
          and all('/' not in name for name in needed)
          and '(RPATH)' not in dynamic and '(RUNPATH)' not in dynamic,
          'GUI must dynamically use system GTK/WebKit and no private library path')
    return binary, {'deb_sha256': digest(package), 'depends': depends, 'elf_needed': needed,
                    'gui_sha256': digest(binary), 'terrain_sha256': terrain['sha256'],
                    'other_native_payloads': False}
