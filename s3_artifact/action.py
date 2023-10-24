import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

from dataclasses_json import dataclass_json
from yaml import safe_load

DEFAULT_MIME_TYPES = {
    ".css": "text/css",
    ".html": "text/html",
    ".js": "application/javascript",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".pdf": "application/pdf",
    ".png": "image/png",
}

S3_NO_PROGRESS = "--no-progress"
S3_CP_OPTIONS = f"--recursive {S3_NO_PROGRESS}"
S3_SYNC_OPTIONS = f"--delete {S3_NO_PROGRESS}"


@dataclass_json
@dataclass(frozen=True)
class S3ArtifactCustomMetadataConfig:
    path: str
    cache_control: str
    mime_type: Optional[str] = None


@dataclass_json
@dataclass(frozen=True)
class S3ArtifactConfig:
    target_buckets: dict[str, str]
    local_artifacts_path: str
    default_cache_control: str
    custom_metadata: tuple[S3ArtifactCustomMetadataConfig, ...] = ()


def _run_commands(commands: Sequence[str], dry_run: bool):
    for command in commands:
        print(command)

        if not dry_run:
            subprocess.run(command, shell=True, check=True)


def deploy(config: S3ArtifactConfig, artifacts_s3_path: str, environment: str) -> Sequence[str]:
    target = f"s3://{config.target_buckets[environment]}"
    return (
        f"aws s3 ls {artifacts_s3_path}",  # Check if artifact exists, otherwise fail deployment
        # cp and sync because there are problems syncing all files - https://github.com/aws/aws-cli/issues/3273
        f"aws s3 cp {artifacts_s3_path} {target} {S3_CP_OPTIONS}",
        f"aws s3 sync {artifacts_s3_path} {target} {S3_SYNC_OPTIONS}",
    )


def upload(config: S3ArtifactConfig, target: str) -> Sequence[str]:
    def _prepare_metadata_command(cache_config: S3ArtifactCustomMetadataConfig):
        content_type = cache_config.mime_type or DEFAULT_MIME_TYPES[Path(cache_config.path).suffix]
        content_type_option = f"--content-type '{content_type}'"

        return (
            f"aws s3 cp {target} {target} {S3_CP_OPTIONS} --exclude '*' --include {cache_config.path} "
            f"--metadata-directive REPLACE {content_type_option} --cache-control '{cache_config.cache_control}'"
        )

    def _get_default_cache_control():
        return f"--cache-control '{config.default_cache_control}'" if config.default_cache_control else ""

    return (
        f"aws s3 sync {config.local_artifacts_path} {target} {_get_default_cache_control()} {S3_SYNC_OPTIONS}",
        *(_prepare_metadata_command(custom_metadata) for custom_metadata in config.custom_metadata),
    )


def get_website_config() -> S3ArtifactConfig:
    return S3ArtifactConfig.from_dict(safe_load(Path(os.environ["CONFIG"]).read_text()))


def main():
    cmd = os.environ["CMD"]
    config = get_website_config()
    artifacts_s3_path = os.environ["ARTIFACTS_S3_PATH"]

    match cmd:
        case "deploy":
            commands = deploy(config, artifacts_s3_path, os.environ["ENVIRONMENT"])
        case "upload":
            commands = upload(config, artifacts_s3_path)
        case _:
            raise NotImplementedError(f"Unknown command - {cmd}")

    _run_commands(commands, os.environ.get("DRY_RUN", "false").lower() in ("y", "yes", "t", "true", "on", "1"))


if __name__ == "__main__":
    main()
