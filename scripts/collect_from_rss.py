# c:\MyProjects\SingularityDaily\scripts\collect_from_rss.py
import os
import feedparser
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from .common_utils import (
    strip_html_tags,
    fetch_article_body,
    safe_filename,
    is_duplicate_md,
    translate_text,
    summarize_and_translate_body,
    initialize_gemini,
)
from . import config

# --- Constants ---
MIN_BODY_LENGTH = 300
MAX_ENTRIES_PER_FEED = 10  # 일반 피드는 항목이 많을 수 있으므로 제한
OUTPUT_DIR = config.ARTICLES_PATH  # 설정 파일에서 'articles' 경로 가져오기

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

def save_markdown(title_ko, title_en, summary_ko, url):
    """마크다운 파일을 저장하고, 중복을 확인합니다."""
    try:
        safe_title = safe_filename(title_ko)
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        path = os.path.join(OUTPUT_DIR, f"{safe_title}.md")

        if is_duplicate_md(path, title_en):
            logging.info(f"🚫 중복 기사: {title_en}")
            return False

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

def process_entry(entry):
    """개별 RSS 항목을 처리합니다."""
    try:
        title_en = strip_html_tags(entry.get("title", ""))
        link = entry.get("link", "")

        if not title_en or not link:
            logging.warning("제목 또는 링크가 없는 항목을 건너뜁니다.")
            return

        body = fetch_article_body(link)

        if not body or len(body.strip()) < MIN_BODY_LENGTH:
            logging.info(f"⚠️ 본문 부족/추출 실패 — 저장하지 않음: {title_en}")
            return

        title_ko = translate_text(title_en)
        summary_ko = summarize_and_translate_body(body)
        
        if not title_ko or not summary_ko:
            logging.error(f"번역 실패: {title_en}")
            return

        save_markdown(title_ko, title_en, summary_ko, link)

    except Exception as e:
        logging.error(f"항목 처리 중 오류 발생 ({entry.get('title', 'N/A')}): {e}")

def main():
    """모든 일반 RSS 피드를 순회하며 기사를 수집하고 저장합니다."""
    try:
        initialize_gemini()
    except (ValueError, RuntimeError) as e:
        logging.error(f"스크립트 실행 중단: {e}")
        exit(1)

    all_tasks = []
    for feed_url in config.RSS_FEEDS:
        logging.info(f"========== 🌐 일반 RSS 피드 스캔 중: {feed_url} ==========")
        try:
            feed = feedparser.parse(feed_url)
            if feed.bozo:
                logging.warning(f"피드 파싱 문제 ({feed_url}): {feed.bozo_exception}")

            entries = feed.entries[:MAX_ENTRIES_PER_FEED]
            all_tasks.extend(entries)
        except Exception as e:
            logging.error(f"피드 처리 중 오류 발생 ({feed_url}): {e}")

    if not all_tasks:
        logging.info("처리할 새 일반 RSS 항목이 없습니다.")
        return

    logging.info(f"총 {len(all_tasks)}개의 일반 RSS 항목을 병렬로 처리합니다...")

    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_task = {executor.submit(process_entry, task): task for task in all_tasks}
        
        for i, future in enumerate(as_completed(future_to_task), 1):
            logging.info(f"  - 일반 기사 진행률: {i}/{len(all_tasks)} 처리 완료...")
            try:
                future.result()
            except Exception as exc:
                task = future_to_task[future]
                logging.error(f"항목 처리 중 예외 발생 ({task.get('title', 'N/A')}): {exc}")

    logging.info("========== 일반 RSS 수집 종료 ==========\n")

if __name__ == "__main__":
    main()