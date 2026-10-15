"""Command-line interface for CommitRelay."""
import argparse
import os
from pathlib import Path
import shlex
import subprocess
import sys
import yaml
from .app import Checkpoints, ConfigError, credential_status, discover, load_sync, run_sync, telegram_send


def valid_configurations(folder):
    return [(path, sync) for path, sync, error in discover(folder) if sync]


def pick(folder, name):
    valid = valid_configurations(folder)
    if name:
        matches = [p for p, s in valid if s.name == name]
        if not matches:
            raise ConfigError("No configuration named " + name)
        return matches[0]
    if not valid:
        raise ConfigError("No valid configurations; use commitrelay add")
    for i, (path, sync) in enumerate(valid, 1):
        print(f"{i}. {sync.name} ({path.name})")
    choice = input("Configuration number: ").strip()
    if not choice.isdigit() or not 1 <= int(choice) <= len(valid):
        raise ConfigError("Invalid selection")
    return valid[int(choice) - 1][0]


def ask(label, default=""):
    answer = input(f"{label}" + (f" [{default}]" if default else "") + ": ").strip()
    return answer or default


def yesno(label, default=False):
    answer = input(f"{label} [{'Y/n' if default else 'y/N'}]: ").strip().lower()
    return default if not answer else answer in ("y", "yes")


def add(folder, name=None):
    folder.mkdir(parents=True, exist_ok=True)
    name = name or ask("Sync name (letters, numbers, - or _)")
    if not name or not all(c.isalnum() or c in "-_" for c in name):
        raise ConfigError("Invalid configuration name")
    path = folder / (name + ".yaml")
    if path.exists():
        raise ConfigError("Already exists: " + str(path))
    print("Where are the files? 1. Local Git checkout  2. GitHub repository")
    kind = ask("Source type", "1")
    if kind == "1":
        p = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)
        root = ask("Local repository folder", p.stdout.strip() if p.returncode == 0 else str(Path.cwd()))
        source = {"type": "local_git", "root": root, "branch": "HEAD"}
        probe = subprocess.run(["git", "-C", root, "rev-parse", "--show-toplevel"], capture_output=True)
        if probe.returncode:
            print("WARNING: local Git checkout cannot be accessed; review the YAML.")
    elif kind == "2":
        source = {"type": "github", "repository": ask("Repository (owner/name)"), "branch": ask("Branch", "main")}
    else:
        raise ConfigError("Choose 1 or 2")
    source["folder"] = ask("Folder within repository", "reports")
    source["pattern"] = ask("File pattern", "*.md")
    print("Parser: 1. None (entire file)  2. Trusted Python script")
    choice = ask("Parser", "1")
    if choice == "1":
        parser = None
    elif choice == "2":
        parser = {"script": ask("Python script relative to project root"), "options": {}}
    else:
        raise ConfigError("Choose 1 or 2")
    telegram = yesno("Enable Telegram destination?", True)
    enabled = yesno("Enable this sync now?", False)
    data = {"name": name, "enabled": enabled, "source": source, "parser": parser, "destinations": {"telegram": telegram}}
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    print("Created", path)
    try:
        load_sync(path)
    except ConfigError as exc:
        print("BROKEN:", exc, "(edit the YAML before running)")


def edit(folder, name):
    path = pick(folder, name)
    editor = os.getenv("VISUAL") or os.getenv("EDITOR")
    if not editor:
        print("Open this file in your editor:", path)
        return
    subprocess.run(shlex.split(editor) + [str(path)], check=True)
    load_sync(path)
    print("Valid:", path)


def toggle(folder, name, enabled):
    path = pick(folder, name)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["enabled"] = enabled
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    print(("Enabled " if enabled else "Disabled ") + data["name"])


def list_configs(folder):
    rows = discover(folder)
    if not rows:
        print("No syncs found; use commitrelay add.")
    for path, sync, error in rows:
        if error:
            print(f"BROKEN       {path.name}: {error}")
        elif not sync.enabled:
            print(f"DISABLED     {sync.name}")
        elif sync.destinations.get("telegram") and credential_status() != "READY":
            print(f"UNCONFIGURED {sync.name}: {credential_status()}")
        else:
            print(f"CONFIGURED   {sync.name}")


def doctor(folder, no_send=False, yes=False, targets=False):
    broken = 0
    for path, sync, error in discover(folder):
        if error:
            print(f"BROKEN {path.name}: {error}")
            broken += 1
        else:
            print(f"{'ENABLED' if sync.enabled else 'DISABLED'} {sync.name}")
    ready = credential_status() == "READY"
    print("Destinations:")
    print("  1. Telegram — " + ("configured" if ready else "unconfigured / missing secrets"))
    print("  2. All implemented destinations")
    print("Private GitHub sources may need COMMITRELAY_GITHUB_TOKEN (read-only).")
    if no_send:
        return broken
    if yes and not targets:
        raise ConfigError("Specify -y --all or -y --telegram to test explicitly")
    if not yes:
        if not yesno("Send harmless test message?", False):
            return broken
        selection = ask("Choose destination number", "1")
        if selection not in ("1", "2"):
            raise ConfigError("Invalid destination selection")
    if not ready:
        print("SKIP Telegram: " + credential_status())
        return broken + 1
    telegram_send("", "", "", test=True)
    print("Telegram test delivered")
    return broken


def selected(folder, name=None, all_=False):
    if all_:
        rows = discover(folder)
        errors = [(p, e) for p, _, e in rows if e]
        if errors:
            raise ConfigError("Broken YAML: " + "; ".join(f"{p}: {e}" for p, e in errors))
        return [s for _, s, _ in rows if s]
    if name:
        p = Path(name)
        return [load_sync(p if p.is_file() else pick(folder, name))]
    raise ConfigError("Provide --all or --config NAME")


def read_job(path):
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError("Cannot load job " + str(path) + ": " + str(exc)) from exc
    if not isinstance(data, dict) or not isinstance(data.get("enabled"), bool) or not isinstance(data.get("configs"), list):
        raise ConfigError("Job needs enabled: true/false and configs: [names]")
    if any(not isinstance(c, str) for c in data["configs"]):
        raise ConfigError("Job configs must contain names")
    return data


def install_hook(repo, job):
    root = Path(repo).expanduser().resolve()
    result = subprocess.run(["git", "-C", str(root), "rev-parse", "--git-path", "hooks"], capture_output=True, text=True)
    if result.returncode:
        raise ConfigError("Not a Git repository: " + str(root))
    hook_dir = Path(result.stdout.strip())
    if not hook_dir.is_absolute():
        hook_dir = root / hook_dir
    target = hook_dir / "post-commit"
    if target.exists():
        raise ConfigError("Refusing to overwrite existing hook: " + str(target))
    job = Path(job).resolve()
    if not job.is_file():
        raise ConfigError("Job YAML not found: " + str(job))
    command = shlex.quote(sys.executable) + " -m commitrelay run --job " + shlex.quote(str(job))
    target.write_text("#!/bin/sh\n" + command + "\n", encoding="utf-8")
    target.chmod(0o755)
    print("Installed local Git post-commit hook:", target)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="commitrelay", description="Git-native file-to-message dispatcher")
    ap.add_argument("--configs", type=Path, default=Path("configs"), help="Directory of sync YAML files")
    ap.add_argument("--state", type=Path, default=Path(".commitrelay-state/deliveries.db"), help="Persistent local SQLite checkpoint path")
    sp = ap.add_subparsers(dest="command", required=True)
    a = sp.add_parser("add", help="Create a sync interactively")
    a.add_argument("name", nargs="?")
    sp.add_parser("list", help="List sync statuses, including broken YAML")
    e = sp.add_parser("edit", help="Select a sync and open in $EDITOR")
    e.add_argument("name", nargs="?")
    for verb in ("enable", "disable"):
        sub = sp.add_parser(verb, help=verb.title() + " a sync")
        sub.add_argument("name", nargs="?")
    d = sp.add_parser("doctor", help="Diagnose and optionally send test messages")
    yesno_group = d.add_mutually_exclusive_group()
    yesno_group.add_argument("-n", action="store_true", help="Diagnose only; never send")
    yesno_group.add_argument("-y", action="store_true", help="Send explicit test messages")
    destinations = d.add_mutually_exclusive_group()
    destinations.add_argument("--all", action="store_true", help="All implemented destinations")
    destinations.add_argument("--telegram", action="store_true", help="Telegram only")
    r = sp.add_parser("run", help="Read, parse and dispatch publishable changes")
    select = r.add_mutually_exclusive_group(required=True)
    select.add_argument("--all", action="store_true")
    select.add_argument("--config", help="Sync name or config YAML path")
    select.add_argument("--job", type=Path, help="Job YAML")
    r.add_argument("--dry-run", action="store_true", help="Preview: no network sends or checkpoint writes")
    h = sp.add_parser("hook", help="Manage local Git hooks")
    h.add_argument("action", choices=["install"])
    h.add_argument("--repo", default=".")
    h.add_argument("--job", required=True)
    args = ap.parse_args(argv)
    try:
        if args.command == "add":
            add(args.configs, args.name)
        elif args.command == "list":
            list_configs(args.configs)
        elif args.command == "edit":
            edit(args.configs, args.name)
        elif args.command in ("enable", "disable"):
            toggle(args.configs, args.name, args.command == "enable")
        elif args.command == "doctor":
            return doctor(args.configs, no_send=args.n, yes=args.y, targets=args.all or args.telegram)
        elif args.command == "hook":
            install_hook(args.repo, args.job)
        elif args.command == "run":
            if args.job:
                job = read_job(args.job)
                if not job["enabled"]:
                    print("SKIP disabled job:", args.job)
                    return 0
                syncs = [load_sync(args.configs / (name + ".yaml")) for name in job["configs"]]
            else:
                syncs = selected(args.configs, args.config, args.all)
            checkpoints = Checkpoints(args.state)
            try:
                for sync in syncs:
                    sent, skipped = run_sync(sync, checkpoints, args.dry_run)
                    print(f"{sync.name}: {sent} deliveries planned/sent, {skipped} skipped")
            finally:
                checkpoints.close()
        return 0
    except (ConfigError, OSError, subprocess.CalledProcessError) as exc:
        print("ERROR:", exc, file=sys.stderr)
        return 1
