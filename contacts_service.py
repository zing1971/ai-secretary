import base64
from config import logger

# 預設聯絡人標籤清單（對應 Google 聯絡人「標籤」功能）
CONTACT_LABELS = [
    "政府機關",
    "學術研究",
    "廠商代表",
    "關鍵夥伴",
    "媒體公關",
    "其他",
]

# 向後相容別名
CONTACT_GROUPS = CONTACT_LABELS


def build_label_cache(service) -> dict:
    """一次性取得所有使用者自訂標籤，返回 {label_name: resourceName} 快取字典。
    用於批次作業前的預熱，避免每筆聯絡人都重複呼叫 contactGroups().list()。
    """
    cache = {}
    try:
        result = service.contactGroups().list(pageSize=200).execute()
        for group in result.get('contactGroups', []):
            if group.get('groupType') == 'USER_CONTACT_GROUP':
                cache[group['name']] = group['resourceName']
        logger.info(f"📦 標籤快取建立完成，共 {len(cache)} 個標籤")
    except Exception as e:
        logger.error(f"建立標籤快取失敗: {e}")
    return cache


def _ensure_label(service, label_name: str, cache: dict = None) -> str | None:
    """確保指定標籤（Contact Group）存在，不存在則建立。
    Args:
        cache: 預先建立的標籤快取 dict（{name: resourceName}），有傳入則優先命中，
               避免每次都呼叫 contactGroups().list()。
    Returns:
        標籤的 resourceName，失敗時回傳 None
    """
    if cache is not None and label_name in cache:
        return cache[label_name]

    try:
        result = service.contactGroups().list(pageSize=200).execute()
        for group in result.get('contactGroups', []):
            if (group.get('groupType') == 'USER_CONTACT_GROUP'
                    and group.get('name') == label_name):
                rn = group['resourceName']
                if cache is not None:
                    cache[label_name] = rn
                return rn

        new_group = service.contactGroups().create(
            body={'contactGroup': {'name': label_name}}
        ).execute()
        resource_name = new_group.get('resourceName')
        logger.info(f"✅ 建立新標籤: {label_name} ({resource_name})")
        if cache is not None:
            cache[label_name] = resource_name
        return resource_name

    except Exception as e:
        logger.error(f"確認/建立標籤失敗 ({label_name}): {e}")
        return None


def _add_to_label(service, contact_resource_name: str, group_resource_name: str) -> bool:
    """將聯絡人加入標籤（Contact Group）。"""
    try:
        service.contactGroups().members().modify(
            resourceName=group_resource_name,
            body={'resourceNamesToAdd': [contact_resource_name]}
        ).execute()
        logger.info(f"🏷️ {contact_resource_name} → {group_resource_name}")
        return True
    except Exception as e:
        logger.error(f"加入標籤失敗: {e}")
        return False


def assign_label_to_contact(service, contact_resource_name: str, label_name: str,
                             cache: dict = None) -> bool:
    """確保標籤存在並將聯絡人加入該標籤。
    Returns:
        成功回傳 True，失敗回傳 False
    """
    group_rn = _ensure_label(service, label_name, cache)
    if not group_rn:
        return False
    return _add_to_label(service, contact_resource_name, group_rn)


def batch_assign_label(service, contact_resource_names: list, label_name: str,
                       cache: dict = None) -> bool:
    """將多筆聯絡人批次加入同一標籤，一次 API 呼叫。
    相較於逐筆呼叫，N 筆同標籤聯絡人從 N 次 modify 降為 1 次。
    Returns:
        成功回傳 True，失敗回傳 False
    """
    if not contact_resource_names:
        return True
    group_rn = _ensure_label(service, label_name, cache)
    if not group_rn:
        return False
    try:
        service.contactGroups().members().modify(
            resourceName=group_rn,
            body={'resourceNamesToAdd': contact_resource_names}
        ).execute()
        logger.info(f"🏷️ 批次寫入標籤 [{label_name}]：{len(contact_resource_names)} 筆")
        return True
    except Exception as e:
        logger.error(f"批次加入標籤失敗 ({label_name}): {e}")
        return False


def create_contact(service, name: str, company: str, job_title: str,
                   email: str, phone: str, photo_bytes: bytes = None,
                   label: str = None):
    """建立新的 Google 聯絡人，並可選擇附加名片照片與分類標籤。
    標籤寫入 Google 聯絡人「標籤」（Contact Group），在 UI 可側邊欄篩選。
    Args:
        service: Google People API service instance
        name, company, job_title, email, phone: 聯絡人基本資訊
        photo_bytes: 名片影像原始位元組 (JPEG)
        label: 分類標籤名稱（須在 CONTACT_LABELS 清單內）
    Returns:
        建立成功的聯絡人物件，或 None
    """
    try:
        contact_body = {}

        if name:
            contact_body['names'] = [{'givenName': name}]

        if company or job_title:
            org = {}
            if company: org['name'] = company
            if job_title: org['title'] = job_title
            contact_body['organizations'] = [org]

        if email:
            contact_body['emailAddresses'] = [{'value': email, 'type': 'work'}]

        if phone:
            contact_body['phoneNumbers'] = [{'value': phone, 'type': 'work'}]

        # 步驟 1：建立聯絡人
        created_contact = service.people().createContact(body=contact_body).execute()
        resource_name = created_contact.get('resourceName')
        logger.info(f"✅ 成功建立聯絡人: {name} ({resource_name})")

        # 步驟 2：寫入標籤（Contact Group）
        if label and resource_name:
            ok = assign_label_to_contact(service, resource_name, label)
            if ok:
                logger.info(f"🏷️ 已貼標籤 [{label}] 至聯絡人: {name}")
            else:
                logger.warning(f"⚠️ 聯絡人已建立但標籤寫入失敗: {name}")

        # 步驟 3：上傳名片照片
        if photo_bytes and resource_name:
            try:
                photo_b64 = base64.b64encode(photo_bytes).decode('utf-8')
                service.people().updateContactPhoto(
                    resourceName=resource_name,
                    body={'photoBytes': photo_b64}
                ).execute()
                logger.info(f"📸 成功上傳名片照片至聯絡人: {name}")
            except Exception as photo_err:
                logger.warning(f"⚠️ 聯絡人已建立但照片上傳失敗: {photo_err}")

        return created_contact

    except Exception as e:
        logger.error(f"建立聯絡人失敗: {e}", exc_info=True)
        return None


def get_unlabeled_contacts(service) -> list[dict]:
    """取得所有未貼任何使用者自訂標籤的聯絡人。
    判斷依據：memberships 中沒有任何 USER_CONTACT_GROUP 類型的群組。
    Returns:
        list of dict，每筆含 resourceName, name, company, job_title
    """
    unlabeled = []
    page_token = None
    try:
        while True:
            kwargs = {
                'resourceName': 'people/me',
                'pageSize': 1000,
                'personFields': 'names,organizations,memberships,emailAddresses',
            }
            if page_token:
                kwargs['pageToken'] = page_token

            result = service.people().connections().list(**kwargs).execute()
            for person in result.get('connections', []):
                memberships = person.get('memberships', [])
                # 系統群組 ID 為英文（myContacts/starred/all…），使用者標籤 ID 為純數字
                has_user_label = any(
                    m.get('contactGroupMembership', {})
                     .get('contactGroupResourceName', '')
                     .split('/')[-1].isdigit()
                    for m in memberships
                )

                if has_user_label:
                    continue

                names = person.get('names', [{}])
                orgs = person.get('organizations', [{}])
                emails = person.get('emailAddresses', [{}])
                unlabeled.append({
                    'resourceName': person.get('resourceName'),
                    'name': names[0].get('displayName', '') if names else '',
                    'company': orgs[0].get('name', '') if orgs else '',
                    'job_title': orgs[0].get('title', '') if orgs else '',
                    'email': emails[0].get('value', '') if emails else '',
                })

            page_token = result.get('nextPageToken')
            if not page_token:
                break

        logger.info(f"📋 找到 {len(unlabeled)} 筆未分類聯絡人")
        return unlabeled

    except Exception as e:
        logger.error(f"取得聯絡人清單失敗: {e}", exc_info=True)
        return []


def update_contact_label(service, resource_name: str, _etag: str, label: str,
                         cache: dict = None) -> bool:
    """將聯絡人加入指定標籤（Contact Group）。_etag 參數保留供向後相容，不使用。"""
    return assign_label_to_contact(service, resource_name, label, cache)


def search_contacts(service, query: str, max_results: int = 10) -> list[dict]:
    """
    根據關鍵字搜尋 Google Contacts 中的聯絡人（姓名、Email、公司名稱等）。

    Args:
        service: Google People API service instance
        query: 搜尋關鍵字
        max_results: 最多回傳幾筆結果（預設 10）

    Returns:
        list of dict，每筆含 resourceName, name, email, phone, company, job_title
    """
    try:
        result = service.people().searchContacts(
            query=query,
            pageSize=max_results,
            readMask='names,emailAddresses,phoneNumbers,organizations',
        ).execute()

        contacts = []
        for item in result.get('results', []):
            person = item.get('person', {})
            names = person.get('names', [{}])
            emails = person.get('emailAddresses', [{}])
            phones = person.get('phoneNumbers', [{}])
            orgs = person.get('organizations', [{}])
            contacts.append({
                'resourceName': person.get('resourceName', ''),
                'name': names[0].get('displayName', '') if names else '',
                'email': emails[0].get('value', '') if emails else '',
                'phone': phones[0].get('value', '') if phones else '',
                'company': orgs[0].get('name', '') if orgs else '',
                'job_title': orgs[0].get('title', '') if orgs else '',
            })
        logger.info(f"🔍 搜尋聯絡人「{query}」，找到 {len(contacts)} 筆")
        return contacts

    except Exception as e:
        logger.error(f"搜尋聯絡人失敗: {e}", exc_info=True)
        return []
