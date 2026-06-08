# ABC Payments — Q4 2025 Dashboard

An interactive, password-protected Streamlit dashboard for the ABC payments
dataset, plus five data-driven insights. Free to host on Streamlit Community
Cloud.

---

## What's in here

| File | Purpose |
|---|---|
| `app.py` | The dashboard (login gate, filters, KPIs, charts, insights). |
| `data_q4_2025.csv` | Cleaned, analysis-ready data (Q4 2025 only). **This is what the app reads.** |
| `prepare_data.py` | The reproducible cleaning step that produced the CSV above. |
| `requirements.txt` | Python dependencies. |
| `.streamlit/config.toml` | Theme / colours. |
| `.streamlit/secrets.toml.example` | Template for the login credentials. |
| `.gitignore` | Keeps the real `secrets.toml` out of git. |

### The data decision
The raw export covered Mar–Dec 2025, but Mar–Sep held only a few hundred
net-*negative* rows (refunds / pre-launch test activity). **98.8% of orders and
all positive revenue sit in Q4**, so the dashboard uses Oct–Dec 2025 only — the
deliberate "use only the data you need" choice. Re-run `python prepare_data.py`
(with the raw CSV present) to regenerate the cleaned file.

---

## 1) Run it locally first (recommended)

```bash
pip install -r requirements.txt

# create the local secrets file (do NOT commit it)
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# then open .streamlit/secrets.toml and set a real username + password

streamlit run app.py
```

Open the URL it prints, log in, and confirm the filters and charts work.

---

## 2) Deploy free on Streamlit Community Cloud

**a. Put the project on GitHub**

```bash
git init
git add .
git commit -m "ABC Q4 2025 dashboard"
git branch -M main
git remote add origin https://github.com/<your-username>/<your-repo>.git
git push -u origin main
```

> `.gitignore` already excludes `.streamlit/secrets.toml`, so your password is
> never pushed. Double-check with `git status` that `secrets.toml` is **not**
> listed. A private repo also works on the free tier.

**b. Deploy**

1. Go to **share.streamlit.io** and sign in with GitHub.
2. **Create app → Deploy a public app from GitHub.**
3. Select your repo, branch `main`, main file `app.py`.
4. Open **Advanced settings → Secrets** and paste:

   ```toml
   [credentials]
   username = "ta_reviewer"
   password = "your-strong-password"
   ```

5. Click **Deploy**. After it builds you get a public `…streamlit.app` URL,
   served over HTTPS, that asks for the username/password before showing
   anything.

**c. Hand-off**

Send your TA the app URL plus the username and password you set in step (b).

> To change the credentials later: **App → Settings → Secrets**, edit, save —
> the app reloads automatically. No code change needed.

---

## Security notes (how the login works)

* The username and password live only in **Streamlit secrets** (encrypted on
  Community Cloud, in a git-ignored file locally) — never in the code or repo.
* They are checked with `hmac.compare_digest`, a constant-time comparison that
  avoids timing side-channels (OWASP guidance).
* The raw password is removed from session state immediately after a successful
  login, and HTTPS/TLS is provided by Community Cloud.
* *Optional hardening:* store a bcrypt **hash** instead of the plaintext
  password and verify with `bcrypt`. For a single shared review credential the
  secrets-based check above is the officially recommended pattern and is
  sufficient here.

## Standards & conventions used

* **ISO 8601** dates (`YYYY-MM-DD`).
* **ISO 3166-1 alpha-3** country codes (used directly for the world map).
* **ISO 4217** currency labelling (all money shown as USD).
* **WCAG 2.1 AA**-minded design: colourblind-aware palette, high-contrast text.
* **GDPR data-minimisation**: only the columns needed for analysis are kept;
  the data is aggregated and contains no personal identifiers.
