"""Thin wrapper around the Docker CLI and the Decepticon launcher."""

from __future__ import annotations

import json
import os
import shutil

from . import paths
from .proc import Stream, run

CORE_SERVICES = ["litellm", "postgres", "neo4j", "sandbox", "langgraph", "skillogy"]

def _env():
    env = dict(os.environ)
    env["DECEPTICON_HOME"] = str(paths.decepticon_home())
    stack = (env.get("DECEPTICON_STACK_NAME") or "").strip()
    env["COMPOSE_PROJECT_NAME"] = f"decepticon-{stack}" if stack else "decepticon"
    return env


def docker_binary():
    return shutil.which("docker")


def docker_version():
    if not docker_binary():
        return None
    rc, out, _ = run(["docker", "--version"], timeout=10)
    return out.strip() if rc == 0 else None


def daemon_running():
    if not docker_binary():
        return False
    rc, _, _ = run(["docker", "info", "--format", "{{.ServerVersion}}"], timeout=20)
    return rc == 0


def compose_ok():
    if not docker_binary():
        return False
    rc, out, _ = run(["docker", "compose", "version", "--short"], timeout=15)
    return rc == 0, out.strip()


def compose(args, cwd=None, timeout=120, env=None):
    cmd = ["docker", "compose"]
    if paths.compose_path().is_file():
        cmd += ["-f", str(paths.compose_path())]
    if paths.env_path().is_file():
        cmd += ["--env-file", str(paths.env_path())]
    cmd += list(args)
    return run(cmd, cwd=cwd or paths.decepticon_home(), timeout=timeout,
               env=env or _env())


def compose_cmd(args):
    """Return the argv for compose without running it (used by the terminal)."""
    cmd = ["docker", "compose"]
    if paths.compose_path().is_file():
        cmd += ["-f", str(paths.compose_path())]
    if paths.env_path().is_file():
        cmd += ["--env-file", str(paths.env_path())]
    return cmd + list(args)


def compose_async(args, timeout=900, on_done=None, cwd=None):
    from .proc import run_async
    return run_async(compose_cmd(args), cwd=cwd or paths.decepticon_home(),
                     env=_env(), timeout=timeout, on_done=on_done)


def _parse_ps(output):
    output = (output or "").strip()
    if not output:
        return []
    try:
        data = json.loads(output)
        if isinstance(data, dict):
            data = [data]
        if isinstance(data, list):
            return [d for d in data if isinstance(d, dict)]
    except ValueError:
        pass
    rows = []
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    return rows


def containers():
    """Return [{name, service, state, health, ports}] for the current stack."""
    if not paths.compose_path().is_file():
        return []
    rc, out, err = compose(["ps", "--all", "--format", "json"], timeout=45)
    if rc != 0:
        return []
    result = []
    for item in _parse_ps(out):
        service = item.get("Service") or item.get("service") or ""
        state = (item.get("State") or item.get("state") or "").lower()
        health = (item.get("Health") or item.get("health") or "").lower()
        ports = item.get("Ports") or item.get("ports") or ""
        if not ports:
            publishers = item.get("Publishers") or []
            parts = []
            for pub in publishers:
                if not isinstance(pub, dict):
                    continue
                published = pub.get("PublishedPort") or pub.get("published_port")
                if published:
                    parts.append(f"{published}->{pub.get('TargetPort', '')}")
            ports = ", ".join(parts)
        result.append({
            "service": service,
            "name": item.get("Name") or item.get("name") or service,
            "state": state,
            "health": health,
            "ports": str(ports),
        })
    result.sort(key=lambda r: (r["service"] not in CORE_SERVICES, r["service"]))
    return result


def stack_state():
    rows = containers()
    if not rows:
        return "stopped", rows
    services = [r for r in rows if r["service"] in CORE_SERVICES]
    if not services:
        return "partial", rows
    running = [r for r in services if r["state"] == "running"]
    if len(running) == len(services):
        unhealthy = [r for r in running if r["health"] in ("unhealthy", "starting")]
        return ("healthy" if not unhealthy else "starting"), rows
    if running:
        return "starting", rows
    return "stopped", rows


def logs_stream(services, on_line, on_exit=None, tail=200):
    args = ["logs", "-f", "--tail", str(tail), "--no-color", "--timestamps"]
    args += list(services)
    return Stream(compose_cmd(args), cwd=paths.decepticon_home(), env=_env(),
                  on_line=on_line, on_exit=on_exit).start()


def web_url():
    env = _read_env_value("WEB_PORT") or "3000"
    return f"http://127.0.0.1:{env}"


def neo4j_url():
    port = _read_env_value("NEO4J_HTTP_PORT") or "7474"
    return f"http://127.0.0.1:{port}"


def langgraph_url():
    port = _read_env_value("LANGGRAPH_PORT") or "2024"
    return f"http://127.0.0.1:{port}"


def _read_env_value(key):
    from .envfile import EnvFile
    path = paths.env_path()
    if not path.is_file():
        return None
    return EnvFile(path).load().get(key) or None


def cli_command():
    """How to open the interactive Decepticon CLI on this machine."""
    launcher = paths.launcher_path()
    if launcher:
        return str(launcher)
    if paths.compose_path().is_file():
        return compose_cmd(["run", "--rm", "cli"])
    return None
