import base64
from config import logger

# 預設聯絡人群組清單（AI 自動分類時可選擇的群組）
CONTACT_GROUPS = [
    "政府機關",
    "學術研究",
    "廠商代表",
    "關鍵夥伴",
    "媒體公關",
    "其他",
]

def create_contact(service, name: str, company: str, job_title: str, 
                   email: str, phone: str, photo_bytes: bytes = None):
    """建立新的 Google 聯絡人，並可選擇附加名片照片
    Args:
        service: Google People API service instance
        name: 姓名
        company: 公司名稱
        job_title: 職稱
        email: 電子郵件
        phone: 電話號碼
        photo_bytes: 名片影像的原始位元組 (JPEG)
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


def ensure_contact_group(service, group_name: str) -> str | None:
    """確保指定名稱的聯絡人群組存在，若不存在則自動建立。
    Args:
        service: Google People API service instance
        group_name: 群組名稱（如「客戶」、「廠商代表」）
    Returns:
        群組的 resourceName（字串），失敗時回傳 None
    """
    try:
        # 列出所有現有使用者自建群組（userContactGroups）
        result = service.contactGroups().list(
            pageSize=100
        ).execute()
        for group in result.get('contactGroups', []):
            if group.get('groupType') == 'USER_CONTACT_GROUP' and group.get('name') == group_name:
                logger.info(f"🏷️ 找到既有群組: {group_name} ({group['resourceName']})")
                return group['resourceName']

        # 群組不存在 → 建立新群組
        new_group = service.contactGroups().create(
            body={'contactGroup': {'name': group_name}}
        ).execute()
        resource_name = new_group.get('resourceName')
        logger.info(f"✅ 成功建立新群組: {group_name} ({resource_name})")
        return resource_name

    except Exception as e:
        logger.error(f"確認/建立聯絡人群組失敗 ({group_name}): {e}")
        return None


def add_contact_to_group(service, contact_resource_name: str, group_resource_name: str) -> bool:
    """將聯絡人加入指定群組。
    Args:
        service: Google People API service instance
        contact_resource_name: 聯絡人的 resourceName (如 people/c123456)
        group_resource_name: 群組的 resourceName (如 contactGroups/123456)
    Returns:
        成功回傳 True，失敗回傳 False
    """
    try:
        service.contactGroups().members().modify(
            resourceName=group_resource_name,
            body={'resourceNamesToAdd': [contact_resource_name]}
        ).execute()
        logger.info(f"✅ 已將 {contact_resource_name} 加入群組 {group_resource_name}")
        return True
    except Exception as e:
        logger.error(f"加入聯絡人群組失敗: {e}")
        return False
