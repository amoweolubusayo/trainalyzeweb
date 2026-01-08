# Trainalyze Web

A simple web app to find unclaimed train refunds from your emails.

## What You'll See

1. **Connect** - Sign in with your email account
2. **Scan** - We look through your transport emails (takes ~30 seconds)
3. **Results** - See potential refunds with direct claim links

---

## Deploy to Vercel

### Step 1: Push to GitHub

```bash
cd ~/Desktop/trainalyzeweb
git init
git add .
git commit -m "Initial commit"
gh repo create trainalyzeweb --public --push
```

### Step 2: Create Google OAuth Credentials for Production

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select your **trainalyze** project
3. Go to **APIs & Services** → **Credentials**
4. Click **Create Credentials** → **OAuth client ID**
5. Select **Web application**
6. Add authorized redirect URI: `https://your-app-name.vercel.app/oauth/callback`
   (You'll update this after deploying)
7. Save the **Client ID** and **Client Secret**

### Step 3: Deploy on Vercel

1. Go to [vercel.com](https://vercel.com) and sign in with GitHub
2. Click **Add New** → **Project**
3. Import your `trainalyzeweb` repository
4. Add Environment Variables:
   - `GOOGLE_CLIENT_ID` = your client ID from step 2
   - `GOOGLE_CLIENT_SECRET` = your client secret from step 2
   - `FLASK_SECRET_KEY` = a random string (run `openssl rand -hex 32` to generate)
5. Click **Deploy**

### Step 4: Update Google OAuth Redirect URI

1. Copy your Vercel URL (e.g., `https://trainalyzeweb.vercel.app`)
2. Go back to Google Cloud Console → Credentials
3. Edit your OAuth client
4. Add the redirect URI: `https://your-vercel-url.vercel.app/oauth/callback`
5. Save

---

## Run Locally

```bash
cd ~/Desktop/trainalyzeweb
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Then open http://localhost:5000

---

## Privacy

- Only reads emails — cannot send, edit, or delete
- Data is processed in memory, not stored
- Remove access anytime from [Google Account Settings](https://myaccount.google.com/permissions)

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `GOOGLE_CLIENT_ID` | OAuth client ID from Google Cloud Console |
| `GOOGLE_CLIENT_SECRET` | OAuth client secret |
| `FLASK_SECRET_KEY` | Random string for session encryption |

---

## Project Structure

```
trainalyzeweb/
├── api/
│   └── index.py         # Vercel serverless function
├── templates/
│   ├── index.html       # Home page
│   ├── scanning.html    # Loading animation
│   └── results.html     # Results page
├── app.py               # Local Flask app
├── vercel.json          # Vercel configuration
├── requirements.txt     # Python dependencies
└── README.md
```
