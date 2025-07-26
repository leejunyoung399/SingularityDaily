import logging
import sys
import os

# --- 경로 설정 ---
# 현재 파일의 디렉토리(프로젝트 루트)를 Python 경로에 추가합니다.
# 이렇게 하면 어떤 환경에서든 'scripts' 패키지를 안정적으로 찾을 수 있습니다.
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

import scripts # scripts 패키지 전체를 import 합니다.


# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - [%(funcName)s] - %(message)s",
    handlers=[logging.StreamHandler()],
)

# pypdf 라이브러리에서 발생하는 과도한 경고 로그를 필터링합니다.
# ERROR 레벨 이상의 로그만 표시하도록 설정하여, 로그를 깨끗하게 유지합니다.
logging.getLogger("pypdf").setLevel(logging.ERROR)
# google-auth-oauthlib 및 oauth2client 라이브러리의 file_cache 관련 경고를 필터링합니다.
logging.getLogger("google_auth_oauthlib.flow").setLevel(logging.ERROR)
logging.getLogger("oauth2client").setLevel(logging.ERROR)

def run_task(name, task_function):
    """주어진 작업을 실행하고 성공 여부를 로깅합니다."""
    logging.info(f"--- 🚀 '{name}' 작업 시작 ---")
    try:
        task_function()
        logging.info(f"--- ✅ '{name}' 작업 성공 ---")
        return True
    except Exception as e:
        # 오류 발생 시 상세 정보를 로그에 남깁니다.
        logging.error(f"--- ❌ '{name}' 작업 중 오류 발생: {e} ---", exc_info=True)
        return False

if __name__ == "__main__":
    # 실행할 작업 목록 정의
    tasks = [
        ("일반 RSS 기사 수집", scripts.collect_from_rss_main),
        ("Google Alerts 키워드 기사 수집", scripts.collect_from_gmail_main),
        ("Google Scholar 논문 수집", scripts.process_scholar_email_main),
        ("중복 콘텐츠 정리", scripts.cleanup_duplicates_main),
        ("내비게이션 생성", scripts.generate_nav_main),
    ]

    for name, func in tasks:
        if not run_task(name, func):
            # 하나의 스크립트라도 실패하면 전체 프로세스 중단
            logging.critical("하나 이상의 스크립트가 실패하여 전체 프로세스를 중단합니다.")
            sys.exit(1)

    logging.info("🎉 모든 데이터 수집 및 처리 작업이 성공적으로 완료되었습니다.")