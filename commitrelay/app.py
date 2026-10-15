"""Local/GitHub readers, trusted parsers, Apprise delivery, and checkpoints."""
from __future__ import annotations
import base64
from dataclasses import dataclass
from datetime import datetime, timezone
from fnmatch import fnmatch
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import sqlite3
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import yaml


class ConfigError(Exception):
    pass


@dataclass
class Sync:
    file: Path
    name: str
    enabled: bool
    source: dict
    parser: object
    destinations: dict


def project_root(config: Path) -> Path:
    for parent in config.resolve().parents:
        if (parent / "pyproject.toml").exists():
            return parent
    return config.resolve().parent.parent


def resolve_parser(config_path: Path, script: str) -> Path:
    """Resolve trusted local scripts, including packaged example parsers."""
    project = (project_root(config_path) / script).resolve()
    if project.is_file():
        return project
    if script.startswith("commitrelay/parsers/") and ".." not in Path(script).parts:
        return (Path(__file__).resolve().parent.parent / script).resolve()
    return project


def load_sync(path: Path) -> Sync:
    try:
        obj = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(str(exc)) from exc
    if not isinstance(obj, dict):
        raise ConfigError("Expected YAML mapping")
    name = obj.get("name")
    if not isinstance(name, str) or not name or not all(x.isalnum() or x in "_-" for x in name):
        raise ConfigError("name must use letters, digits, '-' or '_'")
    if not isinstance(obj.get("enabled"), bool):
        raise ConfigError("enabled must be true or false")
    src = obj.get("source")
    if not isinstance(src, dict) or src.get("type") not in ("local_git", "github"):
        raise ConfigError("source.type must be local_git or github")
    for key in ("folder", "pattern"):
        if not isinstance(src.get(key), str) or not src[key]:
            raise ConfigError("source." + key + " is required")
    folder = PurePosixPath(src["folder"])
    if folder.is_absolute() or ".." in folder.parts:
        raise ConfigError("source.folder must be a safe repository-relative path")
    if src["type"] == "local_git" and not isinstance(src.get("root"), str):
        raise ConfigError("source.root is required for local_git")
    if src["type"] == "github" and (not isinstance(src.get("repository"), str) or src["repository"].count("/") != 1):
        raise ConfigError("source.repository must be owner/repo")
    dest = obj.get("destinations", {})
    if not isinstance(dest, dict) or any(k != "telegram" for k in dest):
        raise ConfigError("Only destinations.telegram is currently implemented")
    if any(not isinstance(v, bool) for v in dest.values()):
        raise ConfigError("destination switches must be booleans")
    parser = obj.get("parser")
    if parser is not None:
        if not isinstance(parser, dict) or not isinstance(parser.get("script"), str):
            raise ConfigError("parser must be null or {script: path}")
        if parser.get("options") is not None and not isinstance(parser["options"], dict):
            raise ConfigError("parser.options must be a mapping")
        if not resolve_parser(path, parser["script"]).is_file():
            raise ConfigError("parser script not found: " + parser["script"])
    return Sync(path, name, obj["enabled"], src, parser, dest)


def discover(directory: Path):
    rows = []
    for p in sorted(directory.glob("*.yaml")):
        try:
            rows.append((p, load_sync(p), None))
        except ConfigError as exc:
            rows.append((p, None, str(exc)))
    return rows


def token_env():
    return os.getenv("COMMITRELAY_TELEGRAM_TOKEN_ENV", "TELEGRAM_BOT_TOKEN")


def chat_env():
    return os.getenv("COMMITRELAY_TELEGRAM_CHAT_ENV", "TELEGRAM_CHAT_ID")


def credential_status():
    missing = [k for k in (token_env(), chat_env()) if not os.getenv(k)]
    return "READY" if not missing else "MISSING_SECRET: " + ", ".join(missing)


def parsed_content(sync: Sync, raw: str):
    if sync.parser is None:
        return raw.strip() or None
    path = resolve_parser(sync.file, sync.parser["script"])
    spec = importlib.util.spec_from_file_location("commitrelay_parser_" + sha256(str(path).encode()).hexdigest()[:12], path)
    if not spec or not spec.loader:
        raise ConfigError("cannot load parser")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    callback = getattr(module, "parse", None)
    if not callable(callback):
        raise ConfigError("parser must define parse(content, options)")
    result = callback(raw, sync.parser.get("options") or {})
    if result is None:
        return None
    if not isinstance(result, str):
        raise ConfigError("parser must return a string or None")
    return result.strip() or None


def git(root, *args):
    p = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    if p.returncode:
        raise ConfigError(p.stderr.strip() or "git command failed")
    return p.stdout


def local_files(src):
    root = Path(src["root"]).expanduser().resolve()
    if not root.is_dir():
        raise ConfigError("local source not found: " + str(root))
    ref = src.get("branch", "HEAD")
    folder = src["folder"].strip("/")
    paths = git(root, "ls-tree", "-r", "--name-only", ref, "--", folder).splitlines()
    for path in paths:
        if str(PurePosixPath(path).parent) == folder and fnmatch(PurePosixPath(path).name, src["pattern"]):
            yield "local:" + str(root), path, git(root, "show", ref + ":" + path)


def github_api(repo, resource, token):
    headers = {"User-Agent": "CommitRelay/0.1", "Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request("https://api.github.com/repos/" + repo + "/" + resource, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        raise ConfigError("GitHub API HTTP " + str(exc.code) + " for " + repo) from exc


def github_files(src):
    repo, ref = src["repository"], src.get("branch", "main")
    token = os.getenv(src.get("token_env", "COMMITRELAY_GITHUB_TOKEN"))
    tree = github_api(repo, "git/trees/" + urllib.parse.quote(ref, safe="") + "?recursive=1", token)
    if tree.get("truncated"):
        raise ConfigError("GitHub tree truncated; choose a smaller source")
    folder = src["folder"].strip("/")
    for item in tree.get("tree", []):
        path = item.get("path", "")
        if item.get("type") != "blob" or str(PurePosixPath(path).parent) != folder or not fnmatch(PurePosixPath(path).name, src["pattern"]):
            continue
        resource = "contents/" + urllib.parse.quote(path, safe="/") + "?ref=" + urllib.parse.quote(ref, safe="")
        file = github_api(repo, resource, token)
        if file.get("encoding") != "base64":
            raise ConfigError("Unsupported GitHub content encoding: " + path)
        yield "github:" + repo + "@" + ref, path, base64.b64decode(file["content"]).decode("utf-8")


def source_files(sync):
    return local_files(sync.source) if sync.source["type"] == "local_git" else github_files(sync.source)


class Checkpoints:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute("CREATE TABLE IF NOT EXISTS delivered (config TEXT, source TEXT, path TEXT, destination TEXT, hash TEXT, at TEXT, PRIMARY KEY(config,source,path,destination))")

    def same(self, key, digest):
        row = self.db.execute("SELECT hash FROM delivered WHERE config=? AND source=? AND path=? AND destination=?", key).fetchone()
        return row is not None and row[0] == digest

    def mark(self, key, digest):
        self.db.execute("INSERT INTO delivered(config,source,path,destination,hash,at) VALUES(?,?,?,?,?,?) ON CONFLICT(config,source,path,destination) DO UPDATE SET hash=excluded.hash,at=excluded.at",
                        (*key, digest, datetime.now(timezone.utc).isoformat()))
        self.db.commit()

    def close(self):
        self.db.close()


def telegram_send(title, path, body, test=False):
    """Send with Apprise rather than maintaining our own Telegram HTTP client.

    Never log or put credentials in tracked configuration. Long reports are
    delivered as a Markdown attachment rather than silently truncated.
    """
    token, chat = os.getenv(token_env()), os.getenv(chat_env())
    if not token or not chat:
        raise ConfigError(credential_status())
    try:
        from apprise import Apprise, NotifyFormat
        from apprise.attachment import AttachMemory

        notifier = Apprise()
        # Construct the URL only in memory; never display it in diagnostics.
        if not notifier.add(f"tgram://{token}/{chat}/"):
            raise ConfigError("Cannot configure Telegram destination through Apprise")
        if test:
            success = notifier.notify(
                body="CommitRelay test message", body_format=NotifyFormat.TEXT
            )
        else:
            filename = PurePosixPath(path).name
            message = title + "\n" + filename + "\n\n" + body
            if len(message) <= 4096:
                success = notifier.notify(
                    body=message, body_format=NotifyFormat.TEXT
                )
            else:
                attachment = AttachMemory(
                    content=body.encode("utf-8"),
                    name=filename,
                    mimetype="text/markdown",
                )
                success = notifier.notify(
                    body=title + "\n" + filename + "\nSee attached Markdown report.",
                    attach=attachment,
                    body_format=NotifyFormat.TEXT,
                )
        if not success:
            raise ConfigError("Telegram delivery through Apprise was not confirmed")
    except ImportError as exc:
        raise ConfigError("Apprise is not installed: pip install -e .") from None
    except ConfigError:
        raise
    except Exception:
        # Library errors can contain service URLs with credentials.
        # Do not surface their raw messages or exception chaining.
        raise ConfigError("Telegram delivery through Apprise failed (details redacted)") from None


def run_sync(sync: Sync, checkpoints: Checkpoints, dry_run=False, baseline=False):
    if not sync.enabled:
        print("SKIP " + sync.name + ": disabled")
        return 0, 0
    sent = skipped = 0
    for source, path, raw in source_files(sync):
        try:
            body = parsed_content(sync, raw)
        except Exception as exc:
            raise ConfigError("Parser failed on " + path + ": " + str(exc)) from exc
        if body is None:
            skipped += 1
            continue
        digest = sha256(body.encode()).hexdigest()
        for destination, enabled in sync.destinations.items():
            if not enabled:
                continue
            key = (sync.name, source, path, destination)
            if checkpoints.same(key, digest):
                skipped += 1
                continue
            if baseline:
                checkpoints.mark(key, digest)
                print(f"BASELINED {sync.name}: {path} -> {destination} (nothing sent)")
            elif dry_run:
                print(f"WOULD SEND {sync.name}: {path} -> {destination} ({len(body)} characters)")
            elif destination == "telegram":
                telegram_send(sync.name, path, body)
                checkpoints.mark(key, digest)
                print(f"SENT {sync.name}: {path} -> {destination}")
            sent += 1
    return sent, skipped
