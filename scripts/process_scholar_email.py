import email
import logging
import os
import re
import base64
import threading
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

from bs4 import BeautifulSoup

from .common_utils import (
    clean_google_url,
    fetch_article_body,
    get_gmail_service,
    get_existing_english_titles_from_dir,
    safe_filename,
    translate_text,
    summarize_and_translate_body,
    initialize_gemini,
)

# --- Constants ---
SEEN_PAPERS_FILE = "seen_scholar_messages.json"

PAPERS_OUTPUT_DIR = os.path.join("docs", "keywords")
MIN_BODY_LENGTH = 300


# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)


def get_html_payload_from_message(msg):
    """Gmail API 메시지 객체에서 HTML payload를 재귀적으로 찾습니다."""
    if "parts" in msg["payload"]:
        for part in msg["payload"]["parts"]:
            if part["mimeType"] == "text/html":
                return part["body"].get("data")
            # 재귀 호출
            data = get_html_payload_from_message({"payload": part})
            if data:
                return data
    elif msg["payload"]["mimeType"] == "text/html":
        return msg["payload"]["body"].get("data")
    return None


def parse_scholar_email(msg):
    """Gmail 메시지를 파싱하여 키워드와 논문 목록을 추출합니다."""
    headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
    subject = headers.get("Subject", "")

    keyword_match = re.match(r'^(.*?)\s*-\s*(?:new results|새로운 결과)', subject, re.IGNORECASE)
    
    if not keyword_match:
        logging.info(f"유효한 알림 메일이 아님 (제목: '{subject}'). 건너뜁니다.")
        return None, [] # 유효한 알림이 아니므로 None을 반환하여 버리도록 신호

    # 매치된 경우, 첫 번째 그룹에서 키워드를 추출합니다.
    keyword = keyword_match.group(1).strip()
    logging.info(f"🔑 추출된 키워드: {keyword}")

    body_data = get_html_payload_from_message(msg)
    if not body_data:
        logging.error("이메일에서 HTML 콘텐츠를 찾을 수 없습니다.")
        return keyword, []

    html_content = base64.urlsafe_b64decode(body_data).decode("utf-8")
    soup = BeautifulSoup(html_content, "html.parser")
    articles = []

    # 실제 이메일 HTML 구조에 맞게, class="gse_alrt_title"를 가진 <a> 태그를 직접 찾습니다.
    for link_tag in soup.find_all("a", class_="gse_alrt_title"):
        title_en = link_tag.get_text(strip=True)
        url = link_tag.get("href", "")

        # 스니펫(요약)을 찾기 위해, 먼저 <a> 태그의 부모인 <h3> 태그를 찾습니다.
        h3_tag = link_tag.find_parent("h3")
        snippet = ""
        if h3_tag:
            # <h3> 태그의 바로 다음 형제인 <div class="gse_alrt_sni">를 찾습니다.
            snippet_tag = h3_tag.find_next_sibling("div", class_="gse_alrt_sni")
            if snippet_tag:
                snippet = snippet_tag.get_text(strip=True)
        
        if title_en and url:
            articles.append({"title_en": title_en, "url": url, "snippet": snippet})

    logging.info(f"📄 이메일에서 {len(articles)}개의 논문을 찾았습니다.")
    return keyword, articles

def save_paper_markdown(keyword, title_ko, title_en, summary_ko, url):
    """논문 요약을 마크다운 파일로 저장합니다."""
    try:
        safe_title = safe_filename(title_ko)
        folder = os.path.join(PAPERS_OUTPUT_DIR, keyword)
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, f"{safe_title}.md")

        with open(path, "w", encoding="utf-8") as f:
            f.write(f"# {title_ko}\n\n")
            f.write(f"**원제목:** {title_en}\n\n")
            f.write(f"**요약:** {summary_ko}\n\n")
            f.write(f"[원문 링크]({url})\n")
        logging.info(f"✅ 저장 완료: {path}")
        return True

    except Exception as e:
        logging.error(f"파일 저장 중 오류 발생 ({title_en}): {e}")
        return False

def load_seen_ids():
    """처리된 이메일 ID 목록을 불러옵니다."""
    if os.path.exists(SEEN_PAPERS_FILE):
        with open(SEEN_PAPERS_FILE, "r") as f:
            return set(json.load(f))
    return set()


def save_seen_ids(ids):
    """처리된 이메일 ID 목록을 저장합니다."""
    with open(SEEN_PAPERS_FILE, "w") as f:
        json.dump(list(ids), f)


def process_paper_entry(article, keyword, existing_titles, lock):
    """개별 논문 항목을 처리, 번역, 저장합니다."""
    try:
        title_en, link_url, snippet = article["title_en"], article["url"], article["snippet"]

        with lock:
            if title_en in existing_titles:
                logging.info(f"🚫 중복 논문: {title_en}")
                return False
            existing_titles.add(title_en)

        logging.info(f"--- ⚙️ 처리 시작: {title_en} ---")

        # 어떤 URL을 처리하기 시작했는지 즉시 로깅하여, 멈춤 현상의 원인을 추적할 수 있도록 합니다.
        logging.info(f"  -> URL: {link_url}")

        link = clean_google_url(link_url)

        # 1. 본문 추출을 먼저 시도합니다.
        body = fetch_article_body(link)

        # 2. 본문 추출에 실패했거나 내용이 너무 짧으면, 이메일의 스니펫을 대체재로 사용합니다.
        if not body or len(body.strip()) < MIN_BODY_LENGTH:
            logging.info(f"  - ℹ️ 정보: 본문 추출 실패 또는 내용 부족. 이메일 스니펫을 사용합니다.")
            body = snippet

        # 3. 본문과 스니펫이 모두 비어있으면 건너뜁니다.
        if not body or not body.strip():
            logging.warning(f"본문/스니펫이 모두 비어있어 건너뜁니다: {title_en}")
            return False

        logging.info(f"  -> 제목 번역 중...")
        title_ko = translate_text(title_en)
        logging.info(f"  -> 제목 번역 완료.")

        logging.info(f"  -> 본문 요약 및 번역 중...")
        summary_ko = summarize_and_translate_body(body)
        logging.info(f"  -> 본문 요약 및 번역 완료.")

        if not title_ko or not summary_ko:
            logging.error(f"번역 실패: {title_en}")
            return False
        
        logging.info(f"  -> 마크다운 저장 중...")
        if save_paper_markdown(keyword, title_ko, title_en, summary_ko, link):
            return True # 제목은 이미 목록에 추가되었습니다.
        return False
    except Exception as e:
        logging.error(f"논문 처리 중 오류 발생 ({article.get('title_en', 'N/A')}): {e}")
        return False

def main():
    try:
        initialize_gemini()
    except (ValueError, RuntimeError) as e:
        logging.error(f"스크립트 실행 중단: {e}")
        # CI/CD 환경에서 실패를 명확히 알리기 위해 0이 아닌 코드로 종료
        exit(1)

    service = get_gmail_service()
    if not service:
        # get_gmail_service 내부에서 이미 CRITICAL 에러를 로깅했으므로, 여기서는 예외를 발생시켜 프로세스를 중단시킵니다.
        raise RuntimeError("Gmail 서비스 객체를 가져오지 못해 스크립트를 중단합니다.")

    query = "from:scholaralerts-noreply@google.com is:unread"
    logging.info(f"🔍 Gmail에서 다음 쿼리로 새 논문 알림을 검색합니다: '{query}'")
    results = service.users().messages().list(userId="me", q=query).execute()
    messages = results.get("messages", [])

    if not messages:
        # 메시지가 없을 때도 성공적으로 확인했다는 의미로 ✅ 아이콘을 추가합니다.
        logging.info("✅ 처리할 새 Google Scholar 알리미 메일이 없습니다.")
        return

    logging.info(f"총 {len(messages)}개의 새 알리미 메일을 발견했습니다.")
    
    # 모든 공유 자원을 루프 시작 전에 초기화합니다.
    seen_ids = load_seen_ids()
    successful_saves = 0
    all_paper_tasks = []
    existing_titles_cache = {}  # 키워드별 기존 제목 캐시
    lock = threading.Lock()

    # 1단계: 모든 이메일을 순회하며 처리할 작업 목록을 수집합니다.
    for msg_info in messages:
        msg_id = msg_info["id"]
        if msg_id in seen_ids:
            continue
        
        try:
            msg = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
            keyword, articles = parse_scholar_email(msg)
            
            if keyword and articles: # 키워드와 논문이 모두 유효한 경우에만 처리
                # 캐시를 사용하여 동일한 키워드에 대해 파일 시스템을 반복적으로 읽는 것을 방지합니다.
                if keyword not in existing_titles_cache:
                    keyword_dir = os.path.join(PAPERS_OUTPUT_DIR, keyword)
                    existing_titles_cache[keyword] = get_existing_english_titles_from_dir(keyword_dir)
                
                # 현재 이메일의 모든 논문을 전체 작업 목록에 추가합니다.
                for article in articles:
                    all_paper_tasks.append((article, keyword, existing_titles_cache[keyword], lock))
                logging.info(f"이메일 ID {msg_id}에서 {len(articles)}개의 논문을 처리 대기열에 추가했습니다.")

            # 이메일 확인이 성공적으로 끝나면, 유효한 데이터 유무와 상관없이 '읽음' 처리하여 다시 확인하지 않도록 합니다.
            service.users().messages().modify(userId="me", id=msg_id, body={"removeLabelIds": ["UNREAD"]}).execute()
            seen_ids.add(msg_id)

        except Exception as e:
            logging.error(f"이메일 ID {msg_id} 처리 중 오류 발생: {e}", exc_info=True)
            # 오류 발생 시, 해당 이메일은 '읽음' 처리하지 않고 건너뛰어 다음 실행 때 재시도하도록 합니다.
            continue

    # 2단계: 수집된 모든 작업을 병렬로 실행합니다.
    if all_paper_tasks:
        logging.info(f"총 {len(all_paper_tasks)}개의 논문 항목을 병렬로 처리합니다...")
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_to_task = {executor.submit(process_paper_entry, task[0], task[1], task[2], task[3]): task for task in all_paper_tasks}
            count = 0
            total = len(future_to_task)
            for future in as_completed(future_to_task):
                count += 1
                logging.info(f"  - 논문 진행률: {count}/{total} 처리 완료...")
                try:
                    if future.result() is True:
                        successful_saves += 1
                except Exception as exc:
                    logging.error(f"논문 처리 중 예외 발생: {exc}")

    logging.info(f"========== Google Scholar 수집 종료: 총 {successful_saves}개의 새 논문을 저장했습니다. ==========\n")
    
    # 3단계: 모든 작업이 끝난 후, 처리된 ID 목록을 최종 저장합니다.
    save_seen_ids(seen_ids)


if __name__ == "__main__":
    main()