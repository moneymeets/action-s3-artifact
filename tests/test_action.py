import json
import os
from dataclasses import asdict
from tempfile import NamedTemporaryFile
from typing import Sequence
from unittest import TestCase
from unittest.mock import patch

import yaml

from s3_artifact import action
from s3_artifact.action import (
    S3ArtifactConfig,
    S3ArtifactCustomMetadataConfig,
    deploy,
    get_website_config,
    main,
    upload,
)

ARTIFACTS_BUCKET = "s3://dummy-artifacts"


def _get_website_config(cache: Sequence[S3ArtifactCustomMetadataConfig] = ()) -> S3ArtifactConfig:
    return S3ArtifactConfig(
        target_buckets={"dev": "dummy-dev", "live": "dummy-live"},
        local_artifacts_path="dist/",
        default_cache_control="max-age=60",
        custom_metadata=tuple(cache),
    )


def _get_metadata_command():
    return (
        f"aws s3 cp {ARTIFACTS_BUCKET} {ARTIFACTS_BUCKET} --recursive --no-progress --exclude '*' --include '*.html' "
        f"--metadata '{json.dumps({
            "X-Frame-Options": "SAMEORIGIN",
            "Content-Security-Policy": "frame-src 'self'; frame-ancestors 'self'; object-src 'none';",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "X-Content-Type-Options": "nosniff",
        })}'"
    )


def _get_upload_commands(pattern: str, mime_type: str, max_age: str) -> tuple[str, str, str]:
    return (
        f"aws s3 sync dist/ {ARTIFACTS_BUCKET} --cache-control 'max-age=60' --delete --no-progress",
        f"aws s3 cp {ARTIFACTS_BUCKET} {ARTIFACTS_BUCKET} --recursive --no-progress --exclude '*' "
        f"--include {pattern} --metadata-directive REPLACE --content-type '{mime_type}' --cache-control '{max_age}'",
        _get_metadata_command(),
    )


class ActionTest(TestCase):
    def test_upload(self):
        # Test success without special metadata
        self.assertEqual(
            first=upload(config=_get_website_config(), target=ARTIFACTS_BUCKET),
            second=(
                f"aws s3 sync dist/ {ARTIFACTS_BUCKET} --cache-control 'max-age=60' --delete --no-progress",
                _get_metadata_command(),
            ),
        )

        # Test success with special metadata
        self.assertEqual(
            first=upload(
                _get_website_config(
                    (S3ArtifactCustomMetadataConfig(path="assets/js/*.js", cache_control="max-age=5"),),
                ),
                ARTIFACTS_BUCKET,
            ),
            second=_get_upload_commands("assets/js/*.js", "application/javascript", "max-age=5"),
        )

        # Test success with special metadata and explicit mime type
        self.assertEqual(
            first=upload(
                _get_website_config(
                    (
                        S3ArtifactCustomMetadataConfig(
                            path="*.js",
                            cache_control="max-age=5",
                            mime_type="text/javascript",
                        ),
                    ),
                ),
                ARTIFACTS_BUCKET,
            ),
            second=_get_upload_commands("*.js", "text/javascript", "max-age=5"),
        )

        # Check KeyError for missing configured mime type
        self.assertRaises(
            KeyError,
            upload,
            _get_website_config((S3ArtifactCustomMetadataConfig(path="assets/*.dummy", cache_control="max-age=3600"),)),
            ARTIFACTS_BUCKET,
        )

    def test_deploy(self):
        target = "s3://dummy-dev"
        self.assertEqual(
            first=deploy(_get_website_config(), ARTIFACTS_BUCKET, "dev"),
            second=(
                f"aws s3 ls {ARTIFACTS_BUCKET}",
                f"aws s3 cp {ARTIFACTS_BUCKET} {target} --recursive --no-progress",
                f"aws s3 sync {ARTIFACTS_BUCKET} {target} --delete --no-progress",
            ),
        )

    @staticmethod
    def _test_main(cmd):
        @patch.dict(
            os.environ,
            {"DRY_RUN": "true", "CMD": cmd, "ARTIFACTS_S3_PATH": "s3://dummy/", "ENVIRONMENT": "dev"},
        )
        @patch.object(action, "get_website_config")
        @patch.object(action, "_run_commands")
        def _test(mock_get_config, mock_run_commands):
            main()
            mock_get_config.assert_called()
            mock_run_commands.assert_called()

        _test()

    @patch.object(action, "upload")
    def test_main_upload(self, mock_upload):
        self._test_main("upload")
        mock_upload.assert_called()

    @patch.object(action, "deploy")
    def test_main_deploy(self, mock_deploy):
        self._test_main("deploy")
        mock_deploy.assert_called()

    def test_main_error(self):
        self.assertRaises(NotImplementedError, self._test_main, "error")

    def test_get_website_config(self):
        with NamedTemporaryFile() as tmp_file:
            yaml_content = yaml.safe_dump(asdict(_get_website_config()))
            tmp_file.write(yaml_content.encode())
            tmp_file.flush()
            with patch.dict(os.environ, {"CONFIG": tmp_file.name}):
                self.assertEqual(get_website_config(), _get_website_config())
