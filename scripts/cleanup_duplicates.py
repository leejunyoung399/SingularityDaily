import os
import re
import logging
import subprocess
from pathlib import Path
from collections import defaultdict

# --- Configuration ---
PROJECT_ROOT = Path(__file__).parent.parent
DOCS_ROOT = PROJECT_ROOT / "docs"
DIRECTORIES_TO_CLEAN = [
    DOCS_ROOT / "articles",
    DOCS_ROOT / "keywords",
]

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

def get_file_commit_date(path):
    """Git 로그를 사용하여 파일의 마지막 커밋 날짜(타임스탬프)를 가져옵니다."""
    try:
        cmd = ['git', 'log', '-1', '--format=%ct', '--', str(path)]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, cwd=PROJECT_ROOT)
        return int(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
        # Git 로그 실패 시 파일 수정 시간으로 대체
        return os.path.getmtime(path)

def main():
    """
    지정된 디렉토리에서 원제목이 동일한 중복 마크다운 파일을 찾아 정리합니다.
    가장 최근에 커밋된 파일을 남기고 나머지는 삭제합니다.
    """
    english_title_map = defaultdict(list)

    logging.info("중복 콘텐츠 정리 시작: 모든 마크다운 파일을 스캔합니다...")

    # 1. 모든 파일 스캔 및 원제목 기준으로 그룹화
    for directory in DIRECTORIES_TO_CLEAN:
        if not directory.is_dir():
            logging.warning(f"정리할 디렉토리를 찾을 수 없습니다: {directory}")
            continue

        for filepath in directory.rglob("*.md"):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                    match = re.search(r"\*\*원제목:\*\*\s*(.*)", content)
                    if match:
                        english_title = match.group(1).strip()
                        english_title_map[english_title].append(filepath)
            except Exception as e:
                logging.warning(f"파일 읽기 오류 {filepath}: {e}")

    logging.info(f"스캔 완료. 총 {len(english_title_map)}개의 고유한 원제목을 발견했습니다.")

    # 2. 중복 파일 식별 및 정리
    deleted_count = 0
    for english_title, file_paths in english_title_map.items():
        if len(file_paths) > 1:
            logging.info(f"\n--- 중복 발견: '{english_title}' ({len(file_paths)}개) ---")
            file_paths.sort(key=get_file_commit_date, reverse=True)
            file_to_keep = file_paths[0]
            logging.info(f"  [보관] {file_to_keep} (가장 최신)")
            for file_to_delete in file_paths[1:]:
                os.remove(file_to_delete)
                logging.info(f"  [삭제] {file_to_delete}")
                deleted_count += 1

    if deleted_count > 0:
        logging.info(f"\n정리 완료. 총 {deleted_count}개의 중복 파일을 삭제했습니다.")
    else:
        logging.info("\n중복 콘텐츠 정리 완료. 삭제할 파일이 없습니다.")

if __name__ == "__main__":
    main()
