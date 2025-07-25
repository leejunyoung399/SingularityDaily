import email
import logging
import os
import re
import base64
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

    # "keyword - new results" 형식의 제목에서 키워드 추출
    keyword_match = re.match(r"^(.*?) - new results", subject)
    if keyword_match:
        keyword = keyword_match.group(1).strip()
    else:
        keyword = subject.strip() # 매치 실패 시, 제목 전체를 키워드로 사용

    logging.info(f"🔑 추출된 키워드: {keyword}")

    body_data = get_html_payload_from_message(msg)
    if not body_data:
        logging.error("이메일에서 HTML 콘텐츠를 찾을 수 없습니다.")
        return keyword, []

    html_content = base64.urlsafe_b64decode(body_data).decode("utf-8")
    soup = BeautifulSoup(html_content, "html.parser")
    articles = []

    for link_tag in soup.find_all("a", class_="gse_alrt_title"):
        title_en = link_tag.get_text(strip=True)
        url = link_tag.get("href", "")
        snippet_tag = link_tag.find_parent("h3").find_next_sibling("div", class_="gse_alrt_sni")
        snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""
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


def process_paper_entry(article, keyword, existing_titles):
    """개별 논문 항목을 처리, 번역, 저장합니다."""
    try:
        title_en, link_url, snippet = article["title_en"], article["url"], article["snippet"]

        if title_en in existing_titles:
            logging.info(f"🚫 중복 논문: {title_en}")
            return False

        logging.info(f"--- ⚙️ 처리 시작: {title_en} ---")

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

        title_ko, summary_ko = translate_text(title_en), summarize_and_translate_body(body)
        if not title_ko or not summary_ko:
            logging.error(f"번역 실패: {title_en}")
            return False
        
        if save_paper_markdown(keyword, title_ko, title_en, summary_ko, link):
            existing_titles.add(title_en)
            return True
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

    # 읽지 않은 구글 스칼라 알리미 메일만 가져오도록 쿼리를 복원합니다.
    query = "from:scholaralerts-noreply@google.com is:unread"
    logging.info(f"🔍 Gmail에서 다음 쿼리로 새 논문 알림을 검색합니다: '{query}'")
    results = service.users().messages().list(userId="me", q=query).execute()
    messages = results.get("messages", [])

    if not messages:
        # 메시지가 없을 때도 성공적으로 확인했다는 의미로 ✅ 아이콘을 추가합니다.
        logging.info("✅ 처리할 새 Google Scholar 알리미 메일이 없습니다.")
        return

    logging.info(f"총 {len(messages)}개의 새 알리미 메일을 발견했습니다.")
    seen_ids = load_seen_ids()
    successful_saves = 0
    all_paper_tasks = []
    existing_titles_cache = {}  # 키워드별 기존 제목 캐시

    for msg_info in messages:
        msg_id = msg_info["id"]
        if msg_id in seen_ids:
            continue
        
        msg = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
        keyword, articles = parse_scholar_email(msg)
        if not articles:
            # 논문이 없는 메일도 처리한 것으로 간주
            seen_ids.add(msg_id)
            continue

        # 캐시를 사용하여 동일한 키워드에 대해 파일 시스템을 반복적으로 읽는 것을 방지합니다.
        if keyword not in existing_titles_cache:
            keyword_dir = os.path.join(PAPERS_OUTPUT_DIR, keyword)
            existing_titles_cache[keyword] = get_existing_english_titles_from_dir(keyword_dir)

        for article in articles:
            all_paper_tasks.append((article, keyword, existing_titles_cache[keyword]))

        # 처리가 끝난 메일은 '읽음'으로 표시하고, seen 목록에 추가
        service.users().messages().modify(userId="me", id=msg_id, body={"removeLabelIds": ["UNREAD"]}).execute()
        seen_ids.add(msg_id)

    if all_paper_tasks:
        logging.info(f"총 {len(all_paper_tasks)}개의 논문 항목을 병렬로 처리합니다...")
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_task = {executor.submit(process_paper_entry, task[0], task[1], task[2]): task for task in all_paper_tasks}
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
    save_seen_ids(seen_ids)


if __name__ == "__main__":
    main()