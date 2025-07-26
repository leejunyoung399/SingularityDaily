# 이 파일은 'scripts' 디렉토리가 파이썬 패키지임을 나타냅니다.
# 각 스크립트의 main 함수를 패키지 레벨로 노출시켜 import를 단순화합니다.

from .collect_from_rss import main as collect_from_rss_main
from .collect_from_gmail import main as collect_from_gmail_main
from .process_scholar_email import main as process_scholar_email_main
from .cleanup_duplicates import main as cleanup_duplicates_main
from .generate_nav import main as generate_nav_main

# __all__을 정의하여 'from scripts import *' 사용 시 가져올 모듈을 명시할 수 있습니다.
# (현재 사용하지는 않지만 좋은 습관입니다.)
__all__ = [
    'collect_from_rss_main',
    'collect_from_gmail_main',
    'process_scholar_email_main',
    'cleanup_duplicates_main',
    'generate_nav_main',
]