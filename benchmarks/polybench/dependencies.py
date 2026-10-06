"""Fetch missing public runtime dependencies before tests or model execution."""
from pathlib import Path

from hx.models import HXError


def share_public_fixture(container, repo):
    """Copy only the known public tokenizer cache into the non-root test home."""
    if repo != "huggingface/transformers":
        return False
    fixture = container.exec_run(["grep", "-Fq", "HuggingFaceM4/tiny-random-idefics",
        "tests/models/idefics/test_processor_idefics.py"], workdir="/testbed")
    if fixture.exit_code:
        return False
    code = (
        "from huggingface_hub import snapshot_download;from pathlib import Path;import shutil,os;"
        "p=Path(snapshot_download('HuggingFaceM4/tiny-random-idefics',token=False,local_files_only=True));"
        "src=p.parent.parent;assert src.name=='models--HuggingFaceM4--tiny-random-idefics';"
        "dst=Path('/tmp/hx-home/.cache/huggingface/hub')/src.name;"
        "dst.parent.mkdir(parents=True,exist_ok=True);"
        "shutil.copytree(src,dst,dirs_exist_ok=True,symlinks=False);"
        "[(os.chmod(root,0o755),[os.chmod(str(Path(root)/f),0o644) for f in files]) "
        "for root,dirs,files in os.walk(dst)];print('public tokenizer accessible to UID1000')"
    )
    result = container.exec_run(["python", "-c", code], workdir="/testbed",
        environment={"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"})
    if result.exit_code:
        raise HXError("public fixture cache transfer failed: " + result.output.decode(errors="replace")[-1500:])
    return True


def prepare_dependencies(container, repo, directory: Path, base: str):
    if repo not in {"microsoft/vscode", "huggingface/transformers"}:
        return
    workdir = "/testbed"
    if repo == "huggingface/transformers":
        fixture = container.exec_run(["grep", "-Fq", "HuggingFaceM4/tiny-random-idefics",
            "tests/models/idefics/test_processor_idefics.py"], workdir=workdir)
        if fixture.exit_code:
            return
    head = container.exec_run(["git", "rev-parse", "HEAD"], workdir=workdir)
    if head.exit_code or head.output.decode().strip() != base:
        raise HXError("container command failed: dependency bootstrap requires the unchanged upstream base")
    directory.mkdir(parents=True, exist_ok=True)
    if repo == "huggingface/transformers":
        result = container.exec_run(["timeout", "300", "python", "-c",
            "from huggingface_hub import snapshot_download;"
            "p=snapshot_download('HuggingFaceM4/tiny-random-idefics',token=False,"
            "allow_patterns=['*.json','*.model','*.txt']);print('public fixture snapshot:',p)"],
            workdir=workdir, environment={"HF_HUB_OFFLINE": "0", "TRANSFORMERS_OFFLINE": "0"})
        (directory / "public-fixture-bootstrap.txt").write_bytes(result.output)
        if result.exit_code:
            raise HXError(f"container command failed: public fixture bootstrap failed ({result.exit_code}): "
                          + result.output.decode(errors="replace")[-1200:])
        return
    result = container.exec_run(["timeout", "300", "yarn", "electron"], workdir=workdir)
    (directory / "electron-bootstrap.txt").write_bytes(result.output)
    if result.exit_code:
        raise HXError(f"container command failed: Electron dependency bootstrap failed ({result.exit_code}): "
                      + result.output.decode(errors="replace")[-1200:])
    probe = container.exec_run(["node", "-e",
        "const fs=require('fs'),p=require('./product.json');"
        "const path='.build/electron/'+p.applicationName;"
        "fs.accessSync(path,fs.constants.X_OK);"
        "console.log(JSON.stringify({executable:path,version:fs.readFileSync('.build/electron/version','utf8')}));"],
        workdir=workdir)
    (directory / "electron-probe.txt").write_bytes(probe.output)
    if probe.exit_code:
        raise HXError("container command failed: Electron bootstrap did not produce the expected executable")
