"""UI strings and language resolution.

Every user-facing string lives in STRINGS as (zh, en). t() picks the
active language, falls back to English, and finally to the key itself so
a missing translation is obvious instead of silently blank.
"""

from __future__ import annotations

import ctypes
import locale
import os

LANGS = ("zh", "en")
DEFAULT_LANG = "en"

STRINGS: dict[str, tuple[str, str]] = {
    # -- shell -------------------------------------------------------
    "app.subtitle": ("GUI · 本地运行", "GUI · local stack"),
    "app.page_error": ("页面加载出错：{err}", "Page failed to load: {err}"),
    "app.first_run": ("没找到 Decepticon，先去「配置」页安装",
                      "Decepticon not found — install it from Settings"),
    "app.theme.dark": ("深色", "Dark"),
    "app.theme.light": ("浅色", "Light"),

    "nav.dashboard": ("概览", "Overview"),
    "nav.setup": ("配置", "Settings"),
    "nav.terminal": ("执行", "Run"),
    "nav.workspace": ("工作区", "Workspace"),
    "nav.logs": ("日志", "Logs"),
    "nav.about": ("关于", "About"),

    "common.refresh": ("刷新", "Refresh"),
    "common.reload": ("重载", "Reload"),
    "common.start": ("启动", "Start"),
    "common.stop": ("停止", "Stop"),
    "common.clear": ("清空", "Clear"),
    "common.unknown": ("未知", "unknown"),
    "common.not_installed": ("未安装", "not installed"),
    "common.installed": ("已安装", "installed"),

    # -- dashboard ---------------------------------------------------
    "dash.title": ("概览", "Overview"),
    "dash.subtitle": ("Decepticon 运行栈与本机环境",
                      "Decepticon stack and local environment"),
    "dash.recheck": ("重新检查", "Re-check"),
    "dash.stat.docker": ("Docker", "Docker"),
    "dash.stat.stack": ("运行栈", "Stack"),
    "dash.stat.version": ("Decepticon 版本", "Decepticon version"),
    "dash.checks": ("环境检查", "Environment"),
    "dash.checks.hint": ("每次打开页面自动运行", "Runs whenever the page opens"),
    "dash.quick": ("快捷入口", "Shortcuts"),
    "dash.quick.web": ("打开 Web 面板", "Open web dashboard"),
    "dash.quick.neo4j": ("Neo4j 浏览器", "Neo4j browser"),
    "dash.quick.workspace": ("打开工作区目录", "Open workspace folder"),
    "dash.quick.terminal": ("进入终端", "Go to terminal"),
    "dash.next": ("下一步", "Next"),
    "dash.next.body": (
        "1. 确认 Docker Desktop 已启动\n"
        "2. 在「配置」页填入模型 API Key\n"
        "3. 点「启动」，再到「终端」页操作 CLI",
        "1. Make sure Docker Desktop is running\n"
        "2. Add a model API key on the Settings page\n"
        "3. Hit Start, then drive the CLI from Terminal",
    ),
    "dash.containers": ("容器", "Containers"),
    "dash.containers.hint": ("数据来自 docker compose ps",
                             "Fed by docker compose ps"),
    "dash.col.service": ("服务", "Service"),
    "dash.col.state": ("状态", "State"),
    "dash.col.health": ("健康", "Health"),
    "dash.col.ports": ("端口", "Ports"),
    "dash.col.name": ("容器", "Container"),
    "dash.state.running": ("运行中", "running"),
    "dash.state.starting": ("启动中", "starting"),
    "dash.state.partial": ("部分运行", "partial"),
    "dash.state.stopped": ("已停止", "stopped"),
    "dash.state.exited": ("已退出", "exited"),
    "dash.state.created": ("已创建", "created"),
    "dash.state.restarting": ("重启中", "restarting"),
    "dash.msg.checking": ("正在检查环境…", "Checking environment…"),
    "dash.msg.checked": ("环境检查完成", "Environment check complete"),
    "dash.msg.starting": ("正在启动运行栈，首次启动要拉镜像，可能几分钟…",
                          "Starting the stack. First run pulls images and can take a few minutes…"),
    "dash.msg.stopping": ("正在停止容器…", "Stopping containers…"),
    "dash.msg.started": ("启动完成", "Stack started"),
    "dash.msg.stopped": ("停止完成", "Stack stopped"),
    "dash.msg.start_failed": ("启动失败：{detail}", "Start failed: {detail}"),
    "dash.msg.stop_failed": ("停止失败：{detail}", "Stop failed: {detail}"),
    "dash.msg.need_install": ("还没安装 Decepticon，先去「配置」页安装",
                              "Decepticon is not installed — install it from Settings"),
    "dash.msg.web_starting": ("Web 面板没在跑，正在启动…", "Web dashboard is not running, starting it…"),

    # -- doctor ------------------------------------------------------
    "doctor.docker": ("Docker", "Docker"),
    "doctor.daemon": ("Docker 守护进程", "Docker daemon"),
    "doctor.compose": ("Docker Compose", "Docker Compose"),
    "doctor.install": ("Decepticon", "Decepticon"),
    "doctor.env": ("模型密钥", "Model key"),
    "doctor.secrets": ("本地密钥", "Local secrets"),
    "doctor.stack": ("运行栈", "Stack"),
    "doctor.conpty": ("终端后端", "Terminal backend"),
    "doctor.docker.missing": ("未检测到 docker 命令", "docker command not found"),
    "doctor.daemon.connect": ("已连接", "connected"),
    "doctor.daemon.need": ("先安装 Docker Desktop", "Install Docker Desktop first"),
    "doctor.daemon.down": ("Docker Desktop 未启动", "Docker Desktop is not running"),
    "doctor.compose.need": ("需要 Compose v2", "Compose v2 required"),
    "doctor.install.launcher": ("缺少 decepticon.exe", "launcher missing"),
    "doctor.install.noversion": ("已安装（无版本文件）", "installed (no version file)"),
    "doctor.install.none": ("尚未安装", "not installed"),
    "doctor.env.none": ("没有 .env", "no .env file"),
    "doctor.env.nokey": ("未配置任何模型密钥", "no model key configured"),
    "doctor.secrets.weak": ("仍是模板默认值", "still template defaults"),
    "doctor.secrets.ok": ("已生成", "generated"),
    "doctor.stack.ok": ("{n} 个容器运行中", "{n} containers running"),
    "doctor.stack.starting": ("启动中", "starting"),
    "doctor.stack.partial": ("只启动了部分容器", "only part of the stack is up"),
    "doctor.stack.stopped": ("未启动", "not running"),
    "doctor.conpty.ok": ("ConPTY 可用", "ConPTY available"),
    "doctor.conpty.unsupported": ("系统不支持，将用管道模式",
                                  "not supported, falling back to pipes"),
    "doctor.conpty.silent": ("无输出，将用管道模式", "silent, falling back to pipes"),
    "doctor.hint.docker": ("安装 Docker Desktop：https://docs.docker.com/desktop/install/windows-install/",
                           "Install Docker Desktop: https://docs.docker.com/desktop/install/windows-install/"),
    "doctor.hint.daemon": ("打开 Docker Desktop，等托盘图标变绿",
                           "Start Docker Desktop and wait for the tray icon to go green"),
    "doctor.hint.compose": ("Docker Desktop 自带 Compose v2，必要时升级",
                            "Compose v2 ships with Docker Desktop; upgrade if needed"),
    "doctor.hint.install": ("在「配置」页点「安装 Decepticon」",
                            "Use Install Decepticon on the Settings page"),
    "doctor.hint.env": ("在「配置」页填入 API Key 并保存",
                        "Add an API key on the Settings page and save"),
    "doctor.hint.secrets": ("保存配置时会自动生成随机密钥",
                            "Saving the config generates random secrets"),
    "doctor.hint.stack": ("在「概览」页点「启动」", "Press Start on the Overview page"),
    "doctor.hint.conpty": ("Windows 10 1809 及以上才支持 ConPTY",
                           "ConPTY needs Windows 10 1809 or newer"),

    # -- setup -------------------------------------------------------
    "setup.title": ("配置", "Settings"),
    "setup.subtitle": ("直接写 Decepticon 的 .env，不必手敲 onboard",
                       "Edits Decepticon's .env, no need to run onboard by hand"),
    "setup.save": ("保存配置", "Save"),
    "setup.model": ("模型服务", "Model provider"),
    "setup.model.hint": ("填一个能用的 key 即可", "One working key is enough"),
    "setup.provider": ("服务商", "Provider"),
    "setup.apikey": ("API Key", "API Key"),
    "setup.show": ("显示", "Show"),
    "setup.base_url": ("API Base（自定义服务商 / Ollama 地址）",
                       "API base (custom provider / Ollama URL)"),
    "setup.model_id": ("模型名（例如 qwen3-coder:30b）", "Model id (e.g. qwen3-coder:30b)"),
    "setup.profile": ("模型档位", "Model profile"),
    "setup.profile.eco": ("分角色，日常使用", "per-agent tiers, everyday use"),
    "setup.profile.max": ("全用高配模型，重要目标", "all high tier, high-value targets"),
    "setup.profile.test": ("全部低配，只做流程验证", "all low tier, pipeline checks"),
    "setup.ports": ("端口", "Ports"),
    "setup.ports.hint": ("留空用默认值", "leave blank for defaults"),
    "setup.port.default": ("默认 {value}", "default {value}"),
    "setup.install": ("安装与向导", "Install & wizards"),
    "setup.installed": ("已安装 v{version}", "installed v{version}"),
    "setup.btn.install": ("安装 / 更新 Decepticon", "Install / update Decepticon"),
    "setup.btn.onboard": ("运行官方 onboard 向导", "Run the official onboard wizard"),
    "setup.btn.env": ("打开 .env 文件", "Open .env"),
    "setup.btn.home": ("打开安装目录", "Open install folder"),
    "setup.other": ("其他", "Other"),
    "setup.tips.title": ("说明", "Notes"),
    "setup.language": ("Agent 输出语言", "Agent output language"),
    "setup.paths": (".env: {env}\n安装目录: {home}", ".env: {env}\ninstall dir: {home}"),
    "setup.tips": (
        "· 保存时会自动把模板里的默认密码换成随机值\n"
        "· LITELLM_MASTER_KEY / POSTGRES_PASSWORD 等留在 .env 里\n"
        "· 改完端口后需要重启运行栈才生效\n"
        "· 安装脚本来自 decepticon.red，走官方渠道",
        "· Saving replaces template passwords with random values\n"
        "· LITELLM_MASTER_KEY / POSTGRES_PASSWORD stay in .env\n"
        "· Port changes take effect after a stack restart\n"
        "· The install script comes from decepticon.red (official)",
    ),
    "setup.msg.saved": ("配置已保存", "Settings saved"),
    "setup.msg.saved_secrets": ("配置已保存，已生成随机本地密钥",
                                "Settings saved, local secrets generated"),
    "setup.msg.install_started": ("安装脚本已在终端启动，完成后点「重载」",
                                  "Installer started in the terminal; hit Reload when it finishes"),
    "setup.msg.need_install": ("先安装 Decepticon", "Install Decepticon first"),
    "setup.msg.no_env": (".env 还不存在，先保存一次配置",
                         ".env does not exist yet — save the settings once"),

    # -- terminal ----------------------------------------------------
    "term.title": ("终端", "Terminal"),
    "term.subtitle": ("直接跑 Decepticon CLI，快捷键和原版一致",
                      "Runs the real Decepticon CLI with the same key bindings"),
    "term.start": ("启动 CLI", "Start CLI"),
    "term.external": ("外部窗口", "External window"),
    "term.clear": ("清屏", "Clear"),
    "term.status.idle": ("未启动", "not started"),
    "term.status.running": ("运行中 · {backend}", "running · {backend}"),
    "term.status.stopped": ("已停止", "stopped"),
    "term.status.failed": ("启动失败", "start failed"),
    "term.status.exited": ("已退出 (code {code})", "exited (code {code})"),
    "term.no_cli": (
        "找不到 Decepticon CLI。\n"
        "请先在「配置」页安装 Decepticon，或在设置里指定自定义命令。",
        "Decepticon CLI not found.\n"
        "Install Decepticon from Settings, or point the terminal at a custom command.",
    ),
    "term.spawn_failed": ("启动失败：{err}", "Failed to start: {err}"),
    "term.need_cli": ("找不到 Decepticon CLI，先安装", "Decepticon CLI not found — install it first"),

    # -- run page ----------------------------------------------------
    "run.title": ("执行", "Run"),
    "run.subtitle": ("填目标，点开始；输出和报告都在这个窗口里",
                     "Enter a target, press start; output and reports stay here"),
    "run.target": ("目标", "Target"),
    "run.target.hint": ("URL 或 IP，例如 https://demo.example.com",
                        "URL or IP, e.g. https://demo.example.com"),
    "run.notes": ("说明", "Notes"),
    "run.notes.hint": ("范围、凭据、豁免项（可留空）", "scope, credentials, exclusions (optional)"),
    "run.mode": ("模式", "Mode"),
    "run.mode.auto": ("自动执行", "Auto"),
    "run.mode.plan": ("先出计划", "Plan first"),
    "run.start": ("启动并执行", "Start & run"),
    "run.send": ("发送任务", "Send task"),
    "run.clear": ("清屏", "Clear"),
    "run.external": ("外部窗口", "External"),
    "run.reports": ("产出文件", "Output"),
    "run.reports.empty": ("还没有产出文件", "No output files yet"),
    "run.reports.hint": ("来自 workspace 目录", "from the workspace folder"),
    "run.open": ("打开", "Open"),
    "run.open_dir": ("打开目录", "Open folder"),
    "run.preview": ("预览", "Preview"),
    "run.col.file": ("文件", "File"),
    "run.need_target": ("先填目标地址", "Enter a target first"),
    "run.starting": ("正在启动 Decepticon，首次启动要拉镜像，请稍等…",
                     "Starting Decepticon. The first run pulls images, hold on…"),
    "run.waiting": ("等待 CLI 就绪，出现输入提示后会自动发送任务…",
                    "Waiting for the CLI; the task is sent once the prompt shows…"),
    "run.wait_timeout": ("等太久了，看到输入提示后点「发送任务」",
                         "Still waiting — press Send task when the prompt appears"),
    "run.sent": ("任务已发送，输出会实时显示在下方",
                 "Task sent; output streams below"),
    "run.no_cli": ("找不到 Decepticon CLI，先在「配置」页安装",
                   "Decepticon CLI not found — install it from Settings"),
    "run.objective": ("对 {target} 在授权范围内进行渗透测试，结束后输出完整报告。{notes}",
                      "Run an authorized penetration test against {target} and produce a full report. {notes}"),
    "run.stopped": ("已停止", "Stopped"),


    # -- workspace ---------------------------------------------------
    "ws.title": ("工作区", "Workspace"),
    "ws.explorer": ("在资源管理器打开", "Open in Explorer"),
    "ws.files": ("文件", "Files"),
    "ws.preview": ("预览", "Preview"),
    "ws.too_large": ("{name}\n\n文件 {size} MB，太大就不在这预览了，双击用系统程序打开。",
                     "{name}\n\n{size} MB — too large to preview here. Double-click to open it externally."),
    "ws.binary": ("{name}\n\n二进制文件（{size} 字节），双击用系统程序打开。",
                  "{name}\n\nBinary file ({size} bytes). Double-click to open it externally."),
    "ws.read_failed": ("读取失败：{err}", "Read failed: {err}"),

    # -- logs --------------------------------------------------------
    "logs.title": ("日志", "Logs"),
    "logs.subtitle": ("跟随 docker compose logs", "Tails docker compose logs"),
    "logs.tab.container": ("容器日志", "Container logs"),
    "logs.tab.app": ("应用日志", "App log"),
    "logs.follow": ("开始跟随", "Follow"),
    "logs.all": ("全部", "All"),
    "logs.exit": ("[进程退出 {code}]", "[process exited {code}]"),

    # -- about -------------------------------------------------------
    "about.title": ("关于", "About"),
    "about.subtitle": ("授权、归属与免责声明", "License, attribution, disclaimer"),
    "about.license": ("许可与归属", "License & attribution"),
    "about.upstream": ("上游仓库", "Upstream repo"),
    "about.docs": ("上游文档", "Upstream docs"),
    "about.apache": ("Apache 2.0 全文", "Apache 2.0 text"),
    "about.disclaimer": ("免责声明", "Disclaimer"),
    "about.disclaimer.body": (
        "只在你拥有书面授权的系统或网络上使用 Decepticon。未经授权访问计算机系统"
        "属于违法行为。本程序不提供任何形式的担保，使用风险由使用者自行承担。",
        "Use Decepticon only on systems or networks you are authorized in writing to test. "
        "Unauthorized access to computer systems is illegal. This program comes with no "
        "warranty of any kind; you use it at your own risk.",
    ),
    "about.notice": (
        "Decepticon GUI v{version}\n"
        "Copyright 2026 Decepticon GUI contributors\n"
        "\n"
        "本程序是 PurpleAILAB/Decepticon 的图形前端，以 Apache License 2.0 分发。\n"
        "上游项目：https://github.com/PurpleAILAB/Decepticon\n"
        "上游版权：Copyright PurpleAILAB and Decepticon contributors\n"
        "上游许可：Apache License, Version 2.0\n"
        "\n"
        "本仓库不包含上游源代码，运行时调用用户本机安装的 Decepticon\n"
        "（官方安装脚本部署于 %USERPROFILE%\\.decepticon）与 Docker 运行栈。\n"
        "\n"
        "修改说明：本程序为独立新增的图形界面与进程编排层，未修改上游代码。\n"
        "上游项目名称、版权声明与许可证文本保持原样。\n"
        "\n"
        "完整许可证文本见仓库根目录 LICENSE 文件。\n"
        "This project is not affiliated with or endorsed by PurpleAILAB.",

        "Decepticon GUI v{version}\n"
        "Copyright 2026 Decepticon GUI contributors\n"
        "\n"
        "A graphical front end for PurpleAILAB/Decepticon, distributed under\n"
        "the Apache License, Version 2.0.\n"
        "Upstream: https://github.com/PurpleAILAB/Decepticon\n"
        "Upstream copyright: PurpleAILAB and Decepticon contributors\n"
        "Upstream license: Apache License, Version 2.0\n"
        "\n"
        "No upstream source code is bundled. At runtime this program drives the\n"
        "user's own Decepticon installation (installed by the official script\n"
        "into %USERPROFILE%\\.decepticon) and its Docker stack.\n"
        "\n"
        "Changes: this is an independently written GUI and process orchestration\n"
        "layer; upstream code is not modified. Upstream names, copyright notices\n"
        "and license text are kept intact.\n"
        "\n"
        "The full license text is in the LICENSE file at the repository root.\n"
        "This project is not affiliated with or endorsed by PurpleAILAB.",
    ),
}


def _detect_windows_language() -> str | None:
    try:
        langid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        primary = langid & 0x3FF
        if primary == 0x04:  # Chinese
            return "zh"
        if primary == 0x09:
            return "en"
    except Exception:  # noqa: BLE001 - not on Windows
        pass
    return None


def _detect_locale_language() -> str | None:
    try:
        code = (locale.getlocale()[0] or "").lower()
    except (ValueError, TypeError):
        code = ""
    if not code:
        try:
            code = os.environ.get("LANG", "").lower()
        except Exception:  # noqa: BLE001
            code = ""
    if code.startswith("zh"):
        return "zh"
    if code.startswith("en"):
        return "en"
    return None


def system_language() -> str:
    """Best guess at the OS UI language, falling back to English."""
    return _detect_windows_language() or _detect_locale_language() or DEFAULT_LANG


class Translator:
    def __init__(self, lang: str | None = None):
        self.lang = lang if lang in LANGS else system_language()

    def set(self, lang: str):
        if lang in LANGS:
            self.lang = lang

    def t(self, key: str, **kwargs) -> str:
        entry = STRINGS.get(key)
        if not entry:
            return key
        index = LANGS.index(self.lang)
        text = entry[index] or entry[LANGS.index(DEFAULT_LANG)] or key
        if kwargs:
            try:
                return text.format(**kwargs)
            except (KeyError, IndexError):
                return text
        return text

    # short alias used across the views
    __call__ = t


translator = Translator()
t = translator.t
