import datetime
import base64
from email.message import EmailMessage

def extract_email_body(payload):
    """從 Gmail payload 中提取純文字內容"""
    body = ""
    if 'parts' in payload:
        for part in payload['parts']:
            if part['mimeType'] == 'text/plain' and 'data' in part['body']:
                body += base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
            elif 'parts' in part:
                body += extract_email_body(part) # 處理 multipart/alternative 等嵌套
    elif payload.get('mimeType') == 'text/plain' and 'data' in payload.get('body', {}):
        body = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8')
    
    # 限制長度避免 tokens 過多
    return body[:2000] if body else ""

def get_recent_emails(service, query=None, max_results=15):
    """依照給定 query 取得信件。若無指定，預設取得過去 24 小時內的未讀信件。"""
    if query is None or query.strip() == "":
        time_3d_ago = datetime.datetime.utcnow() - datetime.timedelta(days=3)
        query = f"is:unread after:{int(time_3d_ago.timestamp())}"
    
    results = service.users().messages().list(userId='me', q=query, maxResults=max_results).execute()
    messages = results.get('messages', [])
    
    email_list = []
    for msg in messages:
        try:
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
            full_body = extract_email_body(payload)
            
            # 若無純文字 body，使用 snippet 墊底
            content_to_summarize = full_body if full_body.strip() else snippet
            
            email_list.append({
                'id': msg['id'],
                'url': f"https://mail.google.com/mail/u/0/#inbox/{msg['id']}",
                'threadId': msg_data.get('threadId'),
                'sender': sender,
                'subject': subject,
                'snippet': snippet,
                'body': content_to_summarize,
                'summary_text': f"[{sender}] [{subject}]" # 交給 LLM 分析詳細內容
            })
        except Exception as e:
            print(f"讀取信件 {msg['id']} 失敗：{e}")
            continue
            
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
