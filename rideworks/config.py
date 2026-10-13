"""Optional repository-local startup settings, without mutating the environment."""

from dataclasses import dataclass
import os
from pathlib import Path
import shlex

from .errors import RideWorksError

KEYS = frozenset({'FLASK_DEBUG', 'FLASK_RUN_PORT', 'RIDEWORKS_DATA_DIR'})
STRAVA_KEYS = frozenset({'STRAVA_CLIENT_ID', 'STRAVA_CLIENT_SECRET'})


class ConfigurationError(RideWorksError):
    """A selected local setting cannot be interpreted safely."""


@dataclass(frozen=True)
class StartupConfig:
    data_dir: str | None
    port: int
    debug: bool


def repository_root():
    """Editable checkout root; an installed wheel has no repository .env."""
    candidate = Path(__file__).resolve().parent.parent
    return candidate if (candidate / 'pyproject.toml').is_file() else None


def _dotenv(root, selected, keys=KEYS):
    if root is None:
        return
    path = Path(root) / '.env'
    if not path.exists():
        return
    try:
        lines = path.read_text(encoding='utf-8').splitlines()
    except (OSError, UnicodeError) as exc:
        raise ConfigurationError('Cannot read repository .env') from exc
    protected = set(selected)
    for line_number, line in enumerate(lines, 1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('export '):
            line = line[7:].lstrip()
        key, separator, raw = line.partition('=')
        key = key.strip()
        # Unrelated legacy settings/secrets are neither parsed nor exported.
        # Higher-priority values also bypass lower-priority file parsing.
        if key not in keys or key in protected:
            continue
        try:
            tokens = shlex.split(raw, comments=True, posix=True)
        except ValueError as exc:
            raise ConfigurationError(f'Invalid {key} syntax in .env line {line_number}') from exc
        if not separator or len(tokens) > 1:
            raise ConfigurationError(f'Invalid {key} syntax in .env line {line_number}; quote values containing spaces')
        selected[key] = tokens[0] if tokens else ''


def startup_config(data_dir=None, port=None, *, repo_root=None, environ=None):
    """CLI > exported environment > repo .env > established defaults.

    Only the selected port/debug values are validated; a lower-priority invalid
    port cannot defeat a valid explicit CLI override. There is no expansion,
    shell execution, global environment mutation or directory search from cwd.
    """
    environment = os.environ if environ is None else environ
    selected = {key: environment[key] for key in KEYS if key in environment}
    if data_dir is not None:
        selected['RIDEWORKS_DATA_DIR'] = data_dir
    if port is not None:
        selected['FLASK_RUN_PORT'] = port
    _dotenv(repository_root() if repo_root is None else repo_root, selected)
    raw_port = str(selected.get('FLASK_RUN_PORT', '8766')).strip()
    if not raw_port.isascii() or not raw_port.isdecimal() or not 1 <= int(raw_port) <= 65535:
        raise ConfigurationError('FLASK_RUN_PORT / serve --port must be an integer from 1 to 65535')
    raw_debug = str(selected.get('FLASK_DEBUG', '0')).strip().lower()
    if raw_debug not in ('0', '1', 'false', 'true', 'no', 'yes', 'off', 'on'):
        raise ConfigurationError('FLASK_DEBUG must be 0/1, false/true, no/yes or off/on')
    chosen_data = selected.get('RIDEWORKS_DATA_DIR')
    if chosen_data is not None and not str(chosen_data).strip():
        raise ConfigurationError('RIDEWORKS_DATA_DIR / --data-dir must not be empty')
    return StartupConfig(chosen_data, int(raw_port), raw_debug in ('1', 'true', 'yes', 'on'))


def strava_credentials(*, repo_root=None, environ=None):
    """Read credentials only for explicit Strava commands; never expose in config repr."""
    environment = os.environ if environ is None else environ
    selected = {key: environment[key] for key in STRAVA_KEYS if key in environment}
    _dotenv(repository_root() if repo_root is None else repo_root, selected, STRAVA_KEYS)
    identity = selected.get('STRAVA_CLIENT_ID', '').strip()
    secret = selected.get('STRAVA_CLIENT_SECRET', '').strip()
    if not identity.isascii() or not identity.isdecimal() or int(identity) < 1 or not secret:
        raise ConfigurationError('Configure STRAVA_CLIENT_ID and STRAVA_CLIENT_SECRET locally before connecting to Strava')
    return identity, secret
