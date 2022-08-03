# action-s3-artifact
GitHub action to upload and deploy S3 artifacts

# Usage

See [action.yml](action.yml).

Upload:
```yaml
steps:
  - name: Upload
    uses: moneymeets/action-s3-artifact@master
    with:
      cmd: upload
      config: s3-artifact-config.yml
      artifacts_s3_path: s3://YourBucketHere/${{ github.event.repository.name }}/${{ github.sha }}/
```

Deploy
```yaml
  - name: Deploy
    uses: moneymeets/action-s3-artifact@master
    with:
      cmd: deploy
      config: s3-artifact-config.yml
      artifacts_s3_path: s3://YourBucketHere/${{ github.event.repository.name }}/${{ github.sha }}/
      environment: ${{ github.event.deployment.environment }}
```

Config example:

```yaml
# s3-artifact-config.yml

target_buckets:
  dev: dummy.dev
  live: dummy.live
local_artifacts_path: dist
default_cache_control: 'public, max-age=60, must-revalidate'
custom_metadata:
  - path: 'assets/css/*.css'
    cache_control: 'public, max-age=31536000, must-revalidate'
    mime_type: 'text/css' # Optional, some default mime types are hardcoded in action.py
  - path: 'assets/js/*.js'
    cache_control: 'public, max-age=31536000, must-revalidate'
```