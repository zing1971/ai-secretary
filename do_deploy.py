import os
import subprocess

with open('.env') as f:
    lines = f.readlines()

env_file = 'env_vars.yaml'
with open(env_file, 'w', encoding='utf-8') as f:
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'): continue
        if line.startswith('DEBUG=') or line.startswith('PORT='): continue
        k, v = line.split('=', 1)
        f.write(f"{k}: '{v}'\n")

    if os.path.exists('token.json'):
        with open('token.json', encoding='utf-8') as tf:
            val = tf.read().replace('\n', '').replace('\r', '')
            f.write(f"GOOGLE_TOKEN_JSON: '{val}'\n")

    if os.path.exists('credentials.json'):
        with open('credentials.json', encoding='utf-8') as cf:
            val = cf.read().replace('\n', '').replace('\r', '')
            f.write(f"GOOGLE_CREDENTIALS_JSON: '{val}'\n")

project = "gen-lang-client-0741928971"
region = "asia-east1"
service = "ai-secretary"
image = f"gcr.io/{project}/{service}"

os.environ["PATH"] = r"C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\bin;" + os.environ.get("PATH", "")

print("Step 2: Build Docker image...")
subprocess.run(f"gcloud builds submit --tag {image} --project {project}", shell=True, check=True)

print("Step 3: Deploy to Cloud Run...")
subprocess.run(f"gcloud run deploy {service} --image {image} --region {region} --allow-unauthenticated --env-vars-file {env_file} --project {project}", shell=True, check=True)

if os.path.exists(env_file):
    os.remove(env_file)

print("Deployment Successful!")
