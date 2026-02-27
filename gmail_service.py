import datetime

def get_recent_emails(service):
    """取得過去 24 小時內的未讀信件摘要。"""
    # 計算 24 小時前的時間
    time_24h_ago = datetime.datetime.utcnow() - datetime.timedelta(days=1)
    query = f"is:unread after:{int(time_24h_ago.timestamp())}"
    
    results = service.users().messages().list(userId='me', q=query).execute()
    messages = results.get('messages', [])
    
    email_summaries = []
    for msg in messages:
        msg_data = service.users().messages().get(userId='me', id=msg['id']).execute()
        payload = msg_data.get('payload', {})
        headers = payload.get('headers', [])
        
        subject = "無主旨"
        sender = "未知寄件人"
        for header in headers:
            if header['name'] == 'Subject':
                subject = header['value']
            if header['name'] == 'From':
                sender = header['value']
        
        snippet = msg_data.get('snippet', '')
        email_summaries.append(f"[{sender}] [{subject}] [摘要：{snippet}]")
    
    return email_summaries
