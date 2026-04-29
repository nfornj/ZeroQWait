# Deployment Fix Notes

This note captures the current way to apply a targeted deployment fix and any related seed step.

## Non-Prod Validation

For the current test deployment flow, run:

```bash
bash deployment/scripts/deploy-test.sh
```

This rebuilds and starts the authoritative local/non-prod Compose stack and publishes:

- `http://localhost:3000`
- `http://localhost:8000`

## Production-Oriented Follow-Up

If the fix also requires data seeding, run the seed helper after the environment is updated:

```bash
chmod +x deploy-db-seed.sh
./deploy-db-seed.sh
```

Use the production deployment path documented in `deployment/docs/README.md` when the change needs to be applied to K3s.

## Verification Checklist

1. Open `https://zeroqwait.com` for production checks or `http://localhost:3000` for non-prod checks.
2. Verify the relevant user flow that prompted the fix.
3. If the change affects search or seeded examples, verify the expected records are present.
4. Confirm the backend health endpoints still respond normally.
