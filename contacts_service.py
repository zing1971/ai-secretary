import base64
from config import logger

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
