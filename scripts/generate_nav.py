import os
import yaml
import re
import logging
import math
import subprocess
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

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
            # 링크를 올바르게 생성하고 URL 인코딩을 적용합니다.
            link = quote(str(relative_link).replace("\\", "/"))
            content += f"- {file_title}\n"
        
        # 페이지네이션 네비게이션 추가
        content += "\n---\n"
        nav_links = []
        if page_num > 1:
            prev_page_link = "index.md" if page_num == 2 else f"page-{page_num - 1}.md"
            nav_links.append(f"{'<< 이전 페이지'}")
        
        nav_links.append(f"페이지 {page_num} / {total_pages}")

        if page_num < total_pages:
            next_page_link = f"page-{page_num + 1}.md"
            nav_links.append(f"{'다음 페이지 >>'}")
        
        content += "  |  ".join(nav_links)

        page_filename = "index.md" if page_num == 1 else f"page-{page_num}.md"
        page_path = output_dir / page_filename
        page_path.write_text(content, encoding="utf-8")
    logging.info(f"✅ '{title}' 섹션에 {total_pages}개의 페이지 생성 완료.")

def get_all_commit_dates(root_path):
    """Git 로그를 한 번만 실행하여 모든 파일의 마지막 커밋 날짜를 효율적으로 수집합니다."""
    logging.info(f"Git 커밋 기록을 스캔하여 파일 날짜를 수집합니다... (시간이 걸릴 수 있습니다)")
    file_dates = {}
    try:
        # --pretty=format:commit %ct: 각 커밋을 'commit' 키워드와 타임스탬프로 시작
        # --name-only: 각 커밋에 포함된 파일 목록만 표시
        cmd = ['git', 'log', '--pretty=format:commit %ct', '--name-only', '--', str(root_path)]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, cwd=PROJECT_ROOT)
        
        # 'commit '을 기준으로 출력을 분리하여 각 커밋을 처리
        for commit_block in result.stdout.strip().split('commit '):
            if not commit_block:
                continue
            
            lines = commit_block.strip().split('\n')
            try:
                commit_date = int(lines[0])
                # 두 번째 줄부터 파일 경로
                for file_path_str in lines[1:]:
                    full_path = PROJECT_ROOT / file_path_str.strip()
                    # git log는 최신순이므로, 파일이 맵에 없으면 추가 (가장 최신 커밋 날짜)
                    if full_path not in file_dates:
                        file_dates[full_path] = commit_date
            except (ValueError, IndexError):
                continue
        logging.info(f"✅ {len(file_dates)}개의 파일에 대한 커밋 날짜를 수집했습니다.")
        return file_dates
    except Exception as e:
        logging.error(f"Git 커밋 날짜 수집 중 오류 발생: {e}. 파일 수정 시간으로 대체합니다.")
        return {}

def process_directory(path, title, commit_date_map, is_recursive=False):
    """디렉토리를 처리하여 페이지네이션된 인덱스를 생성하고, 내비게이션 경로를 반환합니다."""
    if not path.exists() or not path.is_dir():
        return None

    all_md_paths = [p for p in path.glob("*.md") if p.name != "index.md" and not p.name.startswith("page-")]
    if not all_md_paths:
        return None

    # 최적화: 미리 계산된 맵에서 커밋 날짜를 조회하여 정렬합니다.
    all_md_paths.sort(key=lambda p: commit_date_map.get(p, os.path.getmtime(p)), reverse=True)
    create_paginated_index(title, all_md_paths, path)
    
    # 좌측 메뉴에는 최상위 인덱스 파일만 연결합니다.
    return str(path.relative_to(DOCS_ROOT)).replace("\\", "/") + "/index.md"

def main():
    """스크립트의 메인 실행 함수."""
    logging.info("🔍 'docs' 폴더를 스캔하여 내비게이션 구조를 생성합니다...")
    
    # 최적화: 스크립트 시작 시 모든 파일의 커밋 날짜를 한 번에 수집합니다.
    commit_date_map = get_all_commit_dates(DOCS_ROOT)
    
    sections = {}

    # '기사' 섹션 처리
    articles_index = process_directory(DOCS_ROOT / "articles", "기사", commit_date_map)
    if articles_index:
        sections['기사'] = articles_index

    # '블로그' 섹션 처리
    blog_index = process_directory(DOCS_ROOT / "blog", "블로그", commit_date_map)
    if blog_index:
        sections['블로그'] = blog_index

    # '키워드' 섹션 처리 (하위 디렉토리 포함)
    keywords_path = DOCS_ROOT / "keywords"
    if keywords_path.exists() and keywords_path.is_dir():
        keyword_entries = {}
        all_keyword_dirs = [d for d in sorted(keywords_path.iterdir()) if d.is_dir()]
        for keyword_dir in all_keyword_dirs:
            # 각 키워드 폴더를 개별적으로 처리합니다.
            keyword_index = process_directory(keyword_dir, f"{keyword_dir.name} 관련 글", commit_date_map)
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
