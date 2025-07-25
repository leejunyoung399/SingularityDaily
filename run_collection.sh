#!/bin/bash

# 스크립트 실행 중 오류가 발생하면 즉시 중단합니다.
set -e

# 스크립트가 위치한 디렉토리로 이동합니다.
# 이렇게 하면 스크립트가 어디에서 호출되든 항상 올바른 경로에서 실행됩니다.
cd "$(dirname "$0")"

echo "--- 데이터 수집을 시작합니다 ---"

# Render는 detached HEAD 상태에서 실행될 수 있으므로, main 브랜치를 명시적으로 체크아웃합니다.
echo "--- main 브랜치를 체크아웃합니다. ---"
git checkout main

# GitHub의 최신 변경사항을 먼저 가져와서 병합(merge)합니다.
echo "--- GitHub과 동기화 중... ---"
# 'origin' 대신 전체 URL을 사용하여 원격 저장소와 동기화합니다.
git pull https://${GITHUB_PAT}@github.com/leejunyoung399/SingularityDaily.git main

# Git 사용자 정보를 설정합니다. (커밋 작성자 정보)
git config --global user.name "Render Cron Bot"
git config --global user.email "render-bot@users.noreply.github.com"

# 단일 진입점 파이썬 스크립트를 실행하여 모든 데이터 수집 및 처리 작업을 조율합니다.
python main.py
 
# --- 디버깅 로그 추가 ---
echo "--- 파이썬 스크립트 실행 완료. Git 상태를 확인합니다. ---"
git status
echo "----------------------------------------------------"

# git status --porcelain: 변경된 파일이 없으면 출력이 비어있습니다.
if [[ -z $(git status --porcelain) ]]; then
  echo "--- 새로운 콘텐츠가 없습니다. 종료합니다. ---"
else
  echo "--- 새로운 콘텐츠를 발견했습니다. GitHub에 커밋 및 푸시합니다. ---"
  
  # 변경된 모든 파일을 추가합니다.
  git add .
  
  # 변경된 파일 수를 계산하여 커밋 메시지에 포함합니다.
  ADDED_COUNT=$(git status --porcelain | grep "^A" | wc -l)
  MODIFIED_COUNT=$(git status --porcelain | grep "^M" | wc -l)
  
  # 변경 내용을 커밋합니다.
  git commit -m "docs: 자동 수집 콘텐츠 업데이트 (추가: ${ADDED_COUNT}, 수정: ${MODIFIED_COUNT})"
  
  # GitHub 저장소에 변경 내용을 푸시합니다.
  # GITHUB_PAT는 Render에 설정할 개인용 액세스 토큰입니다.
  git push https://${GITHUB_PAT}@github.com/leejunyoung399/SingularityDaily.git main
fi