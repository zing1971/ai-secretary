from config import logger

def create_contact(service, name: str, company: str, job_title: str, email: str, phone: str):
    """建立新的 Google 聯絡人
    Args:
        service: Google People API service instance
        name: 姓名
        company: 公司名稱
        job_title: 職稱
        email: 電子郵件
        phone: 電話號碼
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
            contact_body['phoneNumbers'] = [{'value': phone, 'type': '工作'}]
            
        created_contact = service.people().createContact(body=contact_body).execute()
        logger.info(f"成功建立聯絡人: {name} (Resource Name: {created_contact.get('resourceName')})")
        return created_contact

    except Exception as e:
        logger.error(f"建立聯絡人失敗: {e}", exc_info=True)
        return None
