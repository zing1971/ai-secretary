import datetime
import base64
from email.message import EmailMessage

def get_recent_emails(service):
    """取得過去 24 小時內的未讀信件摘要。"""
    time_24h_ago = datetime.datetime.utcnow() - datetime.timedelta(days=1)
    query = f"is:unread after:{int(time_24h_ago.timestamp())}"
    
    results = service.users().messages().list(userId='me', q=query).execute()
    messages = results.get('messages', [])
    
    email_list = []
    for msg in messages:
        msg_data = service.users().messages().get(userId='me', id=msg['id']).execute()
        headers = msg_data.get('payload', {}).get('headers', [])
        
        subject = "無主旨"
        sender = "未知寄件人"
        for header in headers:
            if header['name'] == 'Subject':
                subject = header['value']
            if header['name'] == 'From':
                sender = header['value']
        
        snippet = msg_data.get('snippet', '')
        email_list.append({
            'id': msg['id'],
            'threadId': msg_data.get('threadId'),
            'sender': sender,
            'subject': subject,
            'snippet': snippet,
            'summary_text': f"[{sender}] [{subject}] [摘要：{snippet}]"
        })
    
    return email_list

def create_gmail_draft(service, to_email, subject, body_text, thread_id=None):
    """建立 Gmail 回覆草稿。"""
    message = EmailMessage()
    message.set_content(body_text)
    message['To'] = to_email
    message['Subject'] = subject

    # 如果提供 thread_id，則關聯到特定討論串
    draft_body = {'message': {
        'raw': base64.urlsafe_b64encode(message.as_bytes()).decode()
    }}
    
    if thread_id:
        draft_body['message']['threadId'] = thread_id

    try:
        draft = service.users().drafts().create(userId='me', body=draft_body).execute()
        return draft
    except Exception as e:
        print(f"建立草稿失敗: {e}")
        return None
