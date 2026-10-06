"""Public, source-aware build preparation; no evaluator data or credentials."""
from __future__ import annotations

import io
import json
import tarfile
from pathlib import PurePosixPath

from benchmarks.polybench.test_environment import docker_environment
from hx.check_execution import command_check
from hx.models import HXError
from hx.process import clean_env
from hx.store import atomic_write


def recipe(repo, workspace):
    # Deliberately narrow: this is derived from the old public Svelte manifest
    # and rollup/_build configuration, not guessed for arbitrary repositories.
    manifest = workspace / "package.json"
    if repo != "sveltejs/svelte" or not manifest.is_file():
        return None
    data = json.loads(manifest.read_text())
    scripts = data.get("scripts", {})
    if scripts.get("build") == "node src/shared/_build.js && rollup -c":
        version = "svelte-public-build@1"
        outputs = ["compiler", "ssr", "shared.js", "src/generators/dom/shared.ts"]
        source = "Public package.json, rollup.config.js and src/shared/_build.js"
    elif (scripts.get('build') == 'node src/shared/_build.js && rollup -c && rollup -c rollup.store.config.js'
          and str(data.get('version', '')).startswith('1.')
          and all((workspace / name).is_file() for name in ['rollup.config.js',
              'rollup.store.config.js', 'src/shared/_build.js', 'src/index.ts',
              'src/server-side-rendering/register.js', 'store.js'])
          and "src/generators/dom/shared.ts" in (workspace / 'src/shared/_build.js').read_text()
          and "store.umd.js" in (workspace / 'rollup.store.config.js').read_text()):
        version = 'svelte-public-build@6-v1-store'
        outputs = ['compiler', 'ssr', 'shared.js', 'src/generators/dom/shared.ts', 'store.umd.js']
        source = 'Public Svelte1 shared generator and compiler/store Rollup configs'
    elif (scripts.get('build') == 'node src/shared/_build.js && rollup -c && rollup -c rollup.store.config.js'
          and str(data.get('version', '')).startswith('2.')
          and all((workspace / name).is_file() for name in ['rollup.config.js',
              'rollup.store.config.js', 'src/shared/_build.js', 'src/index.ts',
              'src/ssr/register.js', 'store.js'])):
        version = 'svelte-public-build@4-rollup-store'
        outputs = ['compiler', 'ssr', 'shared.js', 'src/compile/shared.ts', 'store.umd.js']
        source = 'Public Svelte2 package.json, shared/_build.js and Rollup compiler/store configs'
    elif scripts.get("build") == "npm run build:main && npm run build:shared && npm run build:ssr":
        configs = {name: "rollup/rollup.config." + name + ".js"
                   for name in ("main", "shared", "ssr")}
        generated_shared = (
            str(data.get('version', '')).startswith('1.')
            and scripts.get('build:main') == 'node src/shared/_build.js && rollup -c ' + configs['main']
            and (workspace / 'src/shared/_build.js').is_file()
            and 'src/generators/dom/shared.ts' in (workspace / 'src/shared/_build.js').read_text()
        )
        if not all((scripts.get("build:" + name) == "rollup -c " + config
                    or (name == 'main' and generated_shared))
                   and (workspace / config).is_file() for name, config in configs.items()):
            raise HXError("Unsupported Svelte build layout; validate a new public recipe")
        version = "svelte-public-build@2-legacy-rollup"
        outputs = ["compiler", "ssr", "shared.js"]
        if generated_shared:
            version = 'svelte-public-build@7-v1-generated-shared'
            outputs.append('src/generators/dom/shared.ts')
        source = "Public package.json and rollup/rollup.config.{main,shared,ssr}.js"
    elif (scripts.get('build') == 'rollup -c && npm run tsd'
          and scripts.get('tsd') == 'tsc -p src/compiler --emitDeclarationOnly && tsc -p src/runtime --emitDeclarationOnly'
          and str(data.get('version', '')).startswith('3.')
          and not (workspace / 'src/runtime/ssr.ts').exists()
          and all((workspace / name).is_file() for name in ['rollup.config.js',
              'src/compiler/index.ts', 'src/runtime/index.ts', 'src/runtime/internal/ssr.ts',
              'src/compiler/tsconfig.json', 'src/runtime/tsconfig.json'])
          and {p.name for p in (workspace / 'src/runtime').iterdir() if p.is_dir()}
              == {'motion', 'animate', 'store', 'transition', 'internal', 'easing'}
          and all((workspace / ('src/runtime/' + name + '/index.ts')).is_file()
              for name in ['motion', 'animate', 'store', 'transition', 'internal', 'easing'])
          and all(marker in (workspace / 'rollup.config.js').read_text() for marker in [
              "fs.readdirSync('src/runtime')", 'input: `src/runtime/${dir}/index.ts`',
              'file: `${dir}/index.mjs`', 'file: `${dir}/index.js`'])):
        version = 'svelte-public-build@5-internal-ssr'
        outputs = ['compiler.js', 'compiler.js.map', 'compiler.d.ts', 'index.js',
                   'index.mjs', 'types', 'src/compiler/compile/internal_exports.ts',
                   'motion', 'animate', 'store', 'transition', 'internal', 'easing']
        source = 'Public Svelte3 internal-SSR layout, exact rollup runtime-directory outputs and tsd stages'
    elif (scripts.get("build") == "rollup -c && npm run tsd"
          and scripts.get("tsd") == "tsc -p src/compiler --emitDeclarationOnly && tsc -p src/runtime --emitDeclarationOnly"
          and str(data.get("version", "")).startswith("3.")
          and all((workspace / name).is_file() for name in ["rollup.config.js",
              "src/compiler/index.ts", "src/runtime/index.ts", "src/runtime/ssr.ts",
              "src/compiler/tsconfig.json", "src/runtime/tsconfig.json"])):
        version = "svelte-public-build@3-rollup-typescript"
        outputs = ["compiler.js", "compiler.mjs", "compiler.js.map", "compiler.mjs.map",
                   "compiler.d.ts", "index.js", "index.mjs", "ssr.js", "ssr.mjs", "types",
                   "src/compiler/compile/internal_exports.ts"]
        outputs += ["animate", "easing", "internal", "motion", "store", "transition"]
        # Historical Svelte3 releases predate the action runtime directory.
        # Do not request ownership of a path the source build cannot produce.
        if (workspace / 'src/runtime/action/index.ts').is_file():
            outputs.append('action')
        version = 'svelte-public-build@8-source-runtime-outputs'
        source = "Public Svelte3 package.json, rollup.config.js and compiler/runtime tsconfig.json"
    else:
        raise HXError("Unsupported Svelte build layout; validate a new public recipe")
    return {"version": version, "argv": ["npm", "run", "build"],
        "outputs": outputs,
        "test_hint": ["./node_modules/.bin/mocha", "--opts", "mocha.opts",
                      "--reporter", "json", "--exit"],
        "source": source}


def owned_archive(payload, basename, limit=32_000_000):
    """Repack only regular generated artifacts; reject links and escapes."""
    output = io.BytesIO()
    size = 0
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:*") as source:
        with tarfile.open(fileobj=output, mode="w") as target:
            for member in source:
                path = PurePosixPath(member.name)
                if (path.is_absolute() or ".." in path.parts or not path.parts
                        or path.parts[0] != basename or not (member.isfile() or member.isdir())):
                    raise HXError("Unsafe generated artifact archive")
                size += member.size
                if size > limit:
                    raise HXError("Generated artifact archive exceeds budget")
                member.uid = member.gid = 1000
                member.uname = member.gname = ""
                member.mode = 0o755 if member.isdir() else 0o644
                target.addfile(member, source.extractfile(member) if member.isfile() else None)
    return output.getvalue()


def prepare_generated(container, workdir, workspace, case):
    plan = recipe(case.get("repo"), workspace)
    if not plan:
        return None
    # All recipe paths must be ignored/untracked. Never grant special write
    # permissions to tracked source or to installed dependency trees.
    from benchmarks.polybench.containers import command
    for name in plan["outputs"]:
        if command(container, ["git", "ls-files", "--", name], workdir).strip():
            raise HXError("Generated-output recipe overlaps tracked source: " + name)
        try:
            command(container, ["git", "check-ignore", "--", name], workdir)
        except HXError as error:
            raise HXError("Generated-output path is not ignored: " + name) from error
        probe = container.exec_run(["test", "-e", workdir + "/" + name])
        link = container.exec_run(["test", "-L", workdir + "/" + name])
        if link.exit_code == 0:
            raise HXError("Generated-output path is a symlink: " + name)
        if probe.exit_code == 0:
            chunks, _ = container.get_archive(workdir + "/" + name)
            payload = bytearray()
            for chunk in chunks:
                payload.extend(chunk)
                if len(payload) > 40_000_000:
                    raise HXError("Generated artifact transfer exceeds budget")
            parent = str(PurePosixPath(workdir + "/" + name).parent)
            if not container.put_archive(parent, owned_archive(bytes(payload), PurePosixPath(name).name)):
                raise HXError("Generated artifact ownership staging failed")
        # Clear old outputs. Subsequent tests cannot load an image's stale build.
        command(container, ["rm", "-rf", "--", name], workdir, "1000:1000")
    return plan


def build_check(container, workdir, workspace, case, directory, settings, control, emit):
    plan = recipe(case.get("repo"), workspace)
    if not plan:
        return None
    control()
    record = {**plan, "user": "1000:1000", "model_calls": 0,
              "scope": "Public build prerequisite; not behavioral test evidence"}
    atomic_write(directory / "recipe.json", json.dumps(record, indent=2).encode())
    check = command_check("public_build", ["docker", "exec", "-u", "1000:1000",
        *docker_environment(), "-w", workdir, container.id, *plan["argv"]],
        workspace, clean_env(), directory / "build", settings, control, emit)
    atomic_write(directory / "result.json", json.dumps(check.model_dump(), indent=2).encode())
    emit("tool.worker_preflight", {**record, "passed": check.passed})
    return check


def worker_environment_check(client, case, workspace, directory, settings, control, emit):
    """Exercise actual offline worker population/build before admitting model work."""
    from benchmarks.polybench.containers import command, create, populate
    container = None
    try:
        control()
        container, workdir = create(client, case, offline=True)
        populate(container, workdir, workspace, case)
        check = build_check(container, workdir, workspace, case, directory / "build",
                            settings, control, emit)
        if check and not check.passed:
            raise HXError("Worker source build failed before model admission")
        control()
        probe = command(container, ['node', '-e',
            "const fs=require('fs');const p=require('./package.json');"
            "if(!Object.keys(p.scripts||{}).some(k=>k==='test'||/^test[:-]/.test(k)))throw Error('No test script');"
            "require.resolve('mocha');fs.writeFileSync('.hx-worker-preflight','ok');"
            "fs.unlinkSync('.hx-worker-preflight');console.log(process.getuid());"],
            workdir, '1000:1000').decode().strip()
        if probe != '1000' or command(container, ['git', 'status', '--porcelain'],
                                      workdir, '1000:1000').strip():
            raise HXError("Worker preflight requires UID1000 and unchanged tracked source")
        receipt = {'passed': True, 'case': case['id'], 'offline': True, 'worker_uid': 1000,
                   'image_id': case['image_id'], 'container_id': container.id,
                   'source_clean': True, 'public_build_passed': check.passed if check else None,
                   'model_calls': 0, 'official_calls': 0,
                   'limitation': 'Worker preparation/dependency smoke; not behavioral correctness.'}
        atomic_write(directory / 'receipt.json', json.dumps(receipt, indent=2).encode())
        return receipt
    except Exception as error:
        atomic_write(directory / 'failure.json', json.dumps({'passed': False,
            'case': case['id'], 'error': str(error), 'model_calls': 0}, indent=2).encode())
        raise
    finally:
        if container:
            container.remove(force=True)
