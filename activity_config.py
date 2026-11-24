"""Local installation settings. This file contains no installation credentials.

On a NAS, site_config.json lives beside the real Python files, outside the
document root. Only the runtime files are linked into the public directory.
An unconfigured checkout permits browsing/generation but disables management.
"""
import ipaddress
import json
from pathlib import Path


def load(path=None):
    path = Path(path) if path else Path(__file__).resolve().with_name('site_config.json')
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        data = {}
    if not isinstance(data, dict):
        raise ValueError('Invalid installation settings')
    return data


SETTINGS = load()
OWNER = SETTINGS.get('owner', '')
HOSTS = tuple(SETTINGS.get('admin_hosts', []))
NETWORKS = tuple(ipaddress.ip_network(n) for n in SETTINGS.get('lan_networks', []))
SITE = Path(SETTINGS.get('site_dir', str(Path(__file__).resolve().parent)))
STATE = Path(SETTINGS.get('state_dir', str(Path.home() / '.escursioni-library')))
