# Deployment: Streamlit Community Cloud

Target selected by the user: Streamlit Community Cloud.
Repository: https://github.com/tantancodes/california-housing-atlas
Current status: repository published and CI passed; account-owner sign-in/terms acceptance pending.

1. Publish only this independent implementation and `data/public/` to a GitHub repository.
   Do not commit `data/raw`, `data/processed`, `data/reference`, `data/cache`, `.env` or secrets.
2. In https://share.streamlit.io choose **Create app**, then the repository and branch **main**.
3. Set main file to **app.py**; Advanced settings → Python **3.12**.
4. Keep `ATLAS_ENABLE_PRIVATE` unset/disabled. No secrets are needed for the included public snapshot.
   `requirements.txt` installs locked packages. A database is optional and not needed for the default demo.
5. Choose an available subdomain and deploy. Verify all 58 counties, vintage and metric controls, map-to-chart
   selection, county CSV download, methodology and mobile layout on the live URL before announcing completion.

[Official Community Cloud deployment guide](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy).
Account creation, new OAuth access and terms acceptance may need the account owner's action.

The first deployment intentionally includes only public Census data. Reference CSVs have no verified
redistribution license, and private CRMLS outputs must never be uploaded. FRED context requires an explicit
local fetch and is not bundled. Public county values are ACS owner-occupied housing values, not transaction prices.

## Container alternative

```bash
docker build -t california-housing-atlas .
docker run --name atlas-public --rm -p 127.0.0.1:8502:8501 california-housing-atlas
```

Open http://127.0.0.1:8502. A nonroot user runs Streamlit, and `/_stcore/health` is the health endpoint.
Explicit COPY instructions exclude private data and reference assets. The container binds to 0.0.0.0 internally;
the example only exposes it on local loopback. A hosting provider should terminate HTTPS, route WebSockets,
set a restart policy and provide memory sufficient for GeoPandas/Streamlit. No public upload endpoint exists.

## Optional hosted PostgreSQL

Set `DATABASE_URL` in the provider's secret store, run `python -m atlas.cli database` against a reachable
PostgreSQL 17 service, and enable `ATLAS_PUBLIC_BACKEND=postgres`. Use a database role appropriate to the
job: migration/loading needs schema write access; dashboard reads can use a separate SELECT-only role.
Do not expose PostgreSQL publicly without provider access controls. Community Cloud's default snapshot
mode avoids this operational requirement entirely.
