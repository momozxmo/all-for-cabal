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
    assert 'playwright==1.60.0' in constraints.splitlines()


def test_dockerfile_installs_tkinter_required_by_imported_desktop_modules():
    dockerfile = read('Dockerfile.dev')
    assert 'apt-get install -y --no-install-recommends python3-tk' in dockerfile


def test_dockerfile_migrates_the_persistent_database_before_startup():
    dockerfile = read('Dockerfile.dev')
    assert 'python -m alembic upgrade head' in dockerfile
    assert 'exec python -m uvicorn web.app:app' in dockerfile


def test_docker_image_uses_the_verified_core_and_test_dependencies():
    dockerfile = read('Dockerfile.dev')
    constraints = read('constraints-docker.txt')
    test_requirements = read('requirements-test.txt')
    for dependency in (
        'playwright==1.60.0',
        'fastapi==0.128.7',
        'starlette==0.52.1',
        'uvicorn==0.40.0',
        'SQLAlchemy==2.0.51',
    ):
        assert dependency in constraints
    assert 'pytest==8.4.*' in test_requirements
    assert 'httpx==0.28.*' in test_requirements
    assert 'requirements-test.txt' in dockerfile
    assert '-r requirements-test.txt' in dockerfile


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


def test_docker_documentation_explains_commands_and_release_boundary():
    guide = read('docs/DEVELOPMENT_DOCKER.md')
    for command in ('start', 'test', 'logs', 'stop'):
        assert r'.\scripts\docker_dev.ps1 ' + command in guide
    assert 'scripts/build_local_installer.ps1' in guide
    assert 'Docker' in read('README.md')
    assert 'VPN' in guide
    assert 'IPA' in guide
    assert 'ไม่สร้างข้อมูลจริง' in guide
