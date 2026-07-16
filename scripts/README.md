# Scripts

## deploy.sh

Automated CloudFormation deployment script that deploys all six stacks in dependency order:

```
01-storage -> 02-auth -> 03-compute -> 04-api -> 05-frontend -> 06-monitoring
```

Each stack is deployed with `aws cloudformation deploy`; the script waits for each stack to reach
`CREATE_COMPLETE` / `UPDATE_COMPLETE` before proceeding to the next. Exported values from earlier stacks are
resolved automatically by CloudFormation `Fn::ImportValue` in downstream templates.

### Usage

```bash
bash scripts/deploy.sh dev|prod|staging
```

The environment argument selects the corresponding parameter file from `cloudformation/parameters/`.

### Requirements

- AWS CLI v2
- Python 3.11+ (for Lambda function code packaging)
- jq (for parsing stack outputs)

---

## Additional Scripts

Other utility scripts may be added under this directory as the project grows (e.g., teardown, seed data, log
tail). All scripts use `set -euo pipefail` for strict error handling.
