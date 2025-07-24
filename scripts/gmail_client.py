import os.path
import base64
import re
from . import config

from googleapiclient.errors import HttpError
from .common_utils import get_gmail_service


def get_links_from_gmail():
    """읽지 않은 모든 이메일을 검색하고 본문에서 URL을 추출합니다."""
    service = get_gmail_service()
    if not service:
        return []

    # 읽지 않은 모든 메일을 대상으로 검색
    query = 'is:unread'
    try:
        results = service.users().messages().list(userId='me', q=query).execute()
    except HttpError as error:
        print(f"An error occurred while searching emails: {error}")
        return []

    messages = results.get('messages', [])

    if not messages:
        print("No new unread emails found.")
        return []

    links = []
    url_pattern = r'https?://[^\s<>"]+|www\.[^\s<>"]+'

    print(f"Found {len(messages)} new unread email(s). Processing...")
    for message_info in messages:
        try:
            msg = service.users().messages().get(userId='me', id=message_info['id'], format='full').execute()
            payload = msg.get('payload', {})
            
            body_data = None
            if 'data' in payload.get('body', {}):
                body_data = payload['body']['data']
            # multipart 이메일 처리 (e.g., text/plain and text/html)
            elif 'parts' in payload:
                for part in payload['parts']:
                    if part['mimeType'] == 'text/plain' and 'data' in part['body']:
                        body_data = part['body']['data']
                        break # text/plain을 우선적으로 사용
            
            if body_data:
                body = base64.urlsafe_b64decode(body_data).decode('utf-8', errors='ignore')
                found_urls = re.findall(url_pattern, body)
                if found_urls:
                    links.extend(found_urls)
            
            # 처리된 이메일은 '읽음'으로 표시 (UNREAD 라벨 제거)
            service.users().messages().modify(userId='me', id=message_info['id'], body={'removeLabelIds': ['UNREAD']}).execute()
        
        except HttpError as error:
            print(f"An error occurred while processing message ID {message_info['id']}: {error}")
            continue # 다음 메시지로 계속 진행
    
    return list(set(links)) # 중복 제거 후 반환

if __name__ == '__main__':
    """
    이 스크립트를 직접 실행할 때 테스트를 위해 사용됩니다.
    Gmail에서 링크를 가져와서 출력합니다.
    """
    print("--- Testing get_links_from_gmail() ---")
    links_found = get_links_from_gmail()
    if links_found:
        print("\nFound links:")
        for link in links_found:
            print(f"- {link}")