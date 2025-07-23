#!/bin/bash

# 스크립트 실행 중 오류가 발생하면 즉시 중단합니다.
set -e

echo "--- 데이터 수집을 시작합니다 ---"

# Git 사용자 정보를 설정합니다. (커밋 작성자 정보)
git config --global user.name "Render Cron Bot"
git config --global user.email "render-bot@users.noreply.github.com"

# 파이썬 스크립트들을 순서대로 실행합니다.
python -m scripts.collect_from_gmail
python -m scripts.process_scholar_email
python -m scripts.generate_nav

# git status --porcelain: 변경된 파일이 없으면 출력이 비어있습니다.
if [[ -z $(git status --porcelain) ]]; then
  echo "--- 새로운 콘텐츠가 없습니다. 종료합니다. ---"
else
  echo "--- 새로운 콘텐츠를 발견했습니다. GitHub에 커밋 및 푸시합니다. ---"
  
  # 변경된 모든 파일을 추가합니다.
  git add .
  
  # 변경 내용을 커밋합니다.
  git commit -m "docs: 자동 수집 콘텐츠 업데이트"
  
  # GitHub 저장소에 변경 내용을 푸시합니다.
  # GITHUB_PAT는 Render에 설정할 개인용 액세스 토큰입니다.
  git push https://${GITHUB_PAT}@github.com/leejunyoung399/SingularityDaily.git main
fi