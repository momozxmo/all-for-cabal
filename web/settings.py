import base64
import binascii
import os
import re
import secrets
import warnings
from dataclasses import dataclass
from urllib.parse import urlsplit

from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


# Local development secrets live in a gitignored .env beside the project. Without
# one, APP_SECRET_KEY is regenerated on every start and every restart signs
# people out — including out of the bookmarklet's pairing page, which needs a web
# session to accept the captured cookies.
_ENV_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')

_DIRECT_APP_ENVS = frozenset(
    {'development', 'test', 'local-desktop', 'production'})
_ENV_APP_ENVS = _DIRECT_APP_ENVS - {'test'}
_URLSAFE_BASE64_PATTERN = re.compile(r'[A-Za-z0-9_-]*={0,2}\Z', re.ASCII)


def parse_env_bool(name: str, value: str) -> bool:
    normalized = str(value).strip().lower()
    if normalized not in {'true', 'false'}:
        raise ValueError(f'{name} must be true or false')
    return normalized == 'true'


def read_env_file(path=None):
    """Read KEY=VALUE lines and return them. Missing or unreadable file -> {}.

    Deliberately not a dotenv library, and deliberately not a writer: putting
    these into ``os.environ`` would leak one caller's file into every later
    reader in the process. The values are a fallback layer under the real
    environment instead.

    The path is resolved at call time, not bound as a default, so a test can
    point it somewhere harmless.
    """
    try:
        with open(path or _ENV_FILE, encoding='utf-8') as stream:
            lines = stream.readlines()
    except OSError:
        return {}
    values = {}
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, value = line.partition('=')
        key = key.strip()
        if key:
            values[key] = value.strip().strip('"').strip("'")
    return values


@dataclass(frozen=True)
class Settings:
    app_env: str
    database_url: str
    app_secret_key: str
    aztek_encryption_key: str
    bootstrap_admin_username: str
    bootstrap_admin_password: str
    session_cookie_secure: bool
    session_ttl_seconds: int = 604800
    pairing_ttl_seconds: int = 300
    browser_concurrency: int = 1
    aztek_origin: str = 'https://aztek-tools.combo-interactive.com'
    # Shared SSO login host used by all four game servers; its cookies/origins
    # are equally valid parts of a captured Aztek session.
    aztek_auth_origin: str = 'https://auth.combo-interactive.com'
    local_desktop_mode: bool = False
    local_runtime_dir: str = ''
    local_launcher_secret: str = ''

    def validate(self) -> None:
        if self.app_env not in _DIRECT_APP_ENVS:
            raise ValueError(
                'APP_ENV must be development, test, local-desktop, or production'
            )

        database_url = str(self.database_url).strip()
        if not database_url:
            raise ValueError('DATABASE_URL must not be empty')
        try:
            parsed_database_url = make_url(self.database_url)
        except (ArgumentError, TypeError, ValueError) as exc:
            raise ValueError('DATABASE_URL must be a valid SQLAlchemy URL') from exc
        if (
            self.app_env == 'production'
            and parsed_database_url.get_backend_name() != 'postgresql'
        ):
            raise ValueError('DATABASE_URL must use PostgreSQL in production')

        if type(self.browser_concurrency) is not int or self.browser_concurrency != 1:
            raise ValueError('BROWSER_CONCURRENCY must equal 1')

        if self.app_env != 'test' and len(str(self.app_secret_key)) < 32:
            raise ValueError('APP_SECRET_KEY must contain at least 32 characters')

        encryption_key = str(self.aztek_encryption_key)
        try:
            if _URLSAFE_BASE64_PATTERN.fullmatch(encryption_key) is None:
                raise binascii.Error('not URL-safe base64')
            encoded_key = encryption_key.encode('ascii')
            encoded_key += b'=' * (-len(encoded_key) % 4)
            decoded_key = base64.b64decode(
                encoded_key,
                altchars=b'-_',
                validate=True,
            )
        except (UnicodeEncodeError, binascii.Error, ValueError) as exc:
            raise ValueError(
                'AZTEK_SESSION_ENCRYPTION_KEY must be URL-safe base64'
            ) from exc
        if len(decoded_key) != 32:
            raise ValueError(
                'AZTEK_SESSION_ENCRYPTION_KEY must decode to exactly 32 bytes'
            )

        if self.app_env != 'test':
            for name, origin in (
                ('AZTEK_ORIGIN', self.aztek_origin),
                ('AZTEK_AUTH_ORIGIN', self.aztek_auth_origin),
            ):
                parsed_origin = urlsplit(str(origin))
                if parsed_origin.scheme.lower() != 'https' or not parsed_origin.netloc:
                    raise ValueError(f'{name} must use HTTPS')

        admin_username = str(self.bootstrap_admin_username).strip()
        admin_password = self.bootstrap_admin_password
        if bool(admin_username) != bool(admin_password):
            raise ValueError(
                'BOOTSTRAP_ADMIN_USERNAME and BOOTSTRAP_ADMIN_PASSWORD '
                'must be configured together'
            )
        if admin_password and (
            not isinstance(admin_password, str) or len(admin_password) < 10
        ):
            raise ValueError(
                'BOOTSTRAP_ADMIN_PASSWORD must contain at least 10 characters'
            )

        if self.app_env == 'production':
            missing = [name for name, value in (
                ('APP_SECRET_KEY', self.app_secret_key),
                ('AZTEK_SESSION_ENCRYPTION_KEY', self.aztek_encryption_key),
                ('BOOTSTRAP_ADMIN_USERNAME', admin_username),
                ('BOOTSTRAP_ADMIN_PASSWORD', admin_password),
            ) if not value]
            if missing:
                raise ValueError(
                    'missing production settings: ' + ', '.join(missing)
                )
            if admin_password == 'admin123456':
                raise ValueError(
                    'BOOTSTRAP_ADMIN_PASSWORD must not use the built-in password'
                )
            if not self.session_cookie_secure:
                raise ValueError(
                    'SESSION_COOKIE_SECURE must be true in production'
                )

        if self.local_desktop_mode and self.app_env != 'local-desktop':
            raise ValueError(
                'LOCAL_DESKTOP_MODE requires APP_ENV=local-desktop')
        if self.app_env == 'local-desktop' and not self.local_desktop_mode:
            raise ValueError(
                'APP_ENV=local-desktop requires LOCAL_DESKTOP_MODE=true')
        if self.local_desktop_mode:
            missing_local = [
                name for name, value in (
                    ('LOCAL_RUNTIME_DIR', self.local_runtime_dir),
                    ('LOCAL_LAUNCHER_SECRET', self.local_launcher_secret),
                ) if not str(value).strip()
            ]
            if missing_local:
                raise ValueError(
                    'missing local settings: ' + ', '.join(missing_local))

    @classmethod
    def from_env(cls) -> 'Settings':
        # The real environment wins; the local .env only fills what it leaves out.
        from_file = read_env_file()

        def env(name, default=''):
            value = os.environ.get(name)
            if value is None:
                value = from_file.get(name, default)
            return value

        app_env = env('APP_ENV').strip().lower()
        if app_env not in _ENV_APP_ENVS:
            raise ValueError(
                'APP_ENV must be development, local-desktop, or production'
            )
        production = app_env == 'production'
        local_desktop_mode = parse_env_bool(
            'LOCAL_DESKTOP_MODE', env('LOCAL_DESKTOP_MODE', 'false'))
        session_cookie_secure = parse_env_bool(
            'SESSION_COOKIE_SECURE', env('SESSION_COOKIE_SECURE', 'false'))
        local_runtime_dir = env('LOCAL_RUNTIME_DIR').strip()
        local_launcher_secret = env('LOCAL_LAUNCHER_SECRET').strip()
        app_secret = env('APP_SECRET_KEY').strip()
        encryption_key = env('AZTEK_SESSION_ENCRYPTION_KEY').strip()
        admin_user = env('BOOTSTRAP_ADMIN_USERNAME').strip()
        admin_password = env('BOOTSTRAP_ADMIN_PASSWORD')
        if app_env == 'development' and (not app_secret or not encryption_key):
            # A development run with either generated secret cannot preserve
            # all sessions across restarts.
            warnings.warn(
                'using process-local development secrets; sessions will not survive restart',
                RuntimeWarning,
                stacklevel=2,
            )
        try:
            browser_concurrency = int(env('BROWSER_CONCURRENCY', '1'))
        except ValueError as exc:
            raise ValueError('BROWSER_CONCURRENCY must be an integer') from exc
        resolved_app_secret = app_secret
        resolved_encryption_key = encryption_key
        if app_env == 'development':
            resolved_app_secret = app_secret or secrets.token_urlsafe(48)
            resolved_encryption_key = (
                encryption_key
                or base64.urlsafe_b64encode(os.urandom(32)).decode('ascii')
            )
        settings = cls(
            app_env=app_env,
            database_url=env('DATABASE_URL', 'sqlite:///./all_for_cabal_web.db'),
            app_secret_key=resolved_app_secret,
            aztek_encryption_key=resolved_encryption_key,
            bootstrap_admin_username=admin_user,
            bootstrap_admin_password=admin_password,
            session_cookie_secure=True if production else session_cookie_secure,
            browser_concurrency=browser_concurrency,
            local_desktop_mode=local_desktop_mode,
            local_runtime_dir=local_runtime_dir,
            local_launcher_secret=local_launcher_secret,
        )
        settings.validate()
        return settings
