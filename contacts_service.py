import base64
from config import logger

# 預設聯絡人標籤清單（AI 自動分類時可選擇的標籤）
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

def create_contact(service, name: str, company: str, job_title: str,
                   email: str, phone: str, photo_bytes: bytes = None,
                   label: str = None):
    """建立新的 Google 聯絡人，並可選擇附加名片照片與分類標籤
    Args:
        service: Google People API service instance
        name: 姓名
        company: 公司名稱
        job_title: 職稱
        email: 電子郵件
        phone: 電話號碼
        photo_bytes: 名片影像的原始位元組 (JPEG)
        label: 分類標籤（直接寫入聯絡人 userDefined 欄位）
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

        if label:
            contact_body['userDefined'] = [{'key': '分類', 'value': label}]

        # 步驟 1：建立聯絡人
        created_contact = service.people().createContact(body=contact_body).execute()
        resource_name = created_contact.get('resourceName')
        logger.info(f"✅ 成功建立聯絡人: {name} ({resource_name}) 標籤: {label or '無'}")

        # 步驟 2：如果有名片影像，上傳為聯絡人照片
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
    """取得所有沒有「分類」標籤的聯絡人。
    Returns:
        list of dict，每筆包含 resourceName, etag, name, company, job_title
    """
    unlabeled = []
    page_token = None
    try:
        while True:
            kwargs = {
                'resourceName': 'people/me',
                'pageSize': 1000,
                'personFields': 'names,organizations,userDefined',
            }
            if page_token:
                kwargs['pageToken'] = page_token

            result = service.people().connections().list(**kwargs).execute()
            for person in result.get('connections', []):
                # 檢查是否已有「分類」標籤
                user_defined = person.get('userDefined', [])
                has_label = any(ud.get('key') == '分類' for ud in user_defined)
                if has_label:
                    continue

                names = person.get('names', [{}])
                orgs = person.get('organizations', [{}])
                unlabeled.append({
                    'resourceName': person.get('resourceName'),
                    'etag': person.get('etag', ''),
                    'name': names[0].get('displayName', '') if names else '',
                    'company': orgs[0].get('name', '') if orgs else '',
                    'job_title': orgs[0].get('title', '') if orgs else '',
                })

            page_token = result.get('nextPageToken')
            if not page_token:
                break

        logger.info(f"📋 找到 {len(unlabeled)} 筆未分類聯絡人")
        return unlabeled

    except Exception as e:
        logger.error(f"取得聯絡人清單失敗: {e}", exc_info=True)
        return []


def update_contact_label(service, resource_name: str, etag: str, label: str) -> bool:
    """更新聯絡人的分類標籤（userDefined 欄位）。
    Args:
        service: Google People API service instance
        resource_name: 聯絡人 resourceName (e.g. people/c123456)
        etag: 聯絡人 etag（updateContact 必須提供）
        label: 要寫入的標籤名稱
    Returns:
        成功回傳 True，失敗回傳 False
    """
    try:
        service.people().updateContact(
            resourceName=resource_name,
            updatePersonFields='userDefined',
            body={
                'resourceName': resource_name,
                'etag': etag,
                'userDefined': [{'key': '分類', 'value': label}],
            }
        ).execute()
        logger.info(f"🏷️ 已更新標籤 {resource_name} → {label}")
        return True
    except Exception as e:
        logger.error(f"更新標籤失敗 ({resource_name}): {e}")
        return False
