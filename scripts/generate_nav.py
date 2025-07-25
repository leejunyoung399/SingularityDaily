import os
import yaml
import re
import logging
import math
import subprocess
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DOCS_ROOT = PROJECT_ROOT / "docs"
ITEMS_PER_PAGE = 100  # 페이지당 표시할 항목 수

def shorten_title(title, max_length=60):
    """긴 제목을 자르고, 개행 및 특수문자를 제거합니다."""
    title = title.strip().replace('\n', ' ').replace('\r', '')
    title = re.sub(r'\s+', ' ', title)
    title = re.sub(r'[\"\'`]', '', title)
    if len(title) > max_length:
        title = title[:max_length].rstrip() + "..."
    return title

def create_paginated_index(title, sorted_paths, output_dir):
    """페이지네이션된 인덱스 페이지들을 생성합니다."""
    if not sorted_paths:
        return

    total_items = len(sorted_paths)
    total_pages = math.ceil(total_items / ITEMS_PER_PAGE)

    for page_num in range(1, total_pages + 1):
        start_index = (page_num - 1) * ITEMS_PER_PAGE
        end_index = start_index + ITEMS_PER_PAGE
        page_paths = sorted_paths[start_index:end_index]

        content = f"# {title}\n\n"
        for file_path in page_paths:
            file_title = file_path.stem
            relative_link = os.path.relpath(file_path, output_dir)
            link = str(relative_link).replace("\\", "/")
            content += f"- [{file_title}]({link})\n"
        
        # 페이지네이션 네비게이션 추가
        content += "\n---\n"
        nav_links = []
        if page_num > 1:
            prev_page_link = "index.md" if page_num == 2 else f"page-{page_num - 1}.md"
            nav_links.append(f"[<< 이전 페이지]({prev_page_link})")
        
        nav_links.append(f"페이지 {page_num} / {total_pages}")

        if page_num < total_pages:
            next_page_link = f"page-{page_num + 1}.md"
            nav_links.append(f"[다음 페이지 >>]({next_page_link})")
        
        content += "  |  ".join(nav_links)

        page_filename = "index.md" if page_num == 1 else f"page-{page_num}.md"
        page_path = output_dir / page_filename
        page_path.write_text(content, encoding="utf-8")
    logging.info(f"✅ '{title}' 섹션에 {total_pages}개의 페이지 생성 완료.")

def get_file_commit_date(path):
    """Git 로그를 사용하여 파일의 마지막 커밋 날짜(타임스탬프)를 가져옵니다."""
    try:
        # --format=%ct는 커밋 시간을 유닉스 타임스탬프로 출력합니다.
        cmd = ['git', 'log', '-1', '--format=%ct', '--', str(path)]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, cwd=PROJECT_ROOT)
        return int(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
        # Git 명령이 실패하면 파일 수정 시간을 대체 값으로 사용합니다.
        return os.path.getmtime(path)

def process_directory(path, title, is_recursive=False):
    """디렉토리를 처리하여 페이지네이션된 인덱스를 생성하고, 내비게이션 경로를 반환합니다."""
    if not path.exists() or not path.is_dir():
        return None

    all_md_paths = [p for p in path.glob("*.md") if p.name != "index.md"]
    if not all_md_paths:
        return None

    # 파일 수정 시간 대신, Git 커밋 시간을 기준으로 정렬합니다.
    all_md_paths.sort(key=get_file_commit_date, reverse=True)
    create_paginated_index(title, all_md_paths, path)
    
    # 좌측 메뉴에는 최상위 인덱스 파일만 연결합니다.
    return str(path.relative_to(DOCS_ROOT)).replace("\\", "/") + "/index.md"

def main():
    """스크립트의 메인 실행 함수."""
    logging.info("🔍 'docs' 폴더를 스캔하여 내비게이션 구조를 생성합니다...")
    sections = {}

    # '기사' 섹션 처리
    articles_index = process_directory(DOCS_ROOT / "articles", "기사")
    if articles_index:
        sections['기사'] = articles_index

    # '블로그' 섹션 처리
    blog_index = process_directory(DOCS_ROOT / "blog", "블로그")
    if blog_index:
        sections['블로그'] = blog_index

    # '키워드' 섹션 처리 (하위 디렉토리 포함)
    keywords_path = DOCS_ROOT / "keywords"
    if keywords_path.exists() and keywords_path.is_dir():
        keyword_entries = {}
        all_keyword_dirs = [d for d in sorted(keywords_path.iterdir()) if d.is_dir()]
        for keyword_dir in all_keyword_dirs:
            # 각 키워드 폴더를 개별적으로 처리합니다.
            keyword_index = process_directory(keyword_dir, f"{keyword_dir.name} 관련 글")
            if keyword_index:
                keyword_entries[keyword_dir.name] = keyword_index
        if keyword_entries:
            # mkdocs.yml의 nav 형식에 맞게 재구성합니다.
            sections['키워드'] = [{kw: path} for kw, path in sorted(keyword_entries.items())]
    
    write_mkdocs_yml(sections)

def write_mkdocs_yml(sections):
    """수집된 파일 목록으로 mkdocs.yml 파일을 생성합니다."""
    config = {
        "site_name": "Singularity Daily",
        "site_url": "https://www.singularitydaily.com/",
        "site_author": "leejunyoung399",
        "site_description": "특이점, AI, 생명 연장 등 최신 기술 동향을 수집하고 요약합니다.",
        "theme": {
            "name": "material",
            "language": "ko",
            "logo": "assets/logo.png",
            "favicon": "assets/logo.png",
            "features": [
                # "navigation.instant", # '원문 링크' 새 창 열기 기능과의 충돌로 비활성화
                "navigation.top",
                "navigation.tracking",
                "navigation.expand", # 모든 하위 메뉴를 항상 펼쳐진 상태로 유지
                "content.code.copy",
            ]
        },
        "use_directory_urls": False,
        "markdown_extensions": [
            "admonition",
            {"toc": {"permalink": "¶"}},
            "footnotes",
            "meta",
            "attr_list", # 링크에 속성을 추가할 수 있도록 활성화
        ],
        "extra_css": ["stylesheets/extra.css"],
        "plugins": ["search"],
    }

    nav_structure = [{'홈': 'index.md'}]
    
    # 원하는 순서대로 nav에 추가
    if '블로그' in sections:
        nav_structure.append({'블로그': sections['블로그']})
    if '기사' in sections:
        nav_structure.append({'기사': sections['기사']})
    if '키워드' in sections:
        nav_structure.append({'키워드': sections['키워드']})

    config['nav'] = nav_structure
    output_path = PROJECT_ROOT / "mkdocs.yml"
    with open(output_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, sort_keys=False, width=1000)

    logging.info(f"✅ '{output_path}' 파일이 성공적으로 생성/업데이트되었습니다.")

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    main()