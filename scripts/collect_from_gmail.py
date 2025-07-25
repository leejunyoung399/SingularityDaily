# c:\MyProjects\SingularityDaily\scripts\collect_from_gmail.py
import os
import feedparser
import logging
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from .common_utils import (
    clean_google_url,
    strip_html_tags,
    fetch_article_body,
    safe_filename,
    get_existing_english_titles_from_dir,
    translate_text,
    summarize_and_translate_body,
    initialize_gemini,
)
from . import config # 설정 파일 import 추가

# --- Constants ---
# RSS 피드 목록은 config.py에서 관리합니다.
MIN_BODY_LENGTH = 300
MAX_ENTRIES_PER_FEED = 20
OUTPUT_DIR = os.path.join("docs", "keywords")

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

def save_markdown(keyword, title_ko, title_en, summary_ko, url):
    """마크다운 파일을 저장합니다."""
    try:
        safe_title = safe_filename(title_ko)
        folder = os.path.join(OUTPUT_DIR, keyword)
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
        logging.error(f"파일 저장 중 오류 발생 ({title_en}): {e}", exc_info=True)
        return False

def process_entry(entry, keyword, existing_titles, lock):
    """개별 RSS 항목을 처리합니다."""
    try:
        raw_title = entry.get("title", "")
        raw_link = entry.get("link", "")
        link = clean_google_url(raw_link)
        title_en = strip_html_tags(raw_title)

        if not title_en or not link:
            logging.warning("제목 또는 링크가 없는 항목을 건너뜁니다.")
            return False

        with lock:
            if title_en in existing_titles:
                logging.info(f"🚫 중복 기사: {title_en}")
                return False
            existing_titles.add(title_en)

        # 본문 먼저 추출 후 필터
        body = fetch_article_body(link)

        # 본문 추출 실패 시 처리
        if not body:
            logging.info(f"⚠️ 본문 추출 실패 — 저장하지 않음: {title_en}")
            return False
        # 본문이 너무 짧을 경우 처리
        if len(body.strip()) < MIN_BODY_LENGTH:
            logging.info(f"⚠️ 본문 부족({len(body.strip())}자) — 저장하지 않음: {title_en}")
            return False

        # 번역 수행 (비용 발생)
        title_ko = translate_text(title_en)
        summary_ko = summarize_and_translate_body(body)
        
        if not title_ko or not summary_ko:
            logging.error(f"번역 실패: {title_en}")
            return False

        if save_markdown(keyword, title_ko, title_en, summary_ko, url):
            return True # 제목은 이미 목록에 추가되었습니다.
        return False

    except Exception as e:
        logging.error(f"항목 처리 중 오류 발생 ({entry.get('title', 'N/A')}): {e}", exc_info=True)
        return False

def main():
    """모든 RSS 피드를 순회하며 기사를 수집하고 저장합니다."""
    try:
        initialize_gemini()
    except (ValueError, RuntimeError) as e:
        logging.error(f"스크립트 실행 중단: {e}")
        exit(1)

    existing_titles_cache = {}
    for keyword in config.GOOGLE_ALERTS_RSS_FEEDS.keys():
        keyword_dir = os.path.join(OUTPUT_DIR, keyword)
        existing_titles_cache[keyword] = get_existing_english_titles_from_dir(keyword_dir)
        logging.info(f"기존 '{keyword}' 키워드 {len(existing_titles_cache[keyword])}개의 원제목을 불러왔습니다.")
    lock = threading.Lock()

    all_tasks = []
    for keyword, feed_url in config.GOOGLE_ALERTS_RSS_FEEDS.items():
        logging.info(f"========== 🌐 RSS 피드 스캔 중: {keyword} ==========")
        try:
            feed = feedparser.parse(feed_url)
            if feed.bozo:
                logging.warning(f"'{keyword}' 피드 파싱 문제: {feed.bozo_exception}")

            entries = feed.entries[:MAX_ENTRIES_PER_FEED]
            for entry in entries:
                all_tasks.append((entry, keyword, existing_titles_cache[keyword], lock))
        except Exception as e:
            logging.error(f"'{keyword}' 피드 처리 중 오류 발생: {e}")

    if not all_tasks:
        logging.info("처리할 새 RSS 항목이 없습니다.")
        return

    logging.info(f"총 {len(all_tasks)}개의 RSS 항목을 병렬로 처리합니다...")

    successful_saves = 0
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_task = {executor.submit(process_entry, task[0], task[1], task[2], task[3]): task for task in all_tasks}
        
        count = 0
        total = len(future_to_task)
        for future in as_completed(future_to_task):
            count += 1
            logging.info(f"  - RSS 진행률: {count}/{total} 처리 완료...")
            try:
                if future.result() is True:
                    successful_saves += 1
            except Exception as exc:
                task = future_to_task[future]
                logging.error(f"항목 처리 중 예외 발생 ({task[0].get('title', 'N/A')}): {exc}")

    logging.info(f"========== RSS 수집 종료: 총 {successful_saves}개의 새 키워드 기사를 저장했습니다. ==========\n")

if __name__ == "__main__":
    main()
