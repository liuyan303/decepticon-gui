"""Environment checks shown on the overview page."""

from __future__ import annotations

from . import conpty, dockerops, paths
from .envfile import EnvFile
from .i18n import t


def check_docker_cli():
    version = dockerops.docker_version()
    if version:
        return True, version.replace("Docker version ", "")
    return False, t("doctor.docker.missing")


def check_daemon():
    if not dockerops.docker_binary():
        return False, t("doctor.daemon.need")
    if dockerops.daemon_running():
        return True, t("doctor.daemon.connect")
    return False, t("doctor.daemon.down")


def check_compose():
    ok, version = dockerops.compose_ok() if dockerops.docker_binary() else (False, "")
    return (True, f"v{version}") if ok else (False, t("doctor.compose.need"))


def check_install():
    if paths.is_installed():
        version = paths.installed_version()
        return True, (f"v{version}" if version else t("doctor.install.noversion"))
    if paths.compose_path().is_file():
        return False, t("doctor.install.launcher")
    return False, t("doctor.install.none")


def check_env():
    path = paths.env_path()
    if not path.is_file():
        return False, t("doctor.env.none")
    env = EnvFile(path).load()
    providers = env.configured_providers()
    if providers:
        return True, " · ".join(providers[:3])
    return False, t("doctor.env.nokey")


def check_secrets():
    path = paths.env_path()
    if not path.is_file():
        return False, t("doctor.env.none")
    env = EnvFile(path).load()
    weak = [k for k in ("LITELLM_MASTER_KEY", "POSTGRES_PASSWORD", "NEO4J_PASSWORD")
            if env.is_placeholder(k)]
    return (not weak), (t("doctor.secrets.weak") if weak else t("doctor.secrets.ok"))


def check_stack():
    state, rows = dockerops.stack_state()
    if state == "healthy":
        return True, t("doctor.stack.ok", n=len(rows))
    if state == "starting":
        return False, t("doctor.stack.starting")
    if state == "partial":
        return False, t("doctor.stack.partial")
    return False, t("doctor.stack.stopped")


def check_conpty():
    if not conpty.available():
        return False, t("doctor.conpty.unsupported")
    if conpty.usable():
        return True, t("doctor.conpty.ok")
    return False, t("doctor.conpty.silent")


CHECKS = [
    ("docker", "doctor.docker", check_docker_cli, "doctor.hint.docker"),
    ("daemon", "doctor.daemon", check_daemon, "doctor.hint.daemon"),
    ("compose", "doctor.compose", check_compose, "doctor.hint.compose"),
    ("install", "doctor.install", check_install, "doctor.hint.install"),
    ("env", "doctor.env", check_env, "doctor.hint.env"),
    ("secrets", "doctor.secrets", check_secrets, "doctor.hint.secrets"),
    ("stack", "doctor.stack", check_stack, "doctor.hint.stack"),
    ("conpty", "doctor.conpty", check_conpty, "doctor.hint.conpty"),
]


def run_all(progress=None):
    results = []
    for key, title_key, fn, hint_key in CHECKS:
        try:
            ok, detail = fn()
        except Exception as exc:  # noqa: BLE001 - a broken check must not kill the UI
            ok, detail = False, str(exc)
        item = {"key": key, "title": t(title_key), "ok": ok,
                "detail": detail, "hint": t(hint_key)}
        results.append(item)
        if progress:
            progress(item)
    return results
