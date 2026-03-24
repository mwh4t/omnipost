<h1 align="center">OmniPost</h1>

<p align="center">
   <a href="https://github.com/mwh4t/omnipost/releases/download/v0.1/pitch.pptx">📥 download pitch presentation</a> |
   <a href="https://github.com/mwh4t/omnipost/wiki">📘 full documentation</a>
</p>

<p align="center">
   <strong>🌐 live demo:</strong><br>
   <a href="https://omni-post.dev">omni-post.dev</a><br>
   <sub>⚠️ vpn required from Russia</sub>
</p>

## tech stack

- **python**: backend logic, api integrations, automation
- **javascript**: frontend interactivity
- **css / html**: responsive and user-friendly web interface

## getting started

1. **clone the repository**

```bash
git clone https://github.com/mwh4t/omnipost.git
cd omnipost
```

2. **install dependencies**

using python & pip:
```bash
pip install -r requirements.txt
```

3. **configure your social network api keys**

copy data to `.env` and fill in your api credentials for each social network you intend to use

4. **run the application**
   
for local development:
```bash
honcho start -f Procfile.dev
```
this will run the django development server on http://localhost/
