# common_utils.py
import os
import re
import requests
import logging
import random
import trafilatura
from dotenv import load_dotenv
import google.generativeai as genai
from io import BytesIO
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs

# Gmail 인증을 위한 추가 import
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# .env 파일에서 환경 변수 로드
load_dotenv()

try:
    from pypdf import PdfReader
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36",
]

def initialize_gemini():
    """Gemini API를 초기화합니다. API 키가 없으면 예외를 발생시킵니다."""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        # GitHub Actions 환경에서 이 오류는 보통 Secrets 설정 문제임을 의미합니다.
        raise ValueError("API 초기화 실패: GOOGLE_API_KEY 환경 변수가 설정되지 않았거나 비어있습니다. GitHub Secrets를 확인해주세요.")
    
    try:
        genai.configure(api_key=api_key)
        logging.info("✅ Gemini API가 성공적으로 초기화되었습니다.")
    except Exception as e:
        # 더 구체적인 에러로 변환하여 전파합니다.
        raise RuntimeError(f"Gemini API 설정 실패: {e}") from e

def strip_html_tags(text):
    return re.sub(r"<.*?>", "", text or "")


def clean_google_url(url):
    """Google Alerts 및 Scholar의 리디렉션 URL에서 실제 기사 URL을 추출합니다."""
    if not url:
        return url
    
    parsed_url = urlparse(url)
    hostname = parsed_url.hostname
    
    if hostname and 'google.com' in hostname and ('/url' in parsed_url.path or '/scholar_url' in parsed_url.path):
        query_params = parse_qs(parsed_url.query)
        target_url = query_params.get('q', [None])[0] or query_params.get('url', [None])[0]
        if target_url:
            return target_url
    return url


def translate_text(text):
    """Gemini API를 사용하여 텍스트를 한국어로 번역합니다."""
    if not text.strip():
        return ""

    try:
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        prompt = (
            "Please translate the following text into Korean. "
            "Return only the translation, with no explanation, no greetings, and no formatting.\n"
            f"Text to translate:\n{text}"
        )
        request_options = {"timeout": 60}  # 60초 타임아웃
        response = model.generate_content(prompt, request_options=request_options)
        return response.text.strip()
    except Exception as e:
        logging.error(f"⚠️ 번역 실패 (Gemini API): {e}")
        return ""


def summarize_and_translate_body(text):
    """Gemini API를 사용하여 논문 본문을 더 긴 한국어 요약으로 생성합니다."""
    if not text.strip():
        return ""

    try:
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        prompt = (
            "You are a helpful assistant for a researcher. "
            "The following text is an abstract or the body of a research paper. "
            "Please read it and provide a comprehensive summary in Korean. "
            "The summary should be detailed, around 8-10 sentences long, capturing the key points, methodology, and conclusions of the paper. "
            "Return only the Korean summary, with no other explanations or greetings.\n\n"
            f"Text to summarize:\n{text}"
        )
        request_options = {"timeout": 120}  # 요약은 더 길 수 있으므로 120초
        response = model.generate_content(prompt, request_options=request_options)
        return response.text.strip()
    except Exception as e:
        logging.error(f"⚠️ 요약 실패 (Gemini API): {e}")
        return ""


def fetch_article_body(url, max_length=4000):
    """주어진 URL에서 기사/논문 본문을 추출합니다. HTML과 PDF를 지원하며, 추출 실패 시 대체 방법을 사용합니다."""
    try:
        headers = {
            'User-Agent': random.choice(USER_AGENTS)
        }
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()

        content_type = response.headers.get('Content-Type', '').lower()

        # PDF 처리
        if 'application/pdf' in content_type:
            if not PYPDF_AVAILABLE:
                logging.warning(f"  - PDF 콘텐츠({url}) 발견, 하지만 'pypdf'가 설치되지 않아 건너뜁니다.")
                return None
            
            logging.info(f"  - PDF 콘텐츠 감지. 텍스트 추출 중... ({url})")
            with BytesIO(response.content) as pdf_file:
                reader = PdfReader(pdf_file)
                text = "".join(page.extract_text() or "" for page in reader.pages)
            
            if not text:
                logging.warning(f"  - PDF에서 텍스트를 추출할 수 없습니다 ({url})")
                return None
            return text.strip()[:max_length]

        # HTML 처리 (trafilatura가 기본, BeautifulSoup이 대체)
        article_text = trafilatura.extract(response.text, include_comments=False, include_tables=False)
        
        if not article_text:
            logging.info(f"  - trafilatura 실패. BeautifulSoup으로 대체합니다 ({url})")
            soup = BeautifulSoup(response.text, "html.parser")
            article_tag = soup.find("article")
            if article_tag:
                article_text = article_tag.get_text(separator='\n', strip=True)

        if not article_text:
            logging.warning(f"⚠️ 본문 크롤 실패: 메인 콘텐츠를 추출할 수 없습니다 ({url})")
            return None
            
        return article_text.strip()[:max_length]

    except requests.exceptions.HTTPError as e:
        logging.warning(f"HTTP 오류 ({e.response.status_code}) - URL: {url}")
        return None
    except requests.exceptions.ReadTimeout:
        logging.warning(f"Read Timeout - URL: {url}")
        return None
    except requests.exceptions.ConnectionError as e:
        logging.warning(f"Connection 오류 - URL: {url}")
        return None
    except Exception as e:
        logging.error(f"본문 크롤 중 예측하지 못한 오류 발생: {url}: {e}", exc_info=False)
        return None

def is_duplicate_md(filepath, original_title):
    if not os.path.exists(filepath):
        return False
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            return original_title in content
    except:
        return False

def safe_filename(text, max_length=80):
    text = re.sub(r"[\\/:*?\"<>|]", "", text)
    return text.strip()[:max_length]


def get_gmail_service():
    """
    Gmail API와 인증하고 서비스 객체를 반환합니다.
    로컬과 서버 환경 모두에서 토큰 생성, 검증, 갱신을 처리하는 중앙 함수입니다.
    """
    creds = None
    TOKEN_PATH = "token.json"
    CREDENTIALS_PATH = "credentials.json"
    SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

    if os.path.exists(TOKEN_PATH):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
        except Exception as e:
            logging.error(f"{TOKEN_PATH}에서 인증 정보를 불러오는 데 실패했습니다: {e}")
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logging.info("만료된 Gmail API 토큰을 갱신합니다...")
            try:
                creds.refresh(Request())
                # Render 환경이 아닐 때만 (즉, 로컬에서) 토큰 파일 갱신
                if not os.getenv("RENDER"):
                    with open(TOKEN_PATH, "w") as token:
                        token.write(creds.to_json())
            except Exception as e:
                logging.error(f"토큰 갱신에 실패했습니다. 재인증이 필요할 수 있습니다. 오류: {e}")
                creds = None
        else:
            # 서버 환경에서는 자동 인증 흐름을 시도하지 않고 에러를 명확히 보고
            if os.getenv("RENDER"):
                logging.error("CRITICAL: 서버에서 Gmail 인증에 실패했습니다.")
                logging.error("CRITICAL: 'refresh_token'이 포함된 유효한 'token.json'을 Secret File로 제공해야 합니다.")
                return None
            
            # 로컬 환경에서만 실행되는 인증 흐름
            logging.info("새로운 Gmail API 사용자 인증을 시작합니다...")
            if not os.path.exists(CREDENTIALS_PATH):
                logging.error(f"CRITICAL: '{CREDENTIALS_PATH}' 파일을 찾을 수 없습니다.")
                return None
            
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_console()
            with open(TOKEN_PATH, "w") as token:
                token.write(creds.to_json())

    if not creds:
        logging.error("Gmail API에 대한 유효한 인증 정보를 얻지 못했습니다.")
        return None

    try:
        service = build("gmail", "v1", credentials=creds)
        logging.info("✅ Gmail 서비스가 성공적으로 생성되었습니다.")
        return service
    except Exception as e:
        logging.error(f"Gmail 서비스 빌드에 실패했습니다: {e}")
        return None
