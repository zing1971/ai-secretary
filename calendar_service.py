import datetime
import logging
import pytz

logger = logging.getLogger(__name__)


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
    except (ValueError, AttributeError) as e:
        logger.debug(f"format_event_time 解析失敗（{date_str!r}）：{e}")
        return date_str

def get_events(service, time_min: str, time_max: str, query: str = None):
    """取得指定時間範圍內的行事曆行程 (時間需為 RFC3339 格式)，可選傳入 query 作為字串搜尋"""
    kwargs = {
        'calendarId': 'primary', 
        'timeMin': time_min,
        'timeMax': time_max,
        'singleEvents': True,
        'orderBy': 'startTime'
    }
    if query:
        kwargs['q'] = query
        
    events_result = service.events().list(**kwargs).execute()
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
        html_link = event.get('htmlLink', '')
        
        # 組合資訊
        loc_str = f" | 地點: {location}" if location and location != '無地點' else ""
        desc_str = f" | 備註: {description[:50]}..." if description else ""
        link_str = f"\n  🔗 查看行程：{html_link}" if html_link else ""
        
        # 若是全天行程
        if ' ' in start_fmt:
            time_display = f"{start_fmt} ~ {end_fmt.split(' ')[1]}"  # 結束只顯示時間
        else:
            time_display = f"{start_fmt} (全天)"
            
        processed_events.append(f"• [{time_display}] {summary}{loc_str}{desc_str}{link_str}")
        
    return processed_events

def get_todays_events(service):
    """取得今日全天的行事曆行程。供被動觸發使用。"""
    # 使用 timezone-aware datetime（datetime.utcnow() 已在 Python 3.12 棄用）
    utc = datetime.timezone.utc
    now = datetime.datetime.now(utc).isoformat()
    today_end = datetime.datetime.now(utc).replace(
        hour=23, minute=59, second=59, microsecond=0
    ).isoformat()
    return get_events(service, now, today_end)


def create_event(
    service,
    title: str,
    start_time: str,
    end_time: str,
    description: str = None,
    location: str = None,
) -> dict | None:
    """
    建立一個 Google Calendar 行程。

    Args:
        service: Google Calendar API service instance
        title: 行程標題
        start_time: 開始時間，格式 "YYYY-MM-DD HH:MM"（台北時間）或 "YYYY-MM-DD"（全天）
        end_time: 結束時間，格式同上
        description: 備註說明（可選）
        location: 地點（可選）

    Returns:
        建立成功的行程物件 dict，或拋出 RuntimeError（失敗時）
    """
    tz = pytz.timezone('Asia/Taipei')

    # 全天行程判斷：純日期格式 YYYY-MM-DD（長度 10，無空格無 T）
    is_all_day = len(start_time) == 10 and ' ' not in start_time and 'T' not in start_time

    if is_all_day:
        event_body: dict = {
            'summary': title,
            'start': {'date': start_time},
            'end': {'date': end_time},
        }
    else:
        fmt = "%Y-%m-%d %H:%M"
        try:
            start_dt = tz.localize(datetime.datetime.strptime(start_time, fmt))
            end_dt = tz.localize(datetime.datetime.strptime(end_time, fmt))
        except ValueError as exc:
            raise ValueError(
                f"時間格式不正確：{exc}。"
                f"請使用 'YYYY-MM-DD HH:MM' 或 'YYYY-MM-DD' 格式。"
            ) from exc

        event_body = {
            'summary': title,
            'start': {'dateTime': start_dt.isoformat(), 'timeZone': 'Asia/Taipei'},
            'end': {'dateTime': end_dt.isoformat(), 'timeZone': 'Asia/Taipei'},
        }

    if description:
        event_body['description'] = description
    if location:
        event_body['location'] = location

    try:
        return service.events().insert(calendarId='primary', body=event_body).execute()
    except Exception as exc:
        raise RuntimeError(f"Google Calendar API 建立行程失敗：{exc}") from exc


def get_events_range(service, from_date: str, to_date: str) -> list[str]:
    """
    取得指定日期範圍內的行程。

    Args:
        from_date: 開始日期，格式 "YYYY-MM-DD"
        to_date:   結束日期，格式 "YYYY-MM-DD"（含當天到 23:59:59）
    """
    tz = pytz.timezone('Asia/Taipei')
    fmt = "%Y-%m-%d"
    try:
        start_dt = tz.localize(datetime.datetime.strptime(from_date, fmt))
        end_dt = tz.localize(datetime.datetime.strptime(to_date, fmt)).replace(
            hour=23, minute=59, second=59
        )
    except ValueError as exc:
        raise ValueError(f"日期格式不正確，請用 YYYY-MM-DD：{exc}") from exc
    return get_events(service, start_dt.isoformat(), end_dt.isoformat())


def update_event(
    service,
    event_id: str,
    title: str = None,
    start_time: str = None,
    end_time: str = None,
    description: str = None,
    location: str = None,
) -> dict:
    """
    更新已存在的 Google Calendar 行程（只修改提供的欄位）。
    """
    try:
        existing = service.events().get(calendarId='primary', eventId=event_id).execute()
    except Exception as exc:
        raise RuntimeError(f"找不到行程 (event_id={event_id})：{exc}") from exc

    patch: dict = {}
    if title:
        patch['summary'] = title
    if description is not None:
        patch['description'] = description
    if location is not None:
        patch['location'] = location

    tz = pytz.timezone('Asia/Taipei')
    fmt = "%Y-%m-%d %H:%M"
    if start_time:
        is_all_day = len(start_time) == 10 and ' ' not in start_time
        if is_all_day:
            patch['start'] = {'date': start_time}
        else:
            dt = tz.localize(datetime.datetime.strptime(start_time, fmt))
            patch['start'] = {'dateTime': dt.isoformat(), 'timeZone': 'Asia/Taipei'}
    if end_time:
        is_all_day = len(end_time) == 10 and ' ' not in end_time
        if is_all_day:
            patch['end'] = {'date': end_time}
        else:
            dt = tz.localize(datetime.datetime.strptime(end_time, fmt))
            patch['end'] = {'dateTime': dt.isoformat(), 'timeZone': 'Asia/Taipei'}

    if not patch:
        return existing

    try:
        return service.events().patch(
            calendarId='primary', eventId=event_id, body=patch
        ).execute()
    except Exception as exc:
        raise RuntimeError(f"更新行程失敗 (event_id={event_id})：{exc}") from exc


def delete_event(service, event_id: str) -> None:
    """刪除指定的 Google Calendar 行程。"""
    try:
        service.events().delete(calendarId='primary', eventId=event_id).execute()
    except Exception as exc:
        raise RuntimeError(f"刪除行程失敗 (event_id={event_id})：{exc}") from exc
