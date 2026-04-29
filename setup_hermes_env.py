"""建立 ~/.hermes/.env，從 ai-secretary .env 提取 Telegram 設定。"""
env = {}
with open('/home/zing/ai-secretary/.env') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, _, v = line.partition('=')
            env[k.strip()] = v.strip().strip('"').strip("'")

bot_token = env.get('TELEGRAM_BOT_TOKEN', '')
chat_id = env.get('TELEGRAM_CHAT_ID', '')

content = f'TELEGRAM_BOT_TOKEN={bot_token}\nTELEGRAM_ALLOWED_USERS={chat_id}\n'
with open('/home/zing/.hermes/.env', 'w') as f:
    f.write(content)

print('created ~/.hermes/.env')
print(f'TELEGRAM_BOT_TOKEN set: {bool(bot_token)}')
print(f'TELEGRAM_ALLOWED_USERS: {chat_id}')
