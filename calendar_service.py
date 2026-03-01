import datetime
import pytz

def format_event_time(date_str: str) -> str:
    """將 ISO 時間字串轉換為閱讀友善的台北時間"""
    try:
        # 處理純日期 (全天行程)
        if 'T' not in date_str:
            return date_str
            
        dt = datetime.datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        tz = pytz.timezone('Asia/Taipei')
        dt_taipei = dt.astimezone(tz)
        return dt_taipei.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return date_str

def get_events(service, time_min: str, time_max: str):
    """取得指定時間範圍內的行事曆行程 (時間需為 RFC3339 格式)"""
    events_result = service.events().list(
        calendarId='primary', 
        timeMin=time_min,
        timeMax=time_max,
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    events = events_result.get('items', [])
    
    processed_events = []
    for event in events:
        start_raw = event['start'].get('dateTime', event['start'].get('date'))
        end_raw = event['end'].get('dateTime', event['end'].get('date'))
        
        start_fmt = format_event_time(start_raw)
        end_fmt = format_event_time(end_raw)
        
        summary = event.get('summary', '無標題')
        location = event.get('location', '')
        description = event.get('description', '')
        
        # 組合資訊
        loc_str = f" | 地點: {location}" if location and location != '無地點' else ""
        desc_str = f" | 備註: {description[:50]}..." if description else ""
        
        # 若是全天行程
        if ' ' in start_fmt:
            time_display = f"{start_fmt} ~ {end_fmt.split(' ')[1]}"  # 結束只顯示時間
        else:
            time_display = f"{start_fmt} (全天)"
            
        processed_events.append(f"• [{time_display}] {summary}{loc_str}{desc_str}")
        
    return processed_events

def get_todays_events(service):
    """取得今日全天的行事曆行程。供被動觸發使用。"""
    now = datetime.datetime.utcnow().isoformat() + 'Z'  # 'Z' 表示 UTC 時間
    today_end = datetime.datetime.utcnow().replace(hour=23, minute=59, second=59).isoformat() + 'Z'
    return get_events(service, now, today_end)
