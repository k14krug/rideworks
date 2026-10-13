"""Exact HTTP trust boundary shared by routes, form actions and browser OAuth."""
from dataclasses import dataclass
from urllib.parse import urlsplit

from .config import normalize_public_origin


@dataclass(frozen=True)
class HTTPAccess:
    public_origin: str | None = None

    def __post_init__(self):
        object.__setattr__(self, 'public_origin', normalize_public_origin(self.public_origin))

    def allows_host(self, host, port):
        hosts = {f'127.0.0.1:{port}', f'localhost:{port}'}
        if self.public_origin:
            public = urlsplit(self.public_origin)
            hosts.add(public.netloc)
            if public.port is None:
                hosts.add(f'{public.netloc}:{80 if public.scheme == "http" else 443}')
        return isinstance(host, str) and host.isascii() and host.lower() in hosts

    def allows_origin(self, origin, port):
        origins = {f'http://127.0.0.1:{port}', f'http://localhost:{port}'}
        if self.public_origin:
            origins.add(self.public_origin)
        return origin in origins

    def callback_url(self, port):
        return (self.public_origin or f'http://127.0.0.1:{port}') + '/strava/callback'

    @property
    def callback_domain(self):
        return urlsplit(self.public_origin).hostname if self.public_origin else '127.0.0.1'
