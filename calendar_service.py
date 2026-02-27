import datetime

def get_todays_events(service):
    """取得今日全天的行事曆行程。"""
    now = datetime.datetime.utcnow().isoformat() + 'Z'  # 'Z' 表示 UTC 時間
    today_end = datetime.datetime.utcnow().replace(hour=23, minute=59, second=59).isoformat() + 'Z'
    
    events_result = service.events().list(
        calendarId='primary', 
        timeMin=now,
        timeMax=today_end,
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    events = events_result.get('items', [])
    
    processed_events = []
    for event in events:
        start = event['start'].get('dateTime', event['start'].get('date'))
        summary = event.get('summary', '無標題')
        location = event.get('location', '無地點')
        processed_events.append(f"[{start}] [{summary}] [{location}]")
    
    return processed_events
