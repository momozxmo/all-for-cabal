from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(name: str) -> str:
    return (ROOT / name).read_text(encoding='utf-8')


def test_dockerfile_pins_matching_playwright_image_and_constraint():
    dockerfile = read('Dockerfile.dev')
    constraints = read('constraints-docker.txt')
    assert 'mcr.microsoft.com/playwright/python:v1.60.0-noble' in dockerfile
    assert (
        'pip install --no-cache-dir -c constraints-docker.txt '
        '-r requirements.txt'
    ) in dockerfile
    assert constraints.strip() == 'playwright==1.60.0'


def test_compose_is_loopback_only_single_browser_and_persistent():
    compose = read('compose.yaml')
    assert '127.0.0.1:8000:8000' in compose
    assert 'BROWSER_CONCURRENCY: "1"' in compose
    assert 'DATABASE_URL: sqlite:////data/all_for_cabal_web.db' in compose
    assert 'all-for-cabal-dev-data:/data' in compose
    assert 'init: true' in compose
    assert 'ipc: host' in compose
    assert '/api/health' in compose


def test_docker_build_context_excludes_private_and_generated_state():
    ignored = read('.dockerignore')
    for value in (
        '.env*', '*.db', '*.sqlite', '*.sqlite3', '.cabal_chrome_profile/',
        '.local-runtime/', 'runtime-local/', 'dist/', 'build/', 'artifacts/',
        'build-cache/', '*.xlsx', '*.xls',
    ):
        assert value in ignored


def test_generated_docker_environment_is_gitignored():
    ignored = read('.gitignore')
    assert '.env.docker.local' in ignored


def test_docker_script_has_safe_lifecycle_actions_and_cli_fallback():
    script = read('scripts/docker_dev.ps1')
    for action in ('start', 'test', 'logs', 'stop'):
        assert "'%s'" % action in script
    assert 'Programs\\DockerDesktop\\resources\\bin\\docker.exe' in script
    assert '.env.docker.local' in script
    assert 'RandomNumberGenerator' in script
    assert 'compose up --build --detach' not in script
    assert "@('compose', 'up', '--build', '-d')" in script
    assert "@('compose', 'down')" in script
    assert "@('compose', 'down', '-v')" not in script


def test_installer_build_remains_native_and_docker_free():
    installer = read('scripts/build_local_installer.ps1').lower()
    assert 'pyinstaller' in installer
    assert 'iscc' in installer
    assert 'docker' not in installer
